# Copyright (c) 2021, Mrinimitable Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt


import mrinimitable


def execute():
	mrinimitable.reload_doc("website", "doctype", "web_form_list_column")
	mrinimitable.reload_doctype("Web Form")

	for web_form in mrinimitable.get_all("Web Form", fields=["*"]):
		if web_form.allow_multiple and not web_form.show_list:
			mrinimitable.db.set_value("Web Form", web_form.name, "show_list", True)
