# Copyright (c) 2023, Mrinimitable Technologies and contributors
# For license information, please see license.txt

import mrinimitable
from mrinimitable.model.document import Document


class UTMCampaign(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		campaign_description: DF.SmallText | None
		slug: DF.Data | None
	# end: auto-generated types

	def before_save(self):
		if self.slug:
			self.slug = mrinimitable.utils.slug(self.slug)
