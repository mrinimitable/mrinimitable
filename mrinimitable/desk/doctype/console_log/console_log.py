# Copyright (c) 2020, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.model.document import Document


class ConsoleLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		committed: DF.Check
		script: DF.Code | None
		type: DF.Data | None
	# end: auto-generated types

	def after_delete(self):
		# because on_trash can be bypassed
		mrinimitable.throw(mrinimitable._("Console Logs can not be deleted"))
