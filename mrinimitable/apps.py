# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re

import mrinimitable
from mrinimitable import _
from mrinimitable.core.doctype.installed_applications.installed_applications import (
	get_apps_with_incomplete_dependencies,
	get_setup_wizard_completed_apps,
	get_setup_wizard_not_required_apps,
)

# check if route is /app or /app/* and not /app1 or /app1/*
DESK_APP_PATTERN = re.compile(r"^/app(/.*)?$")


@mrinimitable.whitelist()
def get_apps():
	apps = mrinimitable.get_installed_apps()
	app_list = []
	for app in apps:
		if (
			app not in get_setup_wizard_completed_apps()
			and app not in get_setup_wizard_not_required_apps()
			and "System Manager" not in mrinimitable.get_roles()
		):
			continue

		if app == "mrinimitable":
			continue
		app_details = mrinimitable.get_hooks("add_to_apps_screen", app_name=app)
		if not len(app_details):
			continue
		for app_detail in app_details:
			try:
				has_permission_path = app_detail.get("has_permission")
				if has_permission_path and not mrinimitable.get_attr(has_permission_path)():
					continue
				app_list.append(
					{
						"name": app,
						"logo": app_detail.get("logo"),
						"title": _(app_detail.get("title")),
						"route": app_detail.get("route"),
					}
				)
			except Exception:
				mrinimitable.log_error(f"Failed to call has_permission hook ({has_permission_path}) for {app}")
	return app_list


def get_route(app_name):
	apps = mrinimitable.get_hooks("add_to_apps_screen", app_name=app_name)
	app = next((app for app in apps if app.get("name") == app_name), None)
	return app.get("route") if app and app.get("route") else "/apps"


def is_desk_apps(apps):
	for app in apps:
		route = app.get("route")
		if route and not re.match(DESK_APP_PATTERN, route):
			return False
	return True


def get_default_path():
	apps = get_apps()
	_apps = [app for app in apps if app.get("name") != "mrinimitable"]

	if len(_apps) == 0:
		return None

	system_default_app = mrinimitable.get_system_settings("default_app")
	user_default_app = mrinimitable.get_cached_value("User", mrinimitable.session.user, "default_app")
	if system_default_app and not user_default_app:
		return get_route(system_default_app)
	elif user_default_app:
		return get_route(user_default_app)

	if len(_apps) == 1:
		return _apps[0].get("route") or "/apps"
	elif is_desk_apps(_apps):
		return "/app"
	return "/apps"


@mrinimitable.whitelist()
def set_app_as_default(app_name):
	if mrinimitable.db.get_value("User", mrinimitable.session.user, "default_app") == app_name:
		mrinimitable.db.set_value("User", mrinimitable.session.user, "default_app", "")
	else:
		mrinimitable.db.set_value("User", mrinimitable.session.user, "default_app", app_name)


@mrinimitable.whitelist()
def get_incomplete_setup_route(current_app, app_route):
	pending_apps = get_apps_with_incomplete_dependencies(current_app)

	if not pending_apps:
		return app_route

	for app in pending_apps:
		if app == "mrinimitable":
			return "app"

		app_details = mrinimitable.get_hooks("add_to_apps_screen", app_name=app)
		if not app_details:
			continue

		if route := app_details[0].get("route"):
			return route

	return app_route
