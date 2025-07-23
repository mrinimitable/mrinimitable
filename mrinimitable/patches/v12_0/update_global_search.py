import mrinimitable
from mrinimitable.desk.page.setup_wizard.install_fixtures import update_global_search_doctypes


def execute():
	mrinimitable.reload_doc("desk", "doctype", "global_search_doctype")
	mrinimitable.reload_doc("desk", "doctype", "global_search_settings")
	update_global_search_doctypes()
