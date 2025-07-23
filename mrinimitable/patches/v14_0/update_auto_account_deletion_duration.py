import mrinimitable


def execute():
	days = mrinimitable.db.get_single_value("Website Settings", "auto_account_deletion")
	mrinimitable.db.set_single_value("Website Settings", "auto_account_deletion", days * 24)
