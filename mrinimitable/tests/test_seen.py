# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import mrinimitable
from mrinimitable.tests import IntegrationTestCase


class TestSeen(IntegrationTestCase):
	def tearDown(self):
		mrinimitable.set_user("Administrator")

	def test_if_user_is_added(self):
		ev = mrinimitable.get_doc(
			{
				"doctype": "Event",
				"subject": "test event for seen",
				"starts_on": "2016-01-01 10:10:00",
				"event_type": "Public",
			}
		).insert()

		mrinimitable.set_user("test@example.com")

		from mrinimitable.desk.form.load import getdoc

		# load the form
		getdoc("Event", ev.name)

		# reload the event
		ev = mrinimitable.get_doc("Event", ev.name)

		self.assertTrue("test@example.com" in json.loads(ev._seen))

		# test another user
		mrinimitable.set_user("test1@example.com")

		# load the form
		getdoc("Event", ev.name)

		# reload the event
		ev = mrinimitable.get_doc("Event", ev.name)

		self.assertTrue("test@example.com" in json.loads(ev._seen))
		self.assertTrue("test1@example.com" in json.loads(ev._seen))

		ev.save()
		ev = mrinimitable.get_doc("Event", ev.name)

		self.assertFalse("test@example.com" in json.loads(ev._seen))
		self.assertTrue("test1@example.com" in json.loads(ev._seen))
