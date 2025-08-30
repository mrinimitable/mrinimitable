# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	if mrinimitable.db.exists("DocType", "Onboarding"):
		mrinimitable.rename_doc("DocType", "Onboarding", "Module Onboarding", ignore_if_exists=True)
