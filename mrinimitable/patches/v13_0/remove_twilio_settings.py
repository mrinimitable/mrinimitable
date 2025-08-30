# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	"""Add missing Twilio patch.

	While making Twilio as a standaone app, we missed to delete Twilio records from DB through migration. Adding the missing patch.
	"""
	mrinimitable.delete_doc_if_exists("DocType", "Twilio Number Group")
	if twilio_settings_doctype_in_integrations():
		mrinimitable.delete_doc_if_exists("DocType", "Twilio Settings")
		mrinimitable.db.delete("Singles", {"doctype": "Twilio Settings"})


def twilio_settings_doctype_in_integrations() -> bool:
	"""Check Twilio Settings doctype exists in integrations module or not."""
	return mrinimitable.db.exists("DocType", {"name": "Twilio Settings", "module": "Integrations"})
