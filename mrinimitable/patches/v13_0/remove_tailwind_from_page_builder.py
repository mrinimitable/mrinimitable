# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	mrinimitable.reload_doc("website", "doctype", "web_page_block")
	# remove unused templates
	mrinimitable.delete_doc("Web Template", "Navbar with Links on Right", force=1)
	mrinimitable.delete_doc("Web Template", "Footer Horizontal", force=1)
