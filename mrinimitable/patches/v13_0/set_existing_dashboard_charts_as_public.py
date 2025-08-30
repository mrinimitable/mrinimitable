import mrinimitable


def execute():
	mrinimitable.reload_doc("desk", "doctype", "dashboard_chart")

	if not mrinimitable.db.table_exists("Dashboard Chart"):
		return

	users_with_permission = mrinimitable.get_all(
		"Has Role",
		fields=["parent"],
		filters={"role": ["in", ["System Manager", "Dashboard Manager"]], "parenttype": "User"},
		distinct=True,
	)

	users = [item.parent for item in users_with_permission]
	charts = mrinimitable.get_all("Dashboard Chart", filters={"owner": ["in", users]})

	for chart in charts:
		mrinimitable.db.set_value("Dashboard Chart", chart.name, "is_public", 1)
