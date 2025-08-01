import mrinimitable
from mrinimitable.utils.caching import site_cache

METATAGS = ("title", "description", "image", "author", "published_on")


class MetaTags:
	def __init__(self, path, context):
		self.path = path
		self.context = context
		self.tags = mrinimitable._dict(self.context.get("metatags") or {})
		self.init_metatags_from_context()
		self.set_opengraph_tags()
		self.set_twitter_tags()
		self.set_meta_published_on()
		self.set_metatags_from_website_route_meta()

	def init_metatags_from_context(self):
		for key in METATAGS:
			if not self.tags.get(key) and self.context.get(key):
				self.tags[key] = self.context[key]

		if not self.tags.get("title"):
			self.tags["title"] = self.context.get("name")

		if self.tags.get("image"):
			self.tags["image"] = mrinimitable.utils.get_url(self.tags["image"])

		self.tags["language"] = mrinimitable.local.lang or "en"

	def set_opengraph_tags(self):
		if "og:type" not in self.tags:
			self.tags["og:type"] = "article"

		for key in METATAGS:
			if self.tags.get(key):
				self.tags["og:" + key] = self.tags.get(key)

	def set_twitter_tags(self):
		for key in METATAGS:
			if self.tags.get(key):
				self.tags["twitter:" + key] = self.tags.get(key)

		if self.tags.get("image"):
			self.tags["twitter:card"] = "summary_large_image"
		else:
			self.tags["twitter:card"] = "summary"

	def set_meta_published_on(self):
		if "published_on" in self.tags:
			self.tags["datePublished"] = self.tags["published_on"]
			del self.tags["published_on"]

	def set_metatags_from_website_route_meta(self):
		"""
		Get meta tags from Website Route meta
		they can override the defaults set above
		"""
		route = self.path
		if route == "":
			# homepage
			route = mrinimitable.get_website_settings("home_page")

		route_exists = route and not route.endswith((".js", ".css")) and has_meta_tags(route)

		if route_exists:
			website_route_meta = mrinimitable.get_doc("Website Route Meta", route)
			for meta_tag in website_route_meta.meta_tags:
				d = meta_tag.get_meta_dict()
				self.tags.update(d)


@site_cache(ttl=10 * 60, maxsize=16)
def has_meta_tags(route):
	return bool(mrinimitable.db.exists("Website Route Meta", route))
