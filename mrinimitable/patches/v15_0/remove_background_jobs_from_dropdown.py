import mrinimitable


def execute():
	item = mrinimitable.db.exists("Navbar Item", {"item_label": "Background Jobs"})
	if not item:
		return

	mrinimitable.delete_doc("Navbar Item", item)
