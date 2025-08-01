import mrinimitable


def execute():
	"""
	Rename the Marketing Campaign table to UTM Campaign table
	"""
	if mrinimitable.db.exists("DocType", "UTM Campaign"):
		return

	if not mrinimitable.db.exists("DocType", "Marketing Campaign"):
		return

	mrinimitable.rename_doc("DocType", "Marketing Campaign", "UTM Campaign", force=True)
	mrinimitable.reload_doctype("UTM Campaign", force=True)
