import mrinimitable


def execute():
	"""sets "wkhtmltopdf" as default for pdf_generator field"""
	for pf in mrinimitable.get_all("Print Format", pluck="name"):
		mrinimitable.db.set_value("Print Format", pf, "pdf_generator", "wkhtmltopdf", update_modified=False)
