import mrinimitable


def execute():
	mrinimitable.reload_doctype("System Settings")
	doc = mrinimitable.get_single("System Settings")
	doc.enable_chat = 1

	# Changes prescribed by Nabin Hait (nabin@mrinimitable.io)
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_permissions = True

	doc.save()
