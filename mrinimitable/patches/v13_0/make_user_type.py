import mrinimitable
from mrinimitable.utils.install import create_user_type


def execute():
	mrinimitable.reload_doc("core", "doctype", "role")
	mrinimitable.reload_doc("core", "doctype", "user_document_type")
	mrinimitable.reload_doc("core", "doctype", "user_type_module")
	mrinimitable.reload_doc("core", "doctype", "user_select_document_type")
	mrinimitable.reload_doc("core", "doctype", "user_type")

	create_user_type()
