# Copyright (c) 2019, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.model.document import Document
from mrinimitable.query_builder import Interval
from mrinimitable.query_builder.functions import Now


class ScheduledJobLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		debug_log: DF.Code | None
		details: DF.Code | None
		scheduled_job_type: DF.Link
		status: DF.Literal["Scheduled", "Complete", "Failed"]
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=90):
		table = mrinimitable.qb.DocType("Scheduled Job Log")
		mrinimitable.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))
