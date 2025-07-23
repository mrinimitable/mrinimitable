# Copyright (c) 2018, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import mrinimitable
from mrinimitable.tests import IntegrationTestCase


class TestViewLog(IntegrationTestCase):
	def tearDown(self):
		mrinimitable.set_user("Administrator")

	def test_if_user_is_added(self):
		ev = mrinimitable.get_doc(
			{
				"doctype": "Event",
				"subject": "test event for view logs",
				"starts_on": "2018-06-04 14:11:00",
				"event_type": "Public",
			}
		).insert()

		mrinimitable.set_user("test@example.com")

		from mrinimitable.desk.form.load import getdoc

		# load the form
		getdoc("Event", ev.name)
		a = mrinimitable.get_value(
			doctype="View Log",
			filters={"reference_doctype": "Event", "reference_name": ev.name},
			fieldname=["viewed_by"],
		)

		self.assertEqual("test@example.com", a)
		self.assertNotEqual("test1@example.com", a)
