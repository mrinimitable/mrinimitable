# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import mrinimitable
from mrinimitable.model.document import Document


class ClientScript(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		dt: DF.Link
		enabled: DF.Check
		module: DF.Link | None
		script: DF.Code | None
		view: DF.Literal["List", "Form"]
	# end: auto-generated types

	def on_update(self):
		mrinimitable.clear_cache(doctype=self.dt)

	def on_trash(self):
		mrinimitable.clear_cache(doctype=self.dt)
