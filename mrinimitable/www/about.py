# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable

sitemap = 1


def get_context(context):
	context.doc = mrinimitable.get_cached_doc("About Us Settings")

	return context
