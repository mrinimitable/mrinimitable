# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os

no_cache = 1

import json
import re
from urllib.parse import urlencode

import mrinimitable
import mrinimitable.sessions
from mrinimitable import _
from mrinimitable.utils.jinja_globals import is_rtl

SCRIPT_TAG_PATTERN = re.compile(r"\<script[^<]*\</script\>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script\>")


def get_context(context):
	if mrinimitable.session.user == "Guest":
		mrinimitable.response["status_code"] = 403
		mrinimitable.msgprint(_("Log in to access this page."))
		mrinimitable.redirect(f"/login?{urlencode({'redirect-to': mrinimitable.request.path})}")

	elif mrinimitable.session.data.user_type == "Website User":
		mrinimitable.throw(_("You are not permitted to access this page."), mrinimitable.PermissionError)

	try:
		boot = mrinimitable.sessions.get()
	except Exception as e:
		raise mrinimitable.SessionBootFailed from e

	# this needs commit
	csrf_token = mrinimitable.sessions.get_csrf_token()

	mrinimitable.db.commit()

	hooks = mrinimitable.get_hooks()
	app_include_js = hooks.get("app_include_js", []) + mrinimitable.conf.get("app_include_js", [])
	app_include_css = hooks.get("app_include_css", []) + mrinimitable.conf.get("app_include_css", [])
	app_include_icons = hooks.get("app_include_icons", [])

	if mrinimitable.get_system_settings("enable_telemetry") and os.getenv("MRINIMITABLE_SENTRY_DSN"):
		app_include_js.append("sentry.bundle.js")

	context.update(
		{
			"no_cache": 1,
			"build_version": mrinimitable.utils.get_build_version(),
			"app_include_js": app_include_js,
			"app_include_css": app_include_css,
			"app_include_icons": app_include_icons,
			"layout_direction": "rtl" if is_rtl() else "ltr",
			"lang": mrinimitable.local.lang,
			"sounds": hooks["sounds"],
			"boot": boot,
			"desk_theme": boot.get("desk_theme") or "Light",
			"csrf_token": csrf_token,
			"google_analytics_id": mrinimitable.conf.get("google_analytics_id"),
			"google_analytics_anonymize_ip": mrinimitable.conf.get("google_analytics_anonymize_ip"),
			"app_name": (
				mrinimitable.get_website_settings("app_name") or mrinimitable.get_system_settings("app_name") or "Mrinimitable"
			),
		}
	)

	return context
