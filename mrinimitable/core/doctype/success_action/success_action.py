# Copyright (c) 2018, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

from mrinimitable.model.document import Document


class SuccessAction(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		action_timeout: DF.Int
		first_success_message: DF.Data
		message: DF.Data
		next_actions: DF.Data | None
		ref_doctype: DF.Link
	# end: auto-generated types

	pass
