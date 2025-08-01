# Copyright (c) 2019, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

# import mrinimitable
from mrinimitable.model.document import Document


class WebsiteRouteRedirect(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		redirect_http_status: DF.Literal["301", "302", "307", "308"]
		source: DF.SmallText
		target: DF.SmallText
	# end: auto-generated types

	pass
