import mrinimitable
from mrinimitable.utils.install import add_standard_navbar_items


def execute():
	# Add standard navbar items for OKAYBlue in Navbar Settings
	mrinimitable.reload_doc("core", "doctype", "navbar_settings")
	mrinimitable.reload_doc("core", "doctype", "navbar_item")
	add_standard_navbar_items()
