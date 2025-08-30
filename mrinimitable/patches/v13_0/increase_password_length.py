import mrinimitable


def execute():
	mrinimitable.db.change_column_type("__Auth", column="password", type="TEXT")
