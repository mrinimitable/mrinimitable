import mrinimitable


def execute():
	singles = mrinimitable.qb.Table("tabSingles")
	mrinimitable.qb.from_(singles).delete().where(
		(singles.doctype == "System Settings") & (singles.field == "is_first_startup")
	).run()
