# Copyright (c) 2021, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

# import mrinimitable
from mrinimitable.model.document import Document


class UserTypeModule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		module: DF.Link
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types

	pass
