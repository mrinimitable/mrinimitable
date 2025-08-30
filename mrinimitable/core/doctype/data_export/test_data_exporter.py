# Copyright (c) 2019, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import mrinimitable
from mrinimitable.core.doctype.data_export.exporter import DataExporter
from mrinimitable.tests import IntegrationTestCase


class TestDataExporter(IntegrationTestCase):
	def setUp(self):
		self.doctype_name = "Test DocType for Export Tool"
		self.doc_name = "Test Data for Export Tool"
		self.create_doctype_if_not_exists(doctype_name=self.doctype_name)
		self.create_test_data()

	def create_doctype_if_not_exists(self, doctype_name, force=False):
		"""
		Helper Function for setting up doctypes
		"""
		if force:
			mrinimitable.delete_doc_if_exists("DocType", doctype_name)
			mrinimitable.delete_doc_if_exists("DocType", "Child 1 of " + doctype_name)

		if mrinimitable.db.exists("DocType", doctype_name):
			return

		# Child Table 1
		table_1_name = "Child 1 of " + doctype_name
		mrinimitable.get_doc(
			{
				"doctype": "DocType",
				"name": table_1_name,
				"module": "Custom",
				"custom": 1,
				"istable": 1,
				"fields": [
					{"label": "Child Title", "fieldname": "child_title", "reqd": 1, "fieldtype": "Data"},
					{"label": "Child Number", "fieldname": "child_number", "fieldtype": "Int"},
				],
			}
		).insert()

		# Main Table
		mrinimitable.get_doc(
			{
				"doctype": "DocType",
				"name": doctype_name,
				"module": "Custom",
				"custom": 1,
				"autoname": "field:title",
				"fields": [
					{"label": "Title", "fieldname": "title", "reqd": 1, "fieldtype": "Data"},
					{"label": "Number", "fieldname": "number", "fieldtype": "Int"},
					{
						"label": "Table Field 1",
						"fieldname": "table_field_1",
						"fieldtype": "Table",
						"options": table_1_name,
					},
				],
				"permissions": [{"role": "System Manager"}],
			}
		).insert()

	def create_test_data(self, force=False):
		"""
		Helper Function creating test data
		"""
		if force:
			mrinimitable.delete_doc(self.doctype_name, self.doc_name)

		if not mrinimitable.db.exists(self.doctype_name, self.doc_name):
			self.doc = mrinimitable.get_doc(
				doctype=self.doctype_name,
				title=self.doc_name,
				number="100",
				table_field_1=[
					{"child_title": "Child Title 1", "child_number": "50"},
					{"child_title": "Child Title 2", "child_number": "51"},
				],
			).insert()
		else:
			self.doc = mrinimitable.get_doc(self.doctype_name, self.doc_name)

	def test_export_content(self):
		exp = DataExporter(doctype=self.doctype_name, file_type="CSV")
		exp.build_response()

		self.assertEqual(mrinimitable.response["type"], "csv")
		self.assertEqual(mrinimitable.response["doctype"], self.doctype_name)
		self.assertTrue(mrinimitable.response["result"])
		self.assertRegex(mrinimitable.response["result"], r"Child Title 1.*?,50")
		self.assertRegex(mrinimitable.response["result"], r"Child Title 2.*?,51")

	def test_export_type(self):
		for type in ["csv", "Excel"]:
			with self.subTest(type=type):
				exp = DataExporter(doctype=self.doctype_name, file_type=type)
				exp.build_response()

				self.assertEqual(mrinimitable.response["doctype"], self.doctype_name)
				self.assertTrue(mrinimitable.response["result"])

				if type == "csv":
					self.assertEqual(mrinimitable.response["type"], "csv")
				elif type == "Excel":
					self.assertEqual(mrinimitable.response["type"], "binary")
					self.assertEqual(
						mrinimitable.response["filename"], self.doctype_name + ".xlsx"
					)  # 'Test DocType for Export Tool.xlsx')
					self.assertTrue(mrinimitable.response["filecontent"])

	def tearDown(self):
		pass
