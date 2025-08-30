import mrinimitable


def execute():
	if mrinimitable.db.db_type == "mariadb":
		mrinimitable.db.sql(
			"ALTER TABLE __UserSettings CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
		)
