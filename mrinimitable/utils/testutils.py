# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import mrinimitable


def add_custom_field(doctype, fieldname, fieldtype="Data", options=None):
	mrinimitable.get_doc(
		{
			"doctype": "Custom Field",
			"dt": doctype,
			"fieldname": fieldname,
			"fieldtype": fieldtype,
			"options": options,
		}
	).insert()


def clear_custom_fields(doctype):
	mrinimitable.db.delete("Custom Field", {"dt": doctype})
	mrinimitable.clear_cache(doctype=doctype)
