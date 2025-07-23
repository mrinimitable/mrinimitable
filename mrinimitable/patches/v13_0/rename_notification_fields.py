# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.model.utils.rename_field import rename_field


def execute():
	"""
	Change notification recipient fields from email to receiver fields
	"""
	mrinimitable.reload_doc("Email", "doctype", "Notification Recipient")
	mrinimitable.reload_doc("Email", "doctype", "Notification")

	rename_field("Notification Recipient", "email_by_document_field", "receiver_by_document_field")
	rename_field("Notification Recipient", "email_by_role", "receiver_by_role")
