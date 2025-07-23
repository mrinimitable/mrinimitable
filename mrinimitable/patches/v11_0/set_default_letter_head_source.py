import mrinimitable


def execute():
	mrinimitable.reload_doctype("Letter Head")

	# source of all existing letter heads must be HTML
	mrinimitable.db.sql("update `tabLetter Head` set source = 'HTML'")
