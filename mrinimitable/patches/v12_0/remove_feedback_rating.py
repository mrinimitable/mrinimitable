import mrinimitable


def execute():
	"""
	Deprecate Feedback Trigger and Rating. This feature was not customizable.
	Now can be achieved via custom Web Forms
	"""
	mrinimitable.delete_doc("DocType", "Feedback Trigger")
	mrinimitable.delete_doc("DocType", "Feedback Rating")
