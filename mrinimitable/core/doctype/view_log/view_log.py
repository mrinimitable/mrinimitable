# Copyright (c) 2018, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.model.document import Document


class ViewLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		viewed_by: DF.Data | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=180):
		from mrinimitable.query_builder import Interval
		from mrinimitable.query_builder.functions import Now

		table = mrinimitable.qb.DocType("View Log")
		mrinimitable.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))
