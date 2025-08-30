# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	if not mrinimitable.db.table_exists("Data Import"):
		return

	meta = mrinimitable.get_meta("Data Import")
	# if Data Import is the new one, return early
	if meta.fields[1].fieldname == "import_type":
		return

	mrinimitable.db.sql("DROP TABLE IF EXISTS `tabData Import Legacy`")
	mrinimitable.rename_doc("DocType", "Data Import", "Data Import Legacy")
	mrinimitable.db.commit()
	mrinimitable.db.sql("DROP TABLE IF EXISTS `tabData Import`")
	mrinimitable.rename_doc("DocType", "Data Import Beta", "Data Import")
