# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import mrinimitable
import mrinimitable.desk.form.assign_to
from mrinimitable.automation.doctype.assignment_rule.test_assignment_rule import (
	TEST_DOCTYPE,
	_make_test_record,
	create_test_doctype,
)
from mrinimitable.desk.form.load import get_assignments
from mrinimitable.desk.listview import get_group_by_count
from mrinimitable.tests import IntegrationTestCase


class TestAssign(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_doctype(TEST_DOCTYPE)

	def test_assign(self):
		todo = mrinimitable.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not mrinimitable.db.exists("User", "test@example.com"):
			mrinimitable.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		self._test_basic_assign_on_document(todo)

	def _test_basic_assign_on_document(self, doc):
		added = assign(doc, "test@example.com")

		self.assertTrue("test@example.com" in [d.owner for d in added])

		mrinimitable.desk.form.assign_to.remove(doc.doctype, doc.name, "test@example.com")

		# assignment is cleared
		assignments = mrinimitable.desk.form.assign_to.get(dict(doctype=doc.doctype, name=doc.name))
		self.assertEqual(len(assignments), 0)

	def test_assign_single(self):
		c = mrinimitable.get_doc("Contact Us Settings")
		self._test_basic_assign_on_document(c)

	def test_assignment_count(self):
		mrinimitable.db.delete("ToDo")

		if not mrinimitable.db.exists("User", "test_assign1@example.com"):
			mrinimitable.get_doc(
				{
					"doctype": "User",
					"email": "test_assign1@example.com",
					"first_name": "Test",
					"roles": [{"role": "System Manager"}],
				}
			).insert()

		if not mrinimitable.db.exists("User", "test_assign2@example.com"):
			mrinimitable.get_doc(
				{
					"doctype": "User",
					"email": "test_assign2@example.com",
					"first_name": "Test",
					"roles": [{"role": "System Manager"}],
				}
			).insert()

		note = _make_test_record()
		assign(note, "test_assign1@example.com")

		note = _make_test_record(public=1)
		assign(note, "test_assign2@example.com")

		note = _make_test_record(public=1)
		assign(note, "test_assign2@example.com")

		note = _make_test_record()
		assign(note, "test_assign2@example.com")

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, "[]", "assigned_to")}

		self.assertTrue("test_assign1@example.com" in data)
		self.assertEqual(data["test_assign1@example.com"], 1)
		self.assertEqual(data["test_assign2@example.com"], 3)

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, '[{"public": 1}]', "assigned_to")}

		self.assertFalse("test_assign1@example.com" in data)
		self.assertEqual(data["test_assign2@example.com"], 2)

		mrinimitable.db.rollback()

	def test_assignment_removal(self):
		todo = mrinimitable.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not mrinimitable.db.exists("User", "test@example.com"):
			mrinimitable.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		new_todo = assign(todo, "test@example.com")

		# remove assignment
		mrinimitable.db.set_value("ToDo", new_todo[0].name, "allocated_to", "")

		self.assertFalse(get_assignments("ToDo", todo.name))


def assign(doc, user):
	return mrinimitable.desk.form.assign_to.add(
		{
			"assign_to": [user],
			"doctype": doc.doctype,
			"name": doc.name,
			"description": "test",
		}
	)
