# Copyright (c) 2021, Mrinimitable Technologies and contributors
# For license information, please see license.txt

# import mrinimitable
from mrinimitable.model.document import Document


class DocTypeState(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		color: DF.Literal[
			"Blue", "Cyan", "Gray", "Green", "Light Blue", "Orange", "Pink", "Purple", "Red", "Yellow"
		]
		custom: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		title: DF.Data
	# end: auto-generated types

	pass
