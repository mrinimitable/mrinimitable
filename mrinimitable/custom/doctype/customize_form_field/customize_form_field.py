# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from mrinimitable.model.document import Document


class CustomizeFormField(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		allow_bulk_edit: DF.Check
		allow_in_quick_entry: DF.Check
		allow_on_submit: DF.Check
		bold: DF.Check
		collapsible: DF.Check
		collapsible_depends_on: DF.Code | None
		columns: DF.Int
		default: DF.SmallText | None
		depends_on: DF.Code | None
		description: DF.Text | None
		fetch_from: DF.SmallText | None
		fetch_if_empty: DF.Check
		fieldname: DF.Data | None
		fieldtype: DF.Literal[
			"Autocomplete",
			"Attach",
			"Attach Image",
			"Barcode",
			"Button",
			"Check",
			"Code",
			"Color",
			"Column Break",
			"Currency",
			"Data",
			"Date",
			"Datetime",
			"Duration",
			"Dynamic Link",
			"Float",
			"Fold",
			"Geolocation",
			"Heading",
			"HTML",
			"HTML Editor",
			"Icon",
			"Image",
			"Int",
			"JSON",
			"Link",
			"Long Text",
			"Markdown Editor",
			"Password",
			"Percent",
			"Phone",
			"Rating",
			"Read Only",
			"Section Break",
			"Select",
			"Signature",
			"Small Text",
			"Tab Break",
			"Table",
			"Table MultiSelect",
			"Text",
			"Text Editor",
			"Time",
		]
		hidden: DF.Check
		hide_border: DF.Check
		hide_days: DF.Check
		hide_seconds: DF.Check
		ignore_user_permissions: DF.Check
		ignore_xss_filter: DF.Check
		in_filter: DF.Check
		in_global_search: DF.Check
		in_list_view: DF.Check
		in_preview: DF.Check
		in_standard_filter: DF.Check
		is_custom_field: DF.Check
		is_system_generated: DF.Check
		is_virtual: DF.Check
		label: DF.Data | None
		length: DF.Int
		link_filters: DF.JSON | None
		mandatory_depends_on: DF.Code | None
		no_copy: DF.Check
		non_negative: DF.Check
		options: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		permlevel: DF.Int
		placeholder: DF.Data | None
		precision: DF.Literal["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
		print_hide: DF.Check
		print_hide_if_no_value: DF.Check
		print_width: DF.Data | None
		read_only: DF.Check
		read_only_depends_on: DF.Code | None
		remember_last_selected_value: DF.Check
		report_hide: DF.Check
		reqd: DF.Check
		show_dashboard: DF.Check
		sort_options: DF.Check
		translatable: DF.Check
		unique: DF.Check
		width: DF.Data | None
	# end: auto-generated types

	pass
