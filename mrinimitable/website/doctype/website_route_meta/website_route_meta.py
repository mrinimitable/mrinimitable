# Copyright (c) 2019, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

from mrinimitable.model.document import Document


class WebsiteRouteMeta(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF
		from mrinimitable.website.doctype.website_meta_tag.website_meta_tag import WebsiteMetaTag

		meta_tags: DF.Table[WebsiteMetaTag]
	# end: auto-generated types

	def autoname(self):
		if self.name and self.name.startswith("/"):
			self.name = self.name[1:]

	def clear_cache(self):
		from mrinimitable.website.website_components.metatags import has_meta_tags

		has_meta_tags.clear_cache()
		return super().clear_cache()
