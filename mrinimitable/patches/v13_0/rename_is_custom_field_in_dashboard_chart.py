import mrinimitable
from mrinimitable.model.utils.rename_field import rename_field


def execute():
	if not mrinimitable.db.table_exists("Dashboard Chart"):
		return

	mrinimitable.reload_doc("desk", "doctype", "dashboard_chart")

	if mrinimitable.db.has_column("Dashboard Chart", "is_custom"):
		rename_field("Dashboard Chart", "is_custom", "use_report_chart")
