import mrinimitable


def execute():
	doctype = "Top Bar Item"
	if not mrinimitable.db.table_exists(doctype) or not mrinimitable.db.has_column(doctype, "target"):
		return

	mrinimitable.reload_doc("website", "doctype", "top_bar_item")
	mrinimitable.db.set_value(doctype, {"target": 'target = "_blank"'}, "open_in_new_tab", 1)
