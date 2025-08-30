# Copyright (c) 2020, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import json

import mrinimitable

# import mrinimitable
from mrinimitable.model.document import Document


class DashboardSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		chart_config: DF.Code | None
		user: DF.Link | None
	# end: auto-generated types

	pass


@mrinimitable.whitelist()
def create_dashboard_settings(user):
	if not mrinimitable.db.exists("Dashboard Settings", user):
		doc = mrinimitable.new_doc("Dashboard Settings")
		doc.name = user
		doc.insert(ignore_permissions=True)
		mrinimitable.db.commit()
		return doc


def get_permission_query_conditions(user):
	if not user:
		user = mrinimitable.session.user

	return f"""(`tabDashboard Settings`.name = {mrinimitable.db.escape(user)})"""


@mrinimitable.whitelist()
def save_chart_config(reset, config, chart_name):
	reset = mrinimitable.parse_json(reset)
	doc = mrinimitable.get_doc("Dashboard Settings", mrinimitable.session.user)
	chart_config = mrinimitable.parse_json(doc.chart_config) or {}

	if reset:
		chart_config[chart_name] = {}
	else:
		config = mrinimitable.parse_json(config)
		if chart_name not in chart_config:
			chart_config[chart_name] = {}
		chart_config[chart_name].update(config)

	mrinimitable.db.set_value("Dashboard Settings", mrinimitable.session.user, "chart_config", json.dumps(chart_config))
