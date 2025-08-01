# Copyright (c) 2019, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

# import mrinimitable
from mrinimitable.model.document import Document


class ContactPhone(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		is_primary_mobile_no: DF.Check
		is_primary_phone: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		phone: DF.Data
	# end: auto-generated types

	pass
