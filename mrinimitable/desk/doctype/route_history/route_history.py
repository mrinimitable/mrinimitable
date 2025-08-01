# Copyright (c) 2022, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.deferred_insert import deferred_insert as _deferred_insert
from mrinimitable.model.document import Document


class RouteHistory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		route: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=30):
		from mrinimitable.query_builder import Interval
		from mrinimitable.query_builder.functions import Now

		table = mrinimitable.qb.DocType("Route History")
		mrinimitable.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@mrinimitable.whitelist()
def deferred_insert(routes):
	routes = [
		{
			"user": mrinimitable.session.user,
			"route": route.get("route"),
			"creation": route.get("creation"),
		}
		for route in mrinimitable.parse_json(routes)
	]

	_deferred_insert("Route History", routes)


@mrinimitable.whitelist()
def frequently_visited_links():
	return mrinimitable.get_all(
		"Route History",
		fields=["route", "count(name) as count"],
		filters={"user": mrinimitable.session.user},
		group_by="route",
		order_by="count desc",
		limit=5,
	)
