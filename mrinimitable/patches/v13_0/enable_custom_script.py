# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	"""Enable all the existing Client script"""

	mrinimitable.db.sql(
		"""
		UPDATE `tabClient Script` SET enabled=1
	"""
	)
