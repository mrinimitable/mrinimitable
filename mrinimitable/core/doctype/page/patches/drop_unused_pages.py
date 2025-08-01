import mrinimitable


def execute():
	for name in ("desktop", "space"):
		mrinimitable.delete_doc("Page", name)
