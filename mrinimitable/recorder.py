# Copyright (c) 2018, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import cProfile
import functools
import inspect
import io
import json
import pstats
import re
import time
import typing
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import sqlparse

import mrinimitable
from mrinimitable import _
from mrinimitable.database.utils import is_query_type
from mrinimitable.utils import now_datetime

RECORDER_INTERCEPT_FLAG = "recorder-intercept"
RECORDER_CONFIG_FLAG = "recorder-config"
RECORDER_REQUEST_SPARSE_HASH = "recorder-requests-sparse"
RECORDER_REQUEST_HASH = "recorder-requests"
TRACEBACK_PATH_PATTERN = re.compile(".*/apps/")
RECORDER_AUTO_DISABLE = 10 * 60


if typing.TYPE_CHECKING:
	from mrinimitable.database.database import Database


@dataclass
class RecorderConfig:
	record_requests: bool = True  # Record web request
	record_jobs: bool = True  # record background jobs
	record_sql: bool = True  # Record SQL queries
	capture_stack: bool = True  # Recod call stack of SQL queries
	profile: bool = False  # Run cProfile
	explain: bool = True  # Provide explain output of SQL queries
	request_filter: str = "/"  # Filter request paths
	jobs_filter: str = ""  # Filter background jobs

	def __post_init__(self):
		if not (self.record_jobs or self.record_requests):
			mrinimitable.throw("You must record one of jobs or requests")

	def store(self):
		mrinimitable.cache.set_value(RECORDER_CONFIG_FLAG, self, expires_in_sec=RECORDER_AUTO_DISABLE)

	@classmethod
	def retrieve(cls):
		return mrinimitable.cache.get_value(RECORDER_CONFIG_FLAG) or cls()

	@staticmethod
	def delete():
		mrinimitable.cache.delete_value(RECORDER_CONFIG_FLAG)


def record_sql(*args, **kwargs):
	start_time = time.monotonic()
	result = mrinimitable.db._sql(*args, **kwargs)
	end_time = time.monotonic()

	query = getattr(mrinimitable.db, "last_query", None)
	if not query or isinstance(result, str):
		# run=0, doesn't actually run the query so last_query won't be present
		return result

	stack = []
	if mrinimitable.local._recorder.config.capture_stack:
		stack = list(get_current_stack_frames())

	data = {
		"query": str(query),
		"stack": stack,
		"explain_result": [],
		"time": start_time,
		"duration": float(f"{(end_time - start_time) * 1000:.3f}"),
	}

	mrinimitable.local._recorder.register(data)
	return result


def get_current_stack_frames():
	from mrinimitable.utils.safe_exec import SERVER_SCRIPT_FILE_PREFIX

	try:
		current = inspect.currentframe()
		frames = inspect.getouterframes(current, context=10)
		for frame, filename, lineno, function, context, index in list(reversed(frames))[:-2]:  # noqa: B007
			if "/apps/" in filename or SERVER_SCRIPT_FILE_PREFIX in filename:
				yield {
					"filename": TRACEBACK_PATH_PATTERN.sub("", filename),
					"lineno": lineno,
					"function": function,
				}
	except Exception:
		pass


def post_process():
	"""post process all recorded values.

	Any processing that can be done later should be done here to avoid overhead while
	profiling. As of now following values are post-processed:
	        - `EXPLAIN` output of queries.
	        - SQLParse reformatting of queries
	        - Mark duplicates
	"""
	mrinimitable.db.rollback()
	mrinimitable.db.begin(read_only=True)  # Explicitly start read only transaction

	config = RecorderConfig.retrieve()
	result = list(mrinimitable.cache.hgetall(RECORDER_REQUEST_HASH).values())

	for request in result:
		for call in request["calls"]:
			formatted_query = sqlparse.format(
				call["query"].strip(), keyword_case="upper", reindent=True, strip_comments=True
			)
			call["query"] = formatted_query

			# Collect EXPLAIN for executed query
			if config.explain and is_query_type(formatted_query, ("select", "update", "delete")):
				# Only SELECT/UPDATE/DELETE queries can be "EXPLAIN"ed
				try:
					call["explain_result"] = mrinimitable.db.sql(f"EXPLAIN {formatted_query}", as_dict=True)
				except Exception:
					pass
		mark_duplicates(request)
		mrinimitable.cache.hset(RECORDER_REQUEST_HASH, request["uuid"], request)

	config.delete()


def mark_duplicates(request):
	exact_duplicates = Counter([call["query"] for call in request["calls"]])

	for sql_call in request["calls"]:
		sql_call["normalized_query"] = normalize_query(sql_call["query"])

	normalized_duplicates = Counter([call["normalized_query"] for call in request["calls"]])

	for index, call in enumerate(request["calls"]):
		call["index"] = index
		call["exact_copies"] = exact_duplicates[call["query"]]
		call["normalized_copies"] = normalized_duplicates[call["normalized_query"]]


def normalize_query(query: str) -> str:
	"""Attempt to normalize query by removing variables.
	This gives a different view of similar duplicate queries.

	Example:
	        These two are distinct queries:
	                `select * from user where name = 'x'`
	                `select * from user where name = 'z'`

	        But their "normalized" form would be same:
	                `select * from user where name = ?`
	"""

	try:
		q = sqlparse.parse(query)[0]
		for token in q.flatten():
			if "Token.Literal" in str(token.ttype):
				token.value = "?"

		# Transform IN parts like this: IN (?, ?, ?) -> IN (?)
		q = re.sub(r"( IN )\(\?[\s\n\?\,]*\)", r"\1(?)", str(q), flags=re.IGNORECASE)
		return q
	except Exception as e:
		print("Failed to normalize query ", e)

	return query


def record(force=False):
	flag_value = mrinimitable.client_cache.get_value(RECORDER_INTERCEPT_FLAG)
	if flag_value or force:
		mrinimitable.local._recorder = Recorder(force=force)
		return mrinimitable.local._recorder
	elif flag_value is None:
		# Explicitly set it once so next requests can use client-side cache
		mrinimitable.client_cache.set_value(RECORDER_INTERCEPT_FLAG, False)


def dump():
	if hasattr(mrinimitable.local, "_recorder"):
		mrinimitable.local._recorder.dump()


class Recorder:
	def __init__(self, force=False):
		self.config = RecorderConfig.retrieve()
		self.calls = []
		self.profiler = None
		self._recording = True
		self.force = force
		self.cmd = None
		self.method = None
		self.headers = None
		self.form_dict = None
		self.patched_databases = []

		if (
			self.config.record_requests
			and mrinimitable.request
			and self.config.request_filter in mrinimitable.request.path
		):
			self.path = mrinimitable.request.path
			self.cmd = mrinimitable.local.form_dict.cmd or ""
			self.method = mrinimitable.request.method
			self.headers = dict(mrinimitable.local.request.headers)
			self.form_dict = mrinimitable.local.form_dict
			self.event_type = "HTTP Request"
		elif self.config.record_jobs and mrinimitable.job and self.config.jobs_filter in mrinimitable.job.method:
			self.event_type = "Background Job"
			self.path = mrinimitable.job.method
			self.cmd = None
			self.method = None
			self.headers = None
			self.form_dict = None
		elif not self.force:
			self._recording = False
			return
		else:
			self.event_type = "Function Call"

		self.uuid = mrinimitable.generate_hash(length=10)
		self.time = now_datetime()

		self._patch_sql(mrinimitable.db)

		if self.config.profile:
			self.profiler = cProfile.Profile()
			self.profiler.enable()

	def register(self, data):
		self.calls.append(data)

	def cleanup(self):
		if self.profiler:
			self.profiler.disable()
		self._unpatch_sql()

	def process_profiler(self):
		if self.config.profile or self.profiler:
			self.profiler.disable()
			profiler_output = io.StringIO()
			pstats.Stats(self.profiler, stream=profiler_output).sort_stats("cumulative").print_stats(200)
			profile = profiler_output.getvalue()
			profiler_output.close()
			return profile

	def dump(self):
		if not self._recording:
			return
		profiler_output = self.process_profiler()

		request_data = {
			"uuid": self.uuid,
			"path": self.path,
			"cmd": self.cmd,
			"time": self.time,
			"queries": len(self.calls),
			"time_queries": float("{:0.3f}".format(sum(call["duration"] for call in self.calls))),
			"duration": float(f"{(now_datetime() - self.time).total_seconds() * 1000:0.3f}"),
			"method": self.method,
			"event_type": self.event_type,
		}
		mrinimitable.cache.hset(RECORDER_REQUEST_SPARSE_HASH, self.uuid, request_data)

		request_data["calls"] = self.calls
		request_data["headers"] = self.headers
		request_data["form_dict"] = self.form_dict
		request_data["profile"] = profiler_output
		mrinimitable.cache.hset(RECORDER_REQUEST_HASH, self.uuid, request_data)

		self._unpatch_sql()

	def _patch_sql(self, db: "Database"):
		if not self.config.record_sql:
			return

		mrinimitable.db._sql = mrinimitable.db.sql
		mrinimitable.db.sql = record_sql
		self.patched_databases.append(db)

	def _unpatch_sql(self):
		for db in self.patched_databases:
			db.sql = db._sql


def do_not_record(function):
	@functools.wraps(function)
	def wrapper(*args, **kwargs):
		if hasattr(mrinimitable.local, "_recorder"):
			mrinimitable.local._recorder.cleanup()
			del mrinimitable.local._recorder
		return function(*args, **kwargs)

	return wrapper


def administrator_only(function):
	@functools.wraps(function)
	def wrapper(*args, **kwargs):
		if mrinimitable.session.user != "Administrator":
			mrinimitable.throw(_("Only Administrator is allowed to use Recorder"))
		return function(*args, **kwargs)

	return wrapper


@mrinimitable.whitelist()
@do_not_record
@administrator_only
def status(*args, **kwargs):
	return bool(mrinimitable.cache.get_value(RECORDER_INTERCEPT_FLAG))


@mrinimitable.whitelist()
@do_not_record
@administrator_only
def start(
	record_jobs: bool = True,
	record_requests: bool = True,
	record_sql: bool = True,
	profile: bool = False,
	capture_stack: bool = True,
	explain: bool = True,
	request_filter: str = "/",
	jobs_filter: str = "",
	*args,
	**kwargs,
):
	RecorderConfig(
		record_requests=int(record_requests),
		record_jobs=int(record_jobs),
		record_sql=int(record_sql),
		profile=int(profile),
		capture_stack=int(capture_stack),
		explain=int(explain),
		request_filter=request_filter,
		jobs_filter=jobs_filter,
	).store()
	mrinimitable.client_cache.set_value(RECORDER_INTERCEPT_FLAG, True)
	mrinimitable.cache.expire_key(RECORDER_INTERCEPT_FLAG, RECORDER_AUTO_DISABLE)


@mrinimitable.whitelist()
@do_not_record
@administrator_only
def stop(*args, **kwargs):
	mrinimitable.client_cache.set_value(RECORDER_INTERCEPT_FLAG, False)
	mrinimitable.enqueue(post_process, now=mrinimitable.in_test)


@mrinimitable.whitelist()
@do_not_record
@administrator_only
def get(uuid=None, *args, **kwargs):
	if uuid:
		result = mrinimitable.cache.hget(RECORDER_REQUEST_HASH, uuid)
	else:
		result = list(mrinimitable.cache.hgetall(RECORDER_REQUEST_SPARSE_HASH).values())
	return result


@mrinimitable.whitelist()
@do_not_record
@administrator_only
def export_data(*args, **kwargs):
	return list(mrinimitable.cache.hgetall(RECORDER_REQUEST_HASH).values())


@mrinimitable.whitelist()
@do_not_record
@administrator_only
def delete(*args, **kwargs):
	mrinimitable.cache.delete_value(RECORDER_REQUEST_SPARSE_HASH)
	mrinimitable.cache.delete_value(RECORDER_REQUEST_HASH)


def record_queries(func: Callable):
	"""Decorator to profile a specific function using recorder."""

	@functools.wraps(func)
	def wrapped(*args, **kwargs):
		recorder = record(force=True)
		recorder.path = f"Function call: {func.__module__}.{func.__qualname__}"
		ret = func(*args, **kwargs)
		dump()
		recorder._unpatch_sql()
		post_process()
		print("Recorded queries, open recorder to view them.")
		return ret

	return wrapped


@mrinimitable.whitelist()
@do_not_record
@administrator_only
def import_data(file: str) -> None:
	file_doc = mrinimitable.get_doc("File", {"file_url": file})
	file_content = json.loads(file_doc.get_content())
	for request in file_content:
		mrinimitable.cache.hset(RECORDER_REQUEST_SPARSE_HASH, request["uuid"], request)
		mrinimitable.cache.hset(RECORDER_REQUEST_HASH, request["uuid"], request)
	file_doc.delete(delete_permanently=True)
