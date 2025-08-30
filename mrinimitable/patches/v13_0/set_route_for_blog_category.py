import mrinimitable


def execute():
	categories = mrinimitable.get_list("Blog Category")
	for category in categories:
		doc = mrinimitable.get_doc("Blog Category", category["name"])
		doc.set_route()
		doc.save()
