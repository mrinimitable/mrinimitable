import mrinimitable


def execute():
	table = mrinimitable.qb.DocType("Report")
	mrinimitable.qb.update(table).set(table.prepared_report, 0).where(table.disable_prepared_report == 1)
