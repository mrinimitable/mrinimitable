import mrinimitable


def execute():
	if mrinimitable.db.table_exists("Prepared Report"):
		mrinimitable.reload_doc("core", "doctype", "prepared_report")
		prepared_reports = mrinimitable.get_all("Prepared Report")
		for report in prepared_reports:
			mrinimitable.delete_doc("Prepared Report", report.name)
