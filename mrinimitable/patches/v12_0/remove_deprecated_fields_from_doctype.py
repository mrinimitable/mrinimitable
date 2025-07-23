import mrinimitable


def execute():
	mrinimitable.reload_doc("core", "doctype", "doctype_link")
	mrinimitable.reload_doc("core", "doctype", "doctype_action")
	mrinimitable.reload_doc("core", "doctype", "doctype")
	mrinimitable.model.delete_fields({"DocType": ["hide_heading", "image_view", "read_only_onload"]}, delete=1)

	mrinimitable.db.delete("Property Setter", {"property": "read_only_onload"})
