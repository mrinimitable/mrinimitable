import mrinimitable


def execute():
	mrinimitable.delete_doc_if_exists("DocType", "Web View")
	mrinimitable.delete_doc_if_exists("DocType", "Web View Component")
	mrinimitable.delete_doc_if_exists("DocType", "CSS Class")
