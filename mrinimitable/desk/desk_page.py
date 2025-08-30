# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def get(name):
	"""
	Return the :term:`doclist` of the `Page` specified by `name`
	"""
	page = mrinimitable.get_doc("Page", name)
	if page.is_permitted():
		page.load_assets()
		docs = mrinimitable._dict(page.as_dict())
		if getattr(page, "_dynamic_page", None):
			docs["_dynamic_page"] = 1

		return docs
	else:
		mrinimitable.response["403"] = 1
		raise mrinimitable.PermissionError("No read permission for Page %s" % (page.title or name))


@mrinimitable.whitelist(allow_guest=True)
def getpage(name: str):
	"""
	Load the page from `mrinimitable.form` and send it via `mrinimitable.response`
	"""

	doc = get(name)
	mrinimitable.response.docs.append(doc)
