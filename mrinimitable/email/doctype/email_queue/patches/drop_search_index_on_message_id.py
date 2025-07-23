import mrinimitable


def execute():
	"""Drop search index on message_id"""

	if mrinimitable.db.get_column_type("Email Queue", "message_id") == "text":
		return

	if index := mrinimitable.db.get_column_index("tabEmail Queue", "message_id", unique=False):
		mrinimitable.db.sql(f"ALTER TABLE `tabEmail Queue` DROP INDEX `{index.Key_name}`")
