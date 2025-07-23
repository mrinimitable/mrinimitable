import mrinimitable


def execute():
	column = "apply_user_permissions"
	to_remove = ["DocPerm", "Custom DocPerm"]

	for doctype in to_remove:
		if mrinimitable.db.table_exists(doctype):
			if column in mrinimitable.db.get_table_columns(doctype):
				mrinimitable.db.sql(f"alter table `tab{doctype}` drop column {column}")

	mrinimitable.reload_doc("core", "doctype", "docperm", force=True)
	mrinimitable.reload_doc("core", "doctype", "custom_docperm", force=True)
