# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	mrinimitable.reload_doc("core", "doctype", "system_settings")
	mrinimitable.db.set_single_value("System Settings", "allow_login_after_fail", 60)
