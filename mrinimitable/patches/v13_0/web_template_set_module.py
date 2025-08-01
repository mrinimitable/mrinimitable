# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	"""Set default module for standard Web Template, if none."""
	mrinimitable.reload_doc("website", "doctype", "Web Template Field")
	mrinimitable.reload_doc("website", "doctype", "web_template")

	standard_templates = mrinimitable.get_list("Web Template", {"standard": 1})
	for template in standard_templates:
		doc = mrinimitable.get_doc("Web Template", template.name)
		if not doc.module:
			doc.module = "Website"
			doc.save()
