# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable
import mrinimitable.www.list
from mrinimitable import _

no_cache = 1


def get_context(context):
	if mrinimitable.session.user == "Guest":
		mrinimitable.throw(_("You need to be logged in to access this page"), mrinimitable.PermissionError)

	context.current_user = mrinimitable.get_doc("User", mrinimitable.session.user)
	context.show_sidebar = False
