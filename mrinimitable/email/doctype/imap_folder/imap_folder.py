# Copyright (c) 2021, Mrinimitable Technologies and contributors
# For license information, please see license.txt

# import mrinimitable
from mrinimitable.model.document import Document


class IMAPFolder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		append_to: DF.Link | None
		folder_name: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		uidnext: DF.Data | None
		uidvalidity: DF.Data | None
	# end: auto-generated types

	pass
