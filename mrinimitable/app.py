# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import functools
import logging
import os

import orjson
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.middleware.profiler import ProfilerMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import ClosingIterator

import mrinimitable
import mrinimitable.api
import mrinimitable.handler
import mrinimitable.monitor
import mrinimitable.rate_limiter
import mrinimitable.recorder
import mrinimitable.utils.response
from mrinimitable import _
from mrinimitable.auth import SAFE_HTTP_METHODS, UNSAFE_HTTP_METHODS, HTTPRequest, check_request_ip, validate_auth
from mrinimitable.integrations.oauth2 import get_resource_url, handle_wellknown, is_oauth_metadata_enabled
from mrinimitable.middlewares import StaticDataMiddleware
from mrinimitable.permissions import handle_does_not_exist_error
from mrinimitable.utils import CallbackManager, cint, get_site_name
from mrinimitable.utils.data import escape_html
from mrinimitable.utils.error import log_error, log_error_snapshot
from mrinimitable.website.page_renderers.error_page import ErrorPage
from mrinimitable.website.serve import get_response

_site = None
_sites_path = os.environ.get("SITES_PATH", ".")


# If gc.freeze is done then importing modules before forking allows us to share the memory
import gettext

import babel
import babel.messages
import bleach
import num2words
import pydantic

import mrinimitable.boot
import mrinimitable.client
import mrinimitable.core.doctype.file.file
import mrinimitable.core.doctype.user.user
import mrinimitable.database.mariadb.database  # Load database related utils
import mrinimitable.database.query
import mrinimitable.desk.desktop  # workspace
import mrinimitable.desk.form.save
import mrinimitable.model.db_query
import mrinimitable.query_builder
import mrinimitable.utils.background_jobs  # Enqueue is very common
import mrinimitable.utils.data  # common utils
import mrinimitable.utils.jinja  # web page rendering
import mrinimitable.utils.jinja_globals
import mrinimitable.utils.redis_wrapper  # Exact redis_wrapper
import mrinimitable.utils.safe_exec
import mrinimitable.utils.typing_validations  # any whitelisted method uses this
import mrinimitable.website.path_resolver  # all the page types and resolver
import mrinimitable.website.router  # Website router
import mrinimitable.website.website_generator  # web page doctypes

# end: module pre-loading

# better werkzeug default
# this is necessary because mrinimitable desk sends most requests as form data
# and some of them can exceed werkzeug's default limit of 500kb
Request.max_form_memory_size = None


def after_response_wrapper(app):
	"""Wrap a WSGI application to call after_response hooks after we have responded.

	This is done to reduce response time by deferring expensive tasks."""

	@functools.wraps(app)
	def application(environ, start_response):
		return ClosingIterator(
			app(environ, start_response),
			(
				mrinimitable.rate_limiter.update,
				mrinimitable.recorder.dump,
				mrinimitable.request.after_response.run,
				mrinimitable.destroy,
			),
		)

	return application


@after_response_wrapper
@Request.application
def application(request: Request):
	response = None

	try:
		init_request(request)

		validate_auth()

		if request.method == "OPTIONS":
			response = Response()

		elif mrinimitable.form_dict.cmd:
			from mrinimitable.deprecation_dumpster import deprecation_warning

			deprecation_warning(
				"unknown",
				"v17",
				f"{mrinimitable.form_dict.cmd}: Sending `cmd` for RPC calls is deprecated, call REST API instead `/api/method/cmd`",
			)
			mrinimitable.handler.handle()
			response = mrinimitable.utils.response.build_response("json")

		elif request.path.startswith("/api/"):
			response = mrinimitable.api.handle(request)

		elif request.path.startswith("/backups"):
			response = mrinimitable.utils.response.download_backup(request.path)

		elif request.path.startswith("/private/files/"):
			response = mrinimitable.utils.response.download_private_file(request.path)

		elif request.path.startswith("/.well-known/") and request.method == "GET":
			response = handle_wellknown(request.path)

		elif request.method in ("GET", "HEAD", "POST"):
			response = get_response()

		else:
			raise NotFound

	except Exception as e:
		response = e.get_response(request.environ) if isinstance(e, HTTPException) else handle_exception(e)
		if db := getattr(mrinimitable.local, "db", None):
			db.rollback(chain=True)

	else:
		sync_database()

	finally:
		# Important note:
		# this function *must* always return a response, hence any exception thrown outside of
		# try..catch block like this finally block needs to be handled appropriately.

		try:
			run_after_request_hooks(request, response)
		except Exception:
			# We can not handle exceptions safely here.
			mrinimitable.logger().error("Failed to run after request hook", exc_info=True)

	log_request(request, response)
	process_response(response)

	return response


def run_after_request_hooks(request, response):
	if not getattr(mrinimitable.local, "initialised", False):
		return

	for after_request_task in mrinimitable.get_hooks("after_request"):
		mrinimitable.call(after_request_task, response=response, request=request)


def init_request(request):
	mrinimitable.local.request = request
	mrinimitable.local.request.after_response = CallbackManager()

	mrinimitable.local.is_ajax = mrinimitable.get_request_header("X-Requested-With") == "XMLHttpRequest"

	site = _site or request.headers.get("X-Mrinimitable-Site-Name") or get_site_name(request.host)
	mrinimitable.init(site, sites_path=_sites_path, force=True)

	if not (mrinimitable.local.conf and mrinimitable.local.conf.db_name):
		# site does not exist
		raise NotFound

	mrinimitable.connect(set_admin_as_user=False)
	if mrinimitable.local.conf.maintenance_mode:
		if mrinimitable.local.conf.allow_reads_during_maintenance:
			setup_read_only_mode()
		else:
			raise mrinimitable.SessionStopped("Session Stopped")

	if request.path.startswith("/api/method/upload_file"):
		from mrinimitable.core.api.file import get_max_file_size

		request.max_content_length = get_max_file_size()
	else:
		request.max_content_length = cint(mrinimitable.local.conf.get("max_file_size")) or 25 * 1024 * 1024
	make_form_dict(request)

	if request.method != "OPTIONS":
		mrinimitable.local.http_request = HTTPRequest()

	for before_request_task in mrinimitable.get_hooks("before_request"):
		mrinimitable.call(before_request_task)


def setup_read_only_mode():
	"""During maintenance_mode reads to DB can still be performed to reduce downtime. This
	function sets up read only mode

	- Setting global flag so other pages, desk and database can know that we are in read only mode.
	- Setup read only database access either by:
	    - Connecting to read replica if one exists
	    - Or setting up read only SQL transactions.
	"""
	mrinimitable.flags.read_only = True

	# If replica is available then just connect replica, else setup read only transaction.
	if mrinimitable.conf.read_from_replica:
		mrinimitable.connect_replica()
	else:
		mrinimitable.db.begin(read_only=True)


def log_request(request, response):
	if hasattr(mrinimitable.local, "conf") and mrinimitable.local.conf.enable_mrinimitable_logger:
		mrinimitable.logger("mrinimitable.web", allow_site=mrinimitable.local.site).info(
			{
				"site": get_site_name(request.host),
				"remote_addr": getattr(request, "remote_addr", "NOTFOUND"),
				"pid": os.getpid(),
				"user": getattr(mrinimitable.local.session, "user", "NOTFOUND"),
				"base_url": getattr(request, "base_url", "NOTFOUND"),
				"full_path": getattr(request, "full_path", "NOTFOUND"),
				"method": getattr(request, "method", "NOTFOUND"),
				"scheme": getattr(request, "scheme", "NOTFOUND"),
				"http_status_code": getattr(response, "status_code", "NOTFOUND"),
			}
		)


NO_CACHE_HEADERS = {"Cache-Control": "no-store,no-cache,must-revalidate,max-age=0"}


def process_response(response: Response):
	if not response:
		return

	# Default for all requests is no-cache unless explicitly opted-in by endpoint
	response.headers.setdefault("Cache-Control", NO_CACHE_HEADERS["Cache-Control"])

	# rate limiter headers
	if hasattr(mrinimitable.local, "rate_limiter"):
		response.headers.update(mrinimitable.local.rate_limiter.headers())

	if trace_id := mrinimitable.monitor.get_trace_id():
		response.headers.update({"X-Mrinimitable-Request-Id": trace_id})

	# CORS headers
	if hasattr(mrinimitable.local, "conf"):
		set_cors_headers(response)

	if response.status_code in (401, 403) and is_oauth_metadata_enabled("resource"):
		set_authenticate_headers(response)

	# Update custom headers added during request processing
	response.headers.update(mrinimitable.local.response_headers)

	# Set cookies, only if response is non-cacheable to avoid proxy cache invalidation
	public_cache = any("public" in h for h in response.headers.getlist("Cache-Control"))
	if hasattr(mrinimitable.local, "cookie_manager") and not public_cache:
		mrinimitable.local.cookie_manager.flush_cookies(response=response)

	if mrinimitable._dev_server:
		response.headers.update(NO_CACHE_HEADERS)


def set_cors_headers(response):
	allowed_origins = mrinimitable.conf.allow_cors
	if hasattr(mrinimitable.local, "allow_cors"):
		allowed_origins = mrinimitable.local.allow_cors

	if not (
		allowed_origins and (request := mrinimitable.local.request) and (origin := request.headers.get("Origin"))
	):
		return

	if allowed_origins != "*":
		if not isinstance(allowed_origins, list):
			allowed_origins = [allowed_origins]

		if origin not in allowed_origins:
			return

	cors_headers = {
		"Access-Control-Allow-Credentials": "true",
		"Access-Control-Allow-Origin": origin,
		"Vary": "Origin",
	}

	# only required for preflight requests
	if request.method == "OPTIONS":
		cors_headers["Access-Control-Allow-Methods"] = request.headers.get("Access-Control-Request-Method")

		if allowed_headers := request.headers.get("Access-Control-Request-Headers"):
			cors_headers["Access-Control-Allow-Headers"] = allowed_headers

		# allow browsers to cache preflight requests for upto a day
		if not mrinimitable.conf.developer_mode:
			cors_headers["Access-Control-Max-Age"] = "86400"

	response.headers.update(cors_headers)


def set_authenticate_headers(response: Response):
	headers = {
		"WWW-Authenticate": f'Bearer resource_metadata="{get_resource_url()}/.well-known/oauth-protected-resource"'
	}
	response.headers.update(headers)


def make_form_dict(request: Request):
	request_data = request.get_data(as_text=True)
	if request_data and request.is_json:
		args = orjson.loads(request_data)
	else:
		args = {}
		args.update(request.args or {})
		args.update(request.form or {})

	if isinstance(args, dict):
		mrinimitable.local.form_dict = mrinimitable._dict(args)
		# _ is passed by $.ajax so that the request is not cached by the browser. So, remove _ from form_dict
		mrinimitable.local.form_dict.pop("_", None)
	elif isinstance(args, list):
		mrinimitable.local.form_dict["data"] = args
	else:
		mrinimitable.throw(_("Invalid request arguments"))


@handle_does_not_exist_error
def handle_exception(e):
	response = None
	http_status_code = getattr(e, "http_status_code", 500)
	accept_header = mrinimitable.get_request_header("Accept") or ""
	respond_as_json = (
		mrinimitable.get_request_header("Accept") and (mrinimitable.local.is_ajax or "application/json" in accept_header)
	) or (mrinimitable.local.request.path.startswith("/api/") and not accept_header.startswith("text"))

	if not mrinimitable.session.user:
		# If session creation fails then user won't be unset. This causes a lot of code that
		# assumes presence of this to fail. Session creation fails => guest or expired login
		# usually.
		mrinimitable.session.user = "Guest"

	if respond_as_json:
		# handle ajax responses first
		# if the request is ajax, send back the trace or error message
		response = mrinimitable.utils.response.report_error(http_status_code)

	elif isinstance(e, mrinimitable.SessionStopped):
		response = mrinimitable.utils.response.handle_session_stopped()

	elif (
		http_status_code == 500
		and (mrinimitable.db and isinstance(e, mrinimitable.db.InternalError))
		and (mrinimitable.db and (mrinimitable.db.is_deadlocked(e) or mrinimitable.db.is_timedout(e)))
	):
		http_status_code = 508

	elif http_status_code == 401:
		response = ErrorPage(
			http_status_code=http_status_code,
			title=_("Session Expired"),
			message=_("Your session has expired, please login again to continue."),
		).render()

	elif http_status_code == 403:
		response = ErrorPage(
			http_status_code=http_status_code,
			title=_("Not Permitted"),
			message=_("You do not have enough permissions to complete the action"),
		).render()

	elif http_status_code == 404:
		response = ErrorPage(
			http_status_code=http_status_code,
			title=_("Not Found"),
			message=_("The resource you are looking for is not available"),
		).render()

	elif http_status_code == 429:
		response = mrinimitable.rate_limiter.respond()

	else:
		response = ErrorPage(
			http_status_code=http_status_code, title=_("Server Error"), message=_("Uncaught Exception")
		).render()

	if e.__class__ == mrinimitable.AuthenticationError:
		if hasattr(mrinimitable.local, "login_manager"):
			mrinimitable.local.login_manager.clear_cookies()

	if http_status_code >= 500 or mrinimitable.conf.developer_mode:
		log_error_snapshot(e)

	if mrinimitable.conf.get("developer_mode") and not respond_as_json:
		# don't fail silently for non-json response errors
		print(mrinimitable.get_traceback())

	return response


def sync_database():
	db = getattr(mrinimitable.local, "db", None)
	if not db:
		# db isn't initialized, can't commit or rollback
		return

	# if HTTP method would change server state, commit if necessary
	if mrinimitable.local.request.method in UNSAFE_HTTP_METHODS or mrinimitable.local.flags.commit:
		db.commit(chain=True)
	else:
		db.rollback(chain=True)

	# update session
	if session := getattr(mrinimitable.local, "session_obj", None):
		mrinimitable.request.after_response.add(session.update)


# Always initialize sentry SDK if the DSN is sent
if sentry_dsn := os.getenv("MRINIMITABLE_SENTRY_DSN"):
	import sentry_sdk
	from sentry_sdk.integrations.argv import ArgvIntegration
	from sentry_sdk.integrations.atexit import AtexitIntegration
	from sentry_sdk.integrations.dedupe import DedupeIntegration
	from sentry_sdk.integrations.excepthook import ExcepthookIntegration
	from sentry_sdk.integrations.modules import ModulesIntegration
	from sentry_sdk.integrations.wsgi import SentryWsgiMiddleware

	from mrinimitable.utils.sentry import MrinimitableIntegration, before_send

	integrations = [
		AtexitIntegration(),
		ExcepthookIntegration(),
		DedupeIntegration(),
		ModulesIntegration(),
		ArgvIntegration(),
	]

	experiments = {}
	kwargs = {}

	if os.getenv("ENABLE_SENTRY_DB_MONITORING"):
		integrations.append(MrinimitableIntegration())
		experiments["record_sql_params"] = True

	if tracing_sample_rate := os.getenv("SENTRY_TRACING_SAMPLE_RATE"):
		kwargs["traces_sample_rate"] = float(tracing_sample_rate)
		application = SentryWsgiMiddleware(application)

	if profiling_sample_rate := os.getenv("SENTRY_PROFILING_SAMPLE_RATE"):
		kwargs["profiles_sample_rate"] = float(profiling_sample_rate)

	sentry_sdk.init(
		dsn=sentry_dsn,
		before_send=before_send,
		attach_stacktrace=True,
		release=mrinimitable.__version__,
		auto_enabling_integrations=False,
		default_integrations=False,
		integrations=integrations,
		_experiments=experiments,
		**kwargs,
	)


def serve(
	port=8000,
	profile=False,
	no_reload=False,
	no_threading=False,
	site=None,
	sites_path=".",
	proxy=False,
):
	global application, _site, _sites_path
	_site = site
	_sites_path = sites_path

	from werkzeug.serving import run_simple

	if profile or os.environ.get("USE_PROFILER"):
		application = ProfilerMiddleware(application, sort_by=("cumtime", "calls"), restrictions=(200,))

	if not os.environ.get("NO_STATICS"):
		application = application_with_statics()

	if proxy or os.environ.get("USE_PROXY"):
		application = ProxyFix(application, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

	application.debug = True
	application.config = {"SERVER_NAME": "127.0.0.1:8000"}

	log = logging.getLogger("werkzeug")
	log.propagate = False

	in_test_env = os.environ.get("CI")
	if in_test_env:
		log.setLevel(logging.ERROR)

	run_simple(
		"0.0.0.0",
		int(port),
		application,
		exclude_patterns=["test_*"],
		use_reloader=False if in_test_env else not no_reload,
		use_debugger=not in_test_env,
		use_evalex=not in_test_env,
		threaded=not no_threading,
	)


def application_with_statics():
	global application, _sites_path

	application = SharedDataMiddleware(application, {"/assets": str(os.path.join(_sites_path, "assets"))})

	application = StaticDataMiddleware(application, {"/files": str(os.path.abspath(_sites_path))})

	return application
