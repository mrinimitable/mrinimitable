import mrinimitable
from mrinimitable.model.rename_doc import rename_doc


def execute():
	if mrinimitable.db.table_exists("Standard Reply") and not mrinimitable.db.table_exists("Email Template"):
		rename_doc("DocType", "Standard Reply", "Email Template")
		mrinimitable.reload_doc("email", "doctype", "email_template")
