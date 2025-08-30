import mrinimitable


def execute():
	mrinimitable.db.delete("DocType", {"name": "Feedback Request"})
