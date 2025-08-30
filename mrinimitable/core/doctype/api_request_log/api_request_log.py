# Copyright (c) 2025, Mrinimitable Technologies and contributors
# For license information, please see license.txt

import mrinimitable
from mrinimitable.model.document import Document


class APIRequestLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		method: DF.Data | None
		path: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days: int = 90):
		from mrinimitable.query_builder import Interval
		from mrinimitable.query_builder.functions import Now

		table = mrinimitable.qb.DocType("API Request Log")
		mrinimitable.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))
