# Copyright (c) 2020, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.model.document import Document


class ListViewSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		allow_edit: DF.Check
		disable_auto_refresh: DF.Check
		disable_automatic_recency_filters: DF.Check
		disable_comment_count: DF.Check
		disable_count: DF.Check
		disable_scrolling: DF.Check
		disable_sidebar_stats: DF.Check
		fields: DF.Code | None
	# end: auto-generated types

	pass


@mrinimitable.whitelist()
def save_listview_settings(doctype, listview_settings, removed_listview_fields):
	listview_settings = mrinimitable.parse_json(listview_settings)
	removed_listview_fields = mrinimitable.parse_json(removed_listview_fields)

	if mrinimitable.get_all("List View Settings", filters={"name": doctype}):
		doc = mrinimitable.get_doc("List View Settings", doctype)
		doc.update(listview_settings)
		doc.save()
	else:
		doc = mrinimitable.new_doc("List View Settings")
		doc.name = doctype
		doc.update(listview_settings)
		doc.insert()

	set_listview_fields(doctype, listview_settings.get("fields"), removed_listview_fields)

	return {"meta": mrinimitable.get_meta(doctype, False), "listview_settings": doc}


def set_listview_fields(doctype, listview_fields, removed_listview_fields):
	meta = mrinimitable.get_meta(doctype)

	listview_fields = [f.get("fieldname") for f in mrinimitable.parse_json(listview_fields) if f.get("fieldname")]

	for field in removed_listview_fields:
		set_in_list_view_property(doctype, meta.get_field(field), "0")

	for field in listview_fields:
		set_in_list_view_property(doctype, meta.get_field(field), "1")


def set_in_list_view_property(doctype, field, value):
	if not field or field.fieldname == "status_field":
		return

	property_setter = mrinimitable.db.get_value(
		"Property Setter",
		{"doc_type": doctype, "field_name": field.fieldname, "property": "in_list_view"},
	)
	if property_setter:
		doc = mrinimitable.get_doc("Property Setter", property_setter)
		doc.value = value
		doc.save()
	else:
		mrinimitable.make_property_setter(
			{
				"doctype": doctype,
				"doctype_or_field": "DocField",
				"fieldname": field.fieldname,
				"property": "in_list_view",
				"value": value,
				"property_type": "Check",
			},
			ignore_validate=True,
		)


@mrinimitable.whitelist()
def get_default_listview_fields(doctype):
	meta = mrinimitable.get_meta(doctype)
	path = mrinimitable.get_module_path(
		mrinimitable.scrub(meta.module), "doctype", mrinimitable.scrub(meta.name), mrinimitable.scrub(meta.name) + ".json"
	)
	doctype_json = mrinimitable.get_file_json(path)

	fields = [f.get("fieldname") for f in doctype_json.get("fields") if f.get("in_list_view")]

	if meta.title_field:
		if meta.title_field.strip() not in fields:
			fields.append(meta.title_field.strip())

	return fields
