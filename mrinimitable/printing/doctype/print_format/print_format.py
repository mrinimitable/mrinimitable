# Copyright (c) 2017, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import json

import mrinimitable
import mrinimitable.utils
from mrinimitable import _
from mrinimitable.model.document import Document
from mrinimitable.utils.jinja import validate_template
from mrinimitable.utils.weasyprint import download_pdf, get_html


class PrintFormat(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		absolute_value: DF.Check
		align_labels_right: DF.Check
		css: DF.Code | None
		custom_format: DF.Check
		default_print_language: DF.Link | None
		disabled: DF.Check
		doc_type: DF.Link | None
		font: DF.Data | None
		font_size: DF.Int
		format_data: DF.Code | None
		html: DF.Code | None
		line_breaks: DF.Check
		margin_bottom: DF.Float
		margin_left: DF.Float
		margin_right: DF.Float
		margin_top: DF.Float
		module: DF.Link | None
		page_number: DF.Literal[
			"Hide", "Top Left", "Top Center", "Top Right", "Bottom Left", "Bottom Center", "Bottom Right"
		]
		pdf_generator: DF.Literal["wkhtmltopdf"]
		print_format_builder: DF.Check
		print_format_builder_beta: DF.Check
		print_format_for: DF.Literal["DocType", "Report"]
		print_format_type: DF.Literal["Jinja", "JS"]
		raw_commands: DF.Code | None
		raw_printing: DF.Check
		report: DF.Link | None
		show_section_headings: DF.Check
		standard: DF.Literal["No", "Yes"]
	# end: auto-generated types

	def onload(self):
		templates = mrinimitable.get_all(
			"Print Format Field Template",
			fields=["template", "field", "name"],
			filters={"document_type": self.doc_type},
		)
		self.set_onload("print_templates", templates)

	def before_save(self):
		if self.print_format_for == "Report":
			self.print_format_type = "JS"

	def get_html(self, docname, letterhead=None):
		return get_html(self.doc_type, docname, self.name, letterhead)

	def download_pdf(self, docname, letterhead=None):
		return download_pdf(self.doc_type, docname, self.name, letterhead)

	def validate(self):
		if (
			self.standard == "Yes"
			and not mrinimitable.local.conf.get("developer_mode")
			and not mrinimitable.flags.in_migrate
			and not mrinimitable.flags.in_install
			and not mrinimitable.in_test
		):
			mrinimitable.throw(mrinimitable._("Standard Print Format cannot be updated"))

		# old_doc_type is required for clearing item cache
		self.old_doc_type = mrinimitable.db.get_value("Print Format", self.name, "doc_type")

		self.extract_images()

		if not self.module:
			self.module = mrinimitable.db.get_value("DocType", self.doc_type, "module")

		if self.html and self.print_format_type != "JS":
			validate_template(self.html)

		if self.custom_format and self.raw_printing and not self.raw_commands:
			mrinimitable.throw(_("{0} are required").format(mrinimitable.bold(_("Raw Commands"))), mrinimitable.MandatoryError)

		if self.custom_format and not self.html and not self.raw_printing:
			mrinimitable.throw(_("{0} is required").format(mrinimitable.bold(_("HTML"))), mrinimitable.MandatoryError)

		if self.print_format_for == "Report" and not self.report:
			mrinimitable.throw(_("{0} is required").format(mrinimitable.bold(_("Report"))), mrinimitable.MandatoryError)

	def extract_images(self):
		from mrinimitable.core.doctype.file.utils import extract_images_from_html

		if self.print_format_builder_beta:
			return

		if self.format_data:
			data = json.loads(self.format_data)
			for df in data:
				if df.get("fieldtype") and df["fieldtype"] in ("HTML", "Custom HTML") and df.get("options"):
					df["options"] = extract_images_from_html(self, df["options"])
			self.format_data = json.dumps(data)

	def on_update(self):
		if hasattr(self, "old_doc_type") and self.old_doc_type:
			mrinimitable.clear_cache(doctype=self.old_doc_type)
		if self.doc_type:
			mrinimitable.clear_cache(doctype=self.doc_type)

		self.export_doc()

	def after_rename(self, old: str, new: str, *args, **kwargs):
		if self.doc_type:
			mrinimitable.clear_cache(doctype=self.doc_type)

		# update property setter default_print_format if set
		mrinimitable.db.set_value(
			"Property Setter",
			{
				"doctype_or_field": "DocType",
				"doc_type": self.doc_type,
				"property": "default_print_format",
				"value": old,
			},
			"value",
			new,
		)

	def export_doc(self):
		from mrinimitable.modules.utils import export_module_json

		return export_module_json(self, self.standard == "Yes", self.module)

	def on_trash(self):
		if self.doc_type:
			mrinimitable.clear_cache(doctype=self.doc_type)


@mrinimitable.whitelist()
def make_default(name: str):
	"""Set print format as default"""
	print_format = mrinimitable.get_doc("Print Format", name)
	print_format.check_permission("write")

	doctype = mrinimitable.get_doc("DocType", print_format.doc_type)
	if doctype.custom:
		doctype.default_print_format = name
		doctype.save()
	else:
		# "Customize form"
		mrinimitable.make_property_setter(
			{
				"doctype_or_field": "DocType",
				"doctype": print_format.doc_type,
				"property": "default_print_format",
				"value": name,
			}
		)

	mrinimitable.msgprint(
		mrinimitable._("{0} is now default print format for {1} doctype").format(
			mrinimitable.bold(name), mrinimitable.bold(print_format.doc_type)
		)
	)
