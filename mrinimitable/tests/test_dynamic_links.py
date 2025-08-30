# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import mrinimitable
from mrinimitable.tests import IntegrationTestCase


class TestDynamicLinks(IntegrationTestCase):
	def setUp(self):
		mrinimitable.db.delete("Email Unsubscribe")

	def test_delete_normal(self):
		event = mrinimitable.get_doc(
			{
				"doctype": "Event",
				"subject": "test-for-delete",
				"starts_on": "2014-01-01",
				"event_type": "Public",
			}
		).insert()

		unsub = mrinimitable.get_doc(
			{
				"doctype": "Email Unsubscribe",
				"email": "test@example.com",
				"reference_doctype": event.doctype,
				"reference_name": event.name,
			}
		).insert()

		event.delete()

		self.assertFalse(mrinimitable.db.exists("Email Unsubscribe", unsub.name))

	def test_delete_with_comment(self):
		event = mrinimitable.get_doc(
			{
				"doctype": "Event",
				"subject": "test-for-delete-1",
				"starts_on": "2014-01-01",
				"event_type": "Public",
			}
		).insert()
		event.add_comment("Comment", "test")

		self.assertTrue(
			mrinimitable.get_all("Comment", filters={"reference_doctype": "Event", "reference_name": event.name})
		)
		event.delete()
		self.assertFalse(
			mrinimitable.get_all("Comment", filters={"reference_doctype": "Event", "reference_name": event.name})
		)

	def test_custom_fields(self):
		from mrinimitable.utils.testutils import add_custom_field, clear_custom_fields

		add_custom_field("Event", "test_ref_doc", "Link", "DocType")
		add_custom_field("Event", "test_ref_name", "Dynamic Link", "test_ref_doc")

		unsub = mrinimitable.get_doc(
			{"doctype": "Email Unsubscribe", "email": "test@example.com", "global_unsubscribe": 1}
		).insert()

		event = mrinimitable.get_doc(
			{
				"doctype": "Event",
				"subject": "test-for-delete-2",
				"starts_on": "2014-01-01",
				"event_type": "Public",
				"test_ref_doc": unsub.doctype,
				"test_ref_name": unsub.name,
			}
		).insert()

		self.assertRaises(mrinimitable.LinkExistsError, unsub.delete)

		event.test_ref_doc = None
		event.test_ref_name = None
		event.save()

		unsub.delete()

		clear_custom_fields("Event")
		mrinimitable.db.commit()  # undo changes done by DDL
