# Copyright (c) 2023, Mrinimitable Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import mrinimitable
from mrinimitable import _
from mrinimitable.apps import get_apps


def get_context():
	all_apps = get_apps()

	system_default_app = mrinimitable.get_system_settings("default_app")
	user_default_app = mrinimitable.db.get_value("User", mrinimitable.session.user, "default_app")
	default_app = user_default_app if user_default_app else system_default_app

	if len(all_apps) == 0:
		mrinimitable.local.flags.redirect_location = "/app"
		raise mrinimitable.Redirect

	for app in all_apps:
		app["is_default"] = True if app.get("name") == default_app else False

	return {"apps": all_apps}
