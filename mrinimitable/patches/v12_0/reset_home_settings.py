import mrinimitable


def execute():
	mrinimitable.reload_doc("core", "doctype", "user")
	mrinimitable.db.sql(
		"""
		UPDATE `tabUser`
		SET `home_settings` = ''
		WHERE `user_type` = 'System User'
	"""
	)
