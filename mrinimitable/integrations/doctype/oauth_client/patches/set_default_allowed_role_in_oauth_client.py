import mrinimitable


def execute():
	"""Set default allowed role in OAuth Client"""
	for client in mrinimitable.get_all("OAuth Client", pluck="name"):
		doc = mrinimitable.get_doc("OAuth Client", client)
		if doc.allowed_roles:
			continue
		row = doc.append("allowed_roles", {"role": "All"})  # Current default
		row.db_insert()
