# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	mrinimitable.reload_doc("website", "doctype", "website_theme_ignore_app")
	themes = mrinimitable.get_all("Website Theme", filters={"theme_url": ("not like", "/files/website_theme/%")})
	for theme in themes:
		doc = mrinimitable.get_doc("Website Theme", theme.name)
		try:
			doc.save()
		except Exception:
			print("Ignoring....")
			print(mrinimitable.get_traceback())
