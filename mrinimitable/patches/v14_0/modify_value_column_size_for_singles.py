import mrinimitable


def execute():
	if mrinimitable.db.db_type == "mariadb":
		mrinimitable.db.sql_ddl("alter table `tabSingles` modify column `value` longtext")
