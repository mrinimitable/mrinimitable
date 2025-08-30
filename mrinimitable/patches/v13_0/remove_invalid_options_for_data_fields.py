# Copyright (c) 2022, Mrinimitable and Contributors
# License: MIT. See LICENSE


import mrinimitable
from mrinimitable.model import data_field_options


def execute():
	custom_field = mrinimitable.qb.DocType("Custom Field")
	(
		mrinimitable.qb.update(custom_field)
		.set(custom_field.options, None)
		.where((custom_field.fieldtype == "Data") & (custom_field.options.notin(data_field_options)))
	).run()
