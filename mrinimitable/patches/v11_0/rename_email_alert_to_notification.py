import mrinimitable
from mrinimitable.model.rename_doc import rename_doc


def execute():
	if mrinimitable.db.table_exists("Email Alert Recipient") and not mrinimitable.db.table_exists(
		"Notification Recipient"
	):
		rename_doc("DocType", "Email Alert Recipient", "Notification Recipient")
		mrinimitable.reload_doc("email", "doctype", "notification_recipient")

	if mrinimitable.db.table_exists("Email Alert") and not mrinimitable.db.table_exists("Notification"):
		rename_doc("DocType", "Email Alert", "Notification")
		mrinimitable.reload_doc("email", "doctype", "notification")
