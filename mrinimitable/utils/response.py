# Copyright (c) 2022, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime
import functools
import mimetypes
import os
import sys
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from re import Match
from typing import TYPE_CHECKING
from urllib.parse import quote
from uuid import UUID

import orjson
import werkzeug.utils
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.local import LocalProxy
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file

import mrinimitable
import mrinimitable.model.document
import mrinimitable.sessions
import mrinimitable.utils
from mrinimitable import _
from mrinimitable.core.doctype.access_log.access_log import make_access_log
from mrinimitable.utils import format_timedelta, orjson_dumps

if TYPE_CHECKING:
	from mrinimitable.core.doctype.file.file import File

DateOrTimeTypes = datetime.date | datetime.datetime | datetime.time
timedelta = datetime.timedelta


def report_error(status_code):
	"""Build error. Show traceback in developer mode"""
	from mrinimitable.api import ApiVersion, get_api_version

	allow_traceback = is_traceback_allowed() and (status_code != 404 or mrinimitable.conf.logging)

	traceback = mrinimitable.utils.get_traceback()
	exc_type, exc_value, _ = sys.exc_info()

	match get_api_version():
		case ApiVersion.V1:
			if allow_traceback:
				mrinimitable.errprint(traceback)
				mrinimitable.response.exception = traceback.splitlines()[-1]
			mrinimitable.response["exc_type"] = exc_type.__name__
		case ApiVersion.V2:
			error_log = {"type": exc_type.__name__}
			if allow_traceback:
				print(traceback)
				error_log["exception"] = traceback
			_link_error_with_message_log(error_log, exc_value, mrinimitable.message_log)
			mrinimitable.local.response.errors = [error_log]

	response = build_response("json")
	response.status_code = status_code

	return response


def is_traceback_allowed():
	from mrinimitable.permissions import is_system_user

	return (
		mrinimitable.db
		and mrinimitable.get_system_settings("allow_error_traceback")
		and (not mrinimitable.local.flags.disable_traceback or mrinimitable._dev_server)
		and is_system_user()
	)


def _link_error_with_message_log(error_log, exception, message_logs):
	for message in list(message_logs):
		if message.get("__mrinimitable_exc_id") == getattr(exception, "__mrinimitable_exc_id", None):
			error_log.update(message)
			message_logs.remove(message)
			error_log.pop("raise_exception", None)
			error_log.pop("__mrinimitable_exc_id", None)
			return


def build_response(response_type=None):
	if "docs" in mrinimitable.local.response and not mrinimitable.local.response.docs:
		del mrinimitable.local.response["docs"]

	response_type_map = {
		"csv": as_csv,
		"txt": as_txt,
		"download": as_raw,
		"json": as_json,
		"pdf": as_pdf,
		"page": as_page,
		"redirect": redirect,
		"binary": as_binary,
	}

	return response_type_map[mrinimitable.response.get("type") or response_type]()


def as_csv():
	response = Response()
	response.mimetype = "text/csv"
	filename = f"{mrinimitable.response['doctype']}.csv"
	filename = filename.encode("utf-8").decode("unicode-escape", "ignore")
	response.headers.add("Content-Disposition", "attachment", filename=filename)
	response.data = mrinimitable.response["result"]
	return response


def as_txt():
	response = Response()
	response.mimetype = "text"
	filename = f"{mrinimitable.response['doctype']}.txt"
	filename = filename.encode("utf-8").decode("unicode-escape", "ignore")
	response.headers.add("Content-Disposition", "attachment", filename=filename)
	response.data = mrinimitable.response["result"]
	return response


def as_raw():
	response = Response()
	response.mimetype = (
		mrinimitable.response.get("content_type")
		or mimetypes.guess_type(mrinimitable.response["filename"])[0]
		or "application/unknown"
	)
	filename = mrinimitable.response["filename"].encode("utf-8").decode("unicode-escape", "ignore")
	response.headers.add(
		"Content-Disposition",
		mrinimitable.response.get("display_content_as", "attachment"),
		filename=filename,
	)
	response.data = mrinimitable.response["filecontent"]
	return response


def as_json():
	make_logs()

	response = Response()
	if mrinimitable.local.response.http_status_code:
		response.status_code = mrinimitable.local.response["http_status_code"]
		del mrinimitable.local.response["http_status_code"]

	response.mimetype = "application/json"
	response.data = orjson_dumps(mrinimitable.local.response, default=json_handler)
	return response


def as_pdf():
	response = Response()
	response.mimetype = "application/pdf"
	filename = mrinimitable.response["filename"].encode("utf-8").decode("unicode-escape", "ignore")
	response.headers.add("Content-Disposition", None, filename=filename)
	response.data = mrinimitable.response["filecontent"]
	return response


def as_binary():
	response = Response()
	response.mimetype = "application/octet-stream"
	filename = mrinimitable.response["filename"]
	filename = filename.encode("utf-8").decode("unicode-escape", "ignore")
	response.headers.add("Content-Disposition", None, filename=filename)
	response.data = mrinimitable.response["filecontent"]
	return response


def make_logs():
	"""make strings for msgprint and errprint"""

	from mrinimitable.api import ApiVersion, get_api_version

	match get_api_version():
		case ApiVersion.V1:
			_make_logs_v1()
		case ApiVersion.V2:
			_make_logs_v2()


def _make_logs_v1():
	from mrinimitable.utils.error import guess_exception_source

	response = mrinimitable.local.response

	if mrinimitable.error_log and is_traceback_allowed():
		if source := guess_exception_source(mrinimitable.local.error_log and mrinimitable.local.error_log[0]["exc"]):
			response["_exc_source"] = source
		response["exc"] = orjson.dumps([mrinimitable.utils.cstr(d["exc"]) for d in mrinimitable.local.error_log]).decode()

	if mrinimitable.local.message_log:
		response["_server_messages"] = orjson.dumps(
			[orjson.dumps(d).decode() for d in mrinimitable.local.message_log]
		).decode()

	if mrinimitable.debug_log:
		response["_debug_messages"] = orjson.dumps(mrinimitable.local.debug_log).decode()

	if mrinimitable.flags.error_message:
		response["_error_message"] = mrinimitable.flags.error_message


def _make_logs_v2():
	response = mrinimitable.local.response

	if mrinimitable.local.message_log:
		response["messages"] = mrinimitable.local.message_log

	if mrinimitable.debug_log:
		response["debug"] = [{"message": m} for m in mrinimitable.local.debug_log]


def json_handler(obj):
	"""serialize non-serializable data for json"""

	if isinstance(obj, DateOrTimeTypes):
		return str(obj)

	elif isinstance(obj, timedelta):
		return format_timedelta(obj)

	elif isinstance(obj, LocalProxy):
		return str(obj)

	elif hasattr(obj, "__json__"):
		return obj.__json__()

	elif isinstance(obj, Iterable):
		return list(obj)

	elif isinstance(obj, Decimal):
		return float(obj)

	elif isinstance(obj, Match):
		return obj.string

	elif type(obj) is type or isinstance(obj, Exception):
		return repr(obj)

	elif callable(obj):
		return repr(obj)

	elif isinstance(obj, Path):
		return str(obj)

	# orjson does this already
	# but json_handler needs to be compatible with built-in json module also
	elif isinstance(obj, UUID):
		return str(obj)

	else:
		raise TypeError(f"""Object of type {type(obj)} with value of {obj!r} is not JSON serializable""")


def as_page():
	"""print web page"""
	from mrinimitable.website.serve import get_response

	return get_response(mrinimitable.response["route"], http_status_code=mrinimitable.response.get("http_status_code"))


def redirect():
	return werkzeug.utils.redirect(mrinimitable.response.location)


def download_backup(path):
	try:
		mrinimitable.only_for(("System Manager", "Administrator"))
		make_access_log(report_name="Backup")
	except mrinimitable.PermissionError:
		raise Forbidden(
			_("You need to be logged in and have System Manager Role to be able to access backups.")
		)

	return send_private_file(path)


def download_private_file(path: str) -> Response:
	"""Checks permissions and sends back private file"""
	from mrinimitable.core.doctype.file.utils import find_file_by_url

	if mrinimitable.session.user == "Guest":
		raise Forbidden(_("You don't have permission to access this file"))

	file = find_file_by_url(path, name=mrinimitable.form_dict.fid)
	if not file:
		raise Forbidden(_("You don't have permission to access this file"))

	make_access_log(doctype="File", document=file.name, file_type=os.path.splitext(path)[-1][1:])
	return send_private_file(path.split("/private", 1)[1])


def send_private_file(path: str) -> Response:
	path = os.path.join(mrinimitable.local.conf.get("private_path", "private"), path.strip("/"))
	filename = os.path.basename(path)

	if mrinimitable.local.request.headers.get("X-Use-X-Accel-Redirect"):
		path = "/protected/" + path
		response = Response()
		response.headers["X-Accel-Redirect"] = quote(mrinimitable.utils.encode(path))
		response.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=86400"

	else:
		filepath = mrinimitable.utils.get_site_path(path)
		try:
			f = open(filepath, "rb")
		except OSError:
			raise NotFound

		response = Response(wrap_file(mrinimitable.local.request.environ, f), direct_passthrough=True)

	# no need for content disposition and force download. let browser handle its opening.
	# Except for those that can be injected with scripts.

	extension = os.path.splitext(path)[1]
	blacklist = [".svg", ".html", ".htm", ".xml"]

	if extension.lower() in blacklist:
		response.headers.add("Content-Disposition", "attachment", filename=filename)

	response.mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"

	return response


def handle_session_stopped():
	from mrinimitable.website.serve import get_response

	mrinimitable.respond_as_web_page(
		_("Updating"),
		_("The system is being updated. Please refresh again after a few moments."),
		http_status_code=503,
		indicator_color="orange",
		fullpage=True,
		primary_action=None,
	)
	return get_response("message", http_status_code=503)
