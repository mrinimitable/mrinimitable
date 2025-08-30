# Copyright (c) 2018, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	signatures = mrinimitable.db.get_list("User", {"email_signature": ["!=", ""]}, ["name", "email_signature"])
	mrinimitable.reload_doc("core", "doctype", "user")
	for d in signatures:
		signature = d.get("email_signature")
		signature = signature.replace("\n", "<br>")
		signature = "<div>" + signature + "</div>"
		mrinimitable.db.set_value("User", d.get("name"), "email_signature", signature)
