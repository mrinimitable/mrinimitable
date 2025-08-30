# Copyright (c) 2025, Mrinimitable Technologies and contributors
# For license information, please see license.txt

# import mrinimitable
from mrinimitable.model.document import Document


class SchedulerEvent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		method: DF.Data | None
		scheduled_against: DF.Link
	# end: auto-generated types

	pass
