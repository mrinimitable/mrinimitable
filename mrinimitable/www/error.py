# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import mrinimitable
from mrinimitable import _
from mrinimitable.utils.response import is_traceback_allowed

no_cache = 1


def get_context(context):
	if mrinimitable.flags.in_migrate:
		return

	if not context.title:
		context.title = _("Server Error")
	if not context.message:
		context.message = _("There was an error building this page")

	return {
		"error": mrinimitable.get_traceback().replace("<", "&lt;").replace(">", "&gt;")
		if is_traceback_allowed()
		else ""
	}
