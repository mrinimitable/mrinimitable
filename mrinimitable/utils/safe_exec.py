import ast
import copy
import inspect
import io
import json
import mimetypes
import types
from contextlib import contextmanager
from functools import lru_cache
from itertools import chain
from types import FunctionType, MethodType, ModuleType
from typing import TYPE_CHECKING, Any

import orjson
import RestrictedPython.Guards
from RestrictedPython import PrintCollector, compile_restricted, safe_globals
from RestrictedPython.transformer import RestrictingNodeTransformer

import mrinimitable
import mrinimitable.exceptions
import mrinimitable.integrations.utils
import mrinimitable.utils
import mrinimitable.utils.data
from mrinimitable import _
from mrinimitable.core.utils import html2text
from mrinimitable.mrinimitableclient import MrinimitableClient
from mrinimitable.handler import execute_cmd
from mrinimitable.locale import get_date_format, get_number_format, get_time_format
from mrinimitable.model.delete_doc import delete_doc
from mrinimitable.model.mapper import get_mapped_doc
from mrinimitable.model.rename_doc import rename_doc
from mrinimitable.modules import scrub
from mrinimitable.utils.background_jobs import enqueue, get_jobs
from mrinimitable.utils.caching import site_cache
from mrinimitable.utils.number_format import NumberFormat
from mrinimitable.utils.response import json_handler
from mrinimitable.website.utils import get_next_link, get_toc
from mrinimitable.www.printview import get_visible_columns


class ServerScriptNotEnabled(mrinimitable.PermissionError):
	pass


ARGUMENT_NOT_SET = object()

SAFE_EXEC_CONFIG_KEY = "server_script_enabled"
SERVER_SCRIPT_FILE_PREFIX = "<serverscript>"


class NamespaceDict(mrinimitable._dict):
	"""Raise AttributeError if function not found in namespace"""

	def __getattr__(self, key):
		ret = self.get(key)
		if (not ret and key.startswith("__")) or (key not in self):

			def default_function(*args, **kwargs):
				raise AttributeError(f"module has no attribute '{key}'")

			return default_function
		return ret


class MrinimitableTransformer(RestrictingNodeTransformer):
	def check_name(self, node, name, *args, **kwargs):
		if name == "_dict":
			return

		return super().check_name(node, name, *args, **kwargs)


class MrinimitablePrintCollector(PrintCollector):
	"""Collect written text, and return it when called."""

	def _call_print(self, *objects, **kwargs):
		output = io.StringIO()
		print(*objects, file=output, **kwargs)
		mrinimitable.log(output.getvalue().strip())
		output.close()


def is_safe_exec_enabled() -> bool:
	# server scripts can only be enabled via common_site_config.json
	return bool(mrinimitable.get_common_site_config(cached=True).get(SAFE_EXEC_CONFIG_KEY))


def safe_exec(
	script: str,
	_globals: dict | None = None,
	_locals: dict | None = None,
	*,
	restrict_commit_rollback: bool = False,
	script_filename: str | None = None,
):
	if not is_safe_exec_enabled():
		msg = _("Server Scripts are disabled. Please enable server scripts from shashi configuration.")
		docs_cta = _("Read the documentation to know more")
		msg += f"<br><a href='https://mrinimitableframework.com/docs/user/en/desk/scripting/server-script'>{docs_cta}</a>"
		mrinimitable.throw(msg, ServerScriptNotEnabled, title="Server Scripts Disabled")

	# build globals
	exec_globals = get_safe_globals()
	if _globals:
		exec_globals.update(_globals)

	if restrict_commit_rollback:
		# prevent user from using these in docevents
		exec_globals.mrinimitable.db.pop("commit", None)
		exec_globals.mrinimitable.db.pop("rollback", None)
		exec_globals.mrinimitable.db.pop("add_index", None)

	filename = SERVER_SCRIPT_FILE_PREFIX
	if script_filename:
		filename += f": {mrinimitable.scrub(script_filename)}"

	with safe_exec_flags(), patched_qb():
		# execute script compiled by RestrictedPython
		exec(_compile_code(script, filename=filename), exec_globals, _locals)

	return exec_globals, _locals


@site_cache(maxsize=32)
def _compile_code(script: str, filename: str, mode: str = "exec"):
	return compile_restricted(script, filename=filename, policy=MrinimitableTransformer, mode=mode)


def safe_eval(code, eval_globals=None, eval_locals=None):
	import unicodedata

	code = unicodedata.normalize("NFKC", code)

	_validate_safe_eval_syntax(code)

	if not eval_globals:
		eval_globals = {}

	eval_globals["__builtins__"] = {}
	eval_globals.update(WHITELISTED_SAFE_EVAL_GLOBALS)

	return eval(_compile_code(code, filename="<safe_eval>", mode="eval"), eval_globals, eval_locals)


def _validate_safe_eval_syntax(code):
	BLOCKED_NODES = (ast.NamedExpr,)

	tree = ast.parse(code, mode="eval")
	for node in ast.walk(tree):
		if isinstance(node, BLOCKED_NODES):
			raise SyntaxError(f"Operation not allowed: line {node.lineno} column {node.col_offset}")


@contextmanager
def safe_exec_flags():
	if mrinimitable.flags.in_safe_exec is None:
		mrinimitable.flags.in_safe_exec = 0

	mrinimitable.flags.in_safe_exec += 1

	try:
		yield
	finally:
		# Always ensure that the flag is decremented
		mrinimitable.flags.in_safe_exec -= 1


def get_safe_globals():
	datautils = mrinimitable._dict()

	if mrinimitable.db:
		date_format = get_date_format()
		time_format = get_time_format()
		number_format = get_number_format()
	else:
		date_format = "yyyy-mm-dd"
		time_format = "HH:mm:ss"
		number_format = NumberFormat.from_string("#,###.##")

	datautils.update(SAFE_DATA_UTILS)

	form_dict = getattr(mrinimitable.local, "form_dict", mrinimitable._dict())

	if "_" in form_dict:
		del mrinimitable.local.form_dict["_"]

	user = (getattr(mrinimitable.local, "session", None) and mrinimitable.local.session.user) or "Guest"

	out = NamespaceDict(
		# make available limited methods of mrinimitable
		json=NamespaceDict(loads=json.loads, dumps=json.dumps),
		orjson=SAFE_ORJSON,
		as_json=mrinimitable.as_json,
		dict=dict,
		log=mrinimitable.log,
		_dict=mrinimitable._dict,
		args=form_dict,
		mrinimitable=NamespaceDict(
			call=call_whitelisted_function,
			flags=mrinimitable._dict(),
			format=mrinimitable.format_value,
			format_value=mrinimitable.format_value,
			date_format=date_format,
			time_format=time_format,
			number_format=number_format,
			format_date=mrinimitable.utils.data.global_date_format,
			form_dict=form_dict,
			bold=mrinimitable.bold,
			copy_doc=mrinimitable.copy_doc,
			errprint=mrinimitable.errprint,
			qb=mrinimitable.qb,
			get_meta=mrinimitable.get_meta,
			new_doc=mrinimitable.new_doc,
			get_doc=mrinimitable.get_doc,
			get_mapped_doc=get_mapped_doc,
			get_last_doc=mrinimitable.get_last_doc,
			get_cached_doc=mrinimitable.get_cached_doc,
			get_list=mrinimitable.get_list,
			get_all=mrinimitable.get_all,
			get_system_settings=mrinimitable.get_system_settings,
			rename_doc=rename_doc,
			delete_doc=delete_doc,
			utils=datautils,
			get_url=mrinimitable.utils.get_url,
			render_template=mrinimitable.render_template,
			msgprint=mrinimitable.msgprint,
			throw=mrinimitable.throw,
			sendmail=mrinimitable.sendmail,
			get_print=mrinimitable.get_print,
			attach_print=mrinimitable.attach_print,
			user=user,
			get_fullname=mrinimitable.utils.get_fullname,
			get_gravatar=mrinimitable.utils.get_gravatar_url,
			full_name=mrinimitable.local.session.data.full_name
			if getattr(mrinimitable.local, "session", None) and getattr(mrinimitable.local.session, "data", None)
			else "Guest",
			request=getattr(mrinimitable.local, "request", {}),
			session=mrinimitable._dict(
				user=user,
				csrf_token=mrinimitable.local.session.data.csrf_token
				if getattr(mrinimitable.local, "session", None) and getattr(mrinimitable.local.session, "data", None)
				else "",
			),
			make_get_request=mrinimitable.integrations.utils.make_get_request,
			make_post_request=mrinimitable.integrations.utils.make_post_request,
			make_put_request=mrinimitable.integrations.utils.make_put_request,
			make_patch_request=mrinimitable.integrations.utils.make_patch_request,
			make_delete_request=mrinimitable.integrations.utils.make_delete_request,
			socketio_port=mrinimitable.conf.socketio_port,
			get_hooks=get_hooks,
			enqueue=safe_enqueue,
			sanitize_html=mrinimitable.utils.sanitize_html,
			log_error=mrinimitable.log_error,
			log=mrinimitable.log,
			db=NamespaceDict(
				get_list=mrinimitable.get_list,
				get_all=mrinimitable.get_all,
				get_value=mrinimitable.db.get_value,
				set_value=mrinimitable.db.set_value,
				get_single_value=mrinimitable.db.get_single_value,
				get_default=mrinimitable.db.get_default,
				exists=mrinimitable.db.exists,
				count=mrinimitable.db.count,
				escape=mrinimitable.db.escape,
				sql=read_sql,
				commit=mrinimitable.db.commit,
				rollback=mrinimitable.db.rollback,
				after_commit=mrinimitable.db.after_commit,
				before_commit=mrinimitable.db.before_commit,
				after_rollback=mrinimitable.db.after_rollback,
				before_rollback=mrinimitable.db.before_rollback,
				add_index=mrinimitable.db.add_index,
			),
			website=NamespaceDict(
				abs_url=mrinimitable.website.utils.abs_url,
				extract_title=mrinimitable.website.utils.extract_title,
				get_boot_data=mrinimitable.website.utils.get_boot_data,
				get_home_page=mrinimitable.website.utils.get_home_page,
				get_html_content_based_on_type=mrinimitable.website.utils.get_html_content_based_on_type,
			),
			lang=getattr(mrinimitable.local, "lang", "en"),
			json_handler=json_handler,
		),
		MrinimitableClient=MrinimitableClient,
		style=mrinimitable._dict(border_color="#d1d8dd"),
		get_toc=get_toc,
		get_next_link=get_next_link,
		_=mrinimitable._,
		scrub=scrub,
		guess_mimetype=mimetypes.guess_type,
		html2text=html2text,
		dev_server=mrinimitable._dev_server,
		run_script=run_script,
		is_job_queued=is_job_queued,
		get_visible_columns=get_visible_columns,
	)

	out.mrinimitable.update(SAFE_EXCEPTIONS)

	if mrinimitable.response:
		out.mrinimitable.response = mrinimitable.response

	out.update(safe_globals)

	# default writer allows write access
	out._write_ = _write
	out._getitem_ = _getitem
	out._getattr_ = _getattr_for_safe_exec

	# Allow using `print()` calls with `safe_exec()`
	out._print_ = MrinimitablePrintCollector

	# allow iterators and list comprehension
	out._getiter_ = iter
	out._iter_unpack_sequence_ = RestrictedPython.Guards.guarded_iter_unpack_sequence

	# add common python builtins
	out.update(get_python_builtins())

	return out


def get_keys_for_autocomplete(
	key: str,
	value: Any,
	prefix: str = "",
	offset: int = 0,
	meta: str = "ctx",
	depth: int = 0,
	max_depth: int | None = None,
):
	if max_depth and depth > max_depth:
		return
	full_key = f"{prefix}.{key}" if prefix else key
	if key.startswith("_"):
		return
	if isinstance(value, NamespaceDict | dict) and value:
		if key == "form_dict":
			yield {"value": full_key, "score": offset + 7, "meta": meta}
		else:
			yield from chain.from_iterable(
				get_keys_for_autocomplete(
					key,
					value,
					full_key,
					offset,
					meta,
					depth + 1,
					max_depth=max_depth,
				)
				for key, value in value.items()
			)
	else:
		if isinstance(value, type) and issubclass(value, Exception):
			score = offset + 0
		elif isinstance(value, ModuleType):
			score = offset + 10
		elif isinstance(value, FunctionType | MethodType):
			score = offset + 9
		elif isinstance(value, type):
			score = offset + 8
		elif isinstance(value, dict):
			score = offset + 7
		else:
			score = offset + 6
		yield {"value": full_key, "score": score, "meta": meta}


def is_job_queued(job_name, queue="default"):
	"""
	:param job_name: used to identify a queued job, usually dotted path to function
	:param queue: should be either long, default or short
	"""

	site = mrinimitable.local.site
	queued_jobs = get_jobs(site=site, queue=queue, key="job_name").get(site)
	return queued_jobs and job_name in queued_jobs


def safe_enqueue(function, **kwargs):
	"""
	Enqueue function to be executed using a background worker
	Accepts mrinimitable.enqueue params like job_name, queue, timeout, etc.
	in addition to params to be passed to function

	:param function: whitelisted function or API Method set in Server Script
	"""

	return enqueue("mrinimitable.utils.safe_exec.call_whitelisted_function", function=function, **kwargs)


def call_whitelisted_function(function, **kwargs):
	"""Executes a whitelisted function or Server Script of type API"""

	return call_with_form_dict(lambda: execute_cmd(function), kwargs)


def run_script(script, **kwargs):
	"""run another server script"""

	return call_with_form_dict(lambda: mrinimitable.get_doc("Server Script", script).execute_method(), kwargs)


def call_with_form_dict(function, kwargs):
	# temporarily update form_dict, to use inside below call
	form_dict = getattr(mrinimitable.local, "form_dict", mrinimitable._dict())
	if kwargs:
		mrinimitable.local.form_dict = form_dict.copy().update(kwargs)

	try:
		return function()
	finally:
		mrinimitable.local.form_dict = form_dict


@contextmanager
def patched_qb():
	require_patching = isinstance(mrinimitable.qb.terms, types.ModuleType)
	try:
		if require_patching:
			_terms = mrinimitable.qb.terms
			mrinimitable.qb.terms = _flatten(mrinimitable.qb.terms)
		yield
	finally:
		if require_patching:
			mrinimitable.qb.terms = _terms


@lru_cache
def _flatten(module):
	new_mod = NamespaceDict()
	for name, obj in inspect.getmembers(module, lambda x: not inspect.ismodule(x)):
		if not name.startswith("_"):
			new_mod[name] = obj
	return new_mod


def get_python_builtins():
	return {
		"abs": abs,
		"all": all,
		"any": any,
		"bool": bool,
		"dict": dict,
		"enumerate": enumerate,
		"isinstance": isinstance,
		"issubclass": issubclass,
		"list": list,
		"max": max,
		"min": min,
		"range": range,
		"set": set,
		"sorted": sorted,
		"sum": sum,
		"tuple": tuple,
	}


def get_hooks(hook: str | None = None, default=None, app_name: str | None = None) -> mrinimitable._dict:
	"""Get hooks via `app/hooks.py`

	:param hook: Name of the hook. Will gather all hooks for this name and return as a list.
	:param default: Default if no hook found.
	:param app_name: Filter by app."""

	hooks = mrinimitable.get_hooks(hook=hook, default=default, app_name=app_name)
	return copy.deepcopy(hooks)


def read_sql(query, *args, **kwargs):
	"""a wrapper for mrinimitable.db.sql to allow reads"""
	query = str(query)
	check_safe_sql_query(query)
	return mrinimitable.db.sql(query, *args, **kwargs)


def check_safe_sql_query(query: str, throw: bool = True) -> bool:
	"""Check if SQL query is safe for running in restricted context.

	Safe queries:
	        1. Read only 'select' or 'explain' queries
	        2. CTE on mariadb where writes are not allowed.
	"""

	query = query.strip().lower()
	whitelisted_statements = ("select", "explain")

	if query.startswith(whitelisted_statements) or (
		query.startswith("with") and mrinimitable.db.db_type == "mariadb"
	):
		return True

	if throw:
		mrinimitable.throw(
			_("Query must be of SELECT or read-only WITH type."),
			title=_("Unsafe SQL query"),
			exc=mrinimitable.PermissionError,
		)

	return False


def _getitem(obj, key):
	# guard function for RestrictedPython
	# allow any key to be accessed as long as it does not start with underscore
	if isinstance(key, str) and key.startswith("_"):
		raise SyntaxError("Key starts with _")
	return obj[key]


UNSAFE_ATTRIBUTES = {
	# Generator Attributes
	"gi_frame",
	"gi_code",
	"gi_yieldfrom",
	# Coroutine Attributes
	"cr_frame",
	"cr_code",
	"cr_origin",
	"cr_await",
	# Async Generator Attributes
	"ag_code",
	"ag_frame",
	# Traceback Attributes
	"tb_frame",
	"tb_next",
	# Format Attributes
	"format",
	"format_map",
	# Frame attributes
	"f_back",
	"f_builtins",
	"f_code",
	"f_globals",
	"f_locals",
	"f_trace",
}


def _getattr_for_safe_exec(object, name, default=None):
	# guard function for RestrictedPython
	# allow any key to be accessed as long as
	# 1. it does not start with an underscore (safer_getattr)
	# 2. it is not an UNSAFE_ATTRIBUTES
	_validate_attribute_read(object, name)

	return RestrictedPython.Guards.safer_getattr(object, name, default=default)


def _get_attr_for_eval(object, name, default=ARGUMENT_NOT_SET):
	_validate_attribute_read(object, name)

	# Use vanilla getattr to raise correct attribute error. Safe exec has been supressing attribute
	# error which is bad for DX/UX in general.
	return getattr(object, name) if default is ARGUMENT_NOT_SET else getattr(object, name, default)


def _validate_attribute_read(object, name):
	if isinstance(name, str) and (name in UNSAFE_ATTRIBUTES):
		raise SyntaxError(f"{name} is an unsafe attribute")

	if isinstance(object, types.ModuleType | types.CodeType | types.TracebackType | types.FrameType):
		raise SyntaxError(f"Reading {object} attributes is not allowed")

	if name.startswith("_"):
		raise AttributeError(f'"{name}" is an invalid attribute name because it starts with "_"')


def _write(obj):
	# guard function for RestrictedPython
	if isinstance(
		obj,
		types.ModuleType
		| types.CodeType
		| types.TracebackType
		| types.FrameType
		| type
		| types.FunctionType
		| types.MethodType
		| types.BuiltinFunctionType,
	):
		raise SyntaxError(f"Not allowed to write to object {obj} of type {type(obj)}")
	return obj


def get_module_properties(module, filter_method):
	data = {}
	for key, obj in module.__dict__.items():
		if key.startswith("_"):
			# ignore
			continue

		if filter_method(obj):
			# only allow functions
			data[key] = obj
	return data


VALID_UTILS = (
	"DATE_FORMAT",
	"TIME_FORMAT",
	"DATETIME_FORMAT",
	"is_invalid_date_string",
	"getdate",
	"get_datetime",
	"to_timedelta",
	"get_timedelta",
	"add_to_date",
	"add_days",
	"add_months",
	"add_years",
	"date_diff",
	"month_diff",
	"time_diff",
	"time_diff_in_seconds",
	"time_diff_in_hours",
	"now_datetime",
	"get_timestamp",
	"get_eta",
	"get_system_timezone",
	"convert_utc_to_system_timezone",
	"now",
	"nowdate",
	"today",
	"nowtime",
	"get_first_day",
	"get_quarter_start",
	"get_quarter_ending",
	"get_first_day_of_week",
	"get_year_start",
	"get_year_ending",
	"get_last_day_of_week",
	"get_last_day",
	"get_time",
	"get_datetime_in_timezone",
	"get_datetime_str",
	"get_date_str",
	"get_time_str",
	"get_user_date_format",
	"get_user_time_format",
	"format_date",
	"format_time",
	"format_datetime",
	"format_duration",
	"get_weekdays",
	"get_weekday",
	"get_timespan_date_range",
	"global_date_format",
	"has_common",
	"flt",
	"cint",
	"floor",
	"ceil",
	"cstr",
	"rounded",
	"remainder",
	"safe_div",
	"round_based_on_smallest_currency_fraction",
	"encode",
	"parse_val",
	"fmt_money",
	"get_number_format_info",
	"money_in_words",
	"in_words",
	"is_html",
	"is_image",
	"get_thumbnail_base64_for_image",
	"image_to_base64",
	"pdf_to_base64",
	"strip_html",
	"escape_html",
	"pretty_date",
	"comma_or",
	"comma_and",
	"comma_sep",
	"new_line_sep",
	"filter_strip_join",
	"add_trackers_to_url",
	"parse_and_map_trackers_from_url",
	"map_trackers",
	"get_url",
	"get_host_name_from_request",
	"url_contains_port",
	"get_host_name",
	"get_link_to_form",
	"get_link_to_report",
	"get_absolute_url",
	"get_url_to_form",
	"get_url_to_list",
	"get_url_to_report",
	"get_url_to_report_with_filters",
	"evaluate_filters",
	"compare",
	"get_filter",
	"make_filter_tuple",
	"make_filter_dict",
	"sanitize_column",
	"scrub_urls",
	"expand_relative_urls",
	"quoted",
	"quote_urls",
	"unique",
	"strip",
	"to_markdown",
	"md_to_html",
	"markdown",
	"is_subset",
	"generate_hash",
	"formatdate",
	"get_user_info_for_avatar",
	"get_abbr",
	"get_month",
	"sha256_hash",
	"parse_json",
	"orjson_dumps",
)


SAFE_DATA_UTILS = {key: mrinimitable.utils.data.__dict__[key] for key in VALID_UTILS}


WHITELISTED_SAFE_EVAL_GLOBALS = {
	"int": int,
	"float": float,
	"long": int,
	"round": round,
	# RestrictedPython specific overrides
	"_getattr_": _get_attr_for_eval,
	"_getitem_": _getitem,
	"_getiter_": iter,
	"_iter_unpack_sequence_": RestrictedPython.Guards.guarded_iter_unpack_sequence,
}

SAFE_ORJSON = NamespaceDict(loads=orjson.loads, dumps=orjson.dumps)
for key, val in vars(orjson).items():
	if key.startswith("OPT_"):
		SAFE_ORJSON[key] = val

SAFE_EXCEPTIONS = get_module_properties(
	mrinimitable.exceptions, lambda obj: inspect.isclass(obj) and issubclass(obj, Exception)
)
