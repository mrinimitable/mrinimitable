import mrinimitable


def execute():
	mrinimitable.delete_doc_if_exists("DocType", "Post")
	mrinimitable.delete_doc_if_exists("DocType", "Post Comment")
