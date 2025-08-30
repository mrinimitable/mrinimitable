# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	mrinimitable.delete_doc("DocType", "Package Publish Tool", ignore_missing=True)
	mrinimitable.delete_doc("DocType", "Package Document Type", ignore_missing=True)
	mrinimitable.delete_doc("DocType", "Package Publish Target", ignore_missing=True)
