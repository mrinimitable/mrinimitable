import json

import mrinimitable


def execute():
	"""
	Migrate JSON field of Report according to changes in New ListView
	Rename key columns to fields
	Rename key add_total_row to add_totals_row
	Convert sort_by and sort_order to order_by
	"""

	reports = mrinimitable.get_all("Report", {"report_type": "Report Builder"})

	for report_name in reports:
		settings = mrinimitable.db.get_value("Report", report_name, "json")
		if not settings:
			continue

		settings = mrinimitable._dict(json.loads(settings))

		# columns -> fields
		settings.fields = settings.columns or []
		settings.pop("columns", None)

		# sort_by + order_by -> order_by
		settings.order_by = (settings.sort_by or "creation") + " " + (settings.order_by or "desc")

		# add_total_row -> add_totals_row
		settings.add_totals_row = settings.add_total_row
		settings.pop("add_total_row", None)

		mrinimitable.db.set_value("Report", report_name, "json", json.dumps(settings))
