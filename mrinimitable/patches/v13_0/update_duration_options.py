# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	mrinimitable.reload_doc("core", "doctype", "DocField")

	if mrinimitable.db.has_column("DocField", "show_days"):
		mrinimitable.db.sql(
			"""
			UPDATE
				tabDocField
			SET
				hide_days = 1 WHERE show_days = 0
		"""
		)
		mrinimitable.db.sql_ddl("alter table tabDocField drop column show_days")

	if mrinimitable.db.has_column("DocField", "show_seconds"):
		mrinimitable.db.sql(
			"""
			UPDATE
				tabDocField
			SET
				hide_seconds = 1 WHERE show_seconds = 0
		"""
		)
		mrinimitable.db.sql_ddl("alter table tabDocField drop column show_seconds")

	mrinimitable.clear_cache(doctype="DocField")
