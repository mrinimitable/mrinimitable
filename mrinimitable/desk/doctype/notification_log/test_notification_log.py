# Copyright (c) 2019, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import mrinimitable
from mrinimitable.core.doctype.user.user import get_system_users
from mrinimitable.desk.form.assign_to import add as assign_task
from mrinimitable.tests import IntegrationTestCase


class TestNotificationLog(IntegrationTestCase):
	def test_assignment(self):
		todo = get_todo()
		user = get_user()

		assign_task(
			{"assign_to": [user], "doctype": "ToDo", "name": todo.name, "description": todo.description}
		)
		log_type = mrinimitable.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Assignment")

	def test_share(self):
		todo = get_todo()
		user = get_user()

		mrinimitable.share.add("ToDo", todo.name, user, notify=1)
		log_type = mrinimitable.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Share")

		email = get_last_email_queue()
		content = f"Subject: {mrinimitable.utils.get_fullname(mrinimitable.session.user)} shared a document ToDo"
		self.assertTrue(content in email.message)


def get_last_email_queue():
	res = mrinimitable.get_all("Email Queue", fields=["message"], order_by="creation desc", limit=1)
	return res[0]


def get_todo():
	if not mrinimitable.get_all("ToDo"):
		return mrinimitable.get_doc({"doctype": "ToDo", "description": "Test for Notification"}).insert()

	res = mrinimitable.get_all("ToDo", limit=1)
	return mrinimitable.get_cached_doc("ToDo", res[0].name)


def get_user():
	return get_system_users(limit=1)[0]
