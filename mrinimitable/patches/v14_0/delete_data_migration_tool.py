# Copyright (c) 2022, Mrinimitable Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import mrinimitable


def execute():
	doctypes = mrinimitable.get_all("DocType", {"module": "Data Migration", "custom": 0}, pluck="name")
	for doctype in doctypes:
		mrinimitable.delete_doc("DocType", doctype, ignore_missing=True)

	mrinimitable.delete_doc("Module Def", "Data Migration", ignore_missing=True, force=True)
