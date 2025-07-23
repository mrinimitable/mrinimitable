import mrinimitable
from mrinimitable.desk.doctype.notification_settings.notification_settings import (
	create_notification_settings,
)


def execute():
	mrinimitable.reload_doc("desk", "doctype", "notification_settings")
	mrinimitable.reload_doc("desk", "doctype", "notification_subscribed_document")

	users = mrinimitable.get_all("User", fields=["name"])
	for user in users:
		create_notification_settings(user.name)
