# Copyright (c) 2022, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import mimetypes
import os
import re
from functools import lru_cache, wraps

import yaml
from werkzeug.wrappers import Response

import mrinimitable
from mrinimitable.apps import get_apps, get_default_path, is_desk_apps
from mrinimitable.model.document import Document
from mrinimitable.utils import (
	cint,
	cstr,
	get_assets_json,
	get_build_version,
	get_system_timezone,
	md_to_html,
)

FRONTMATTER_PATTERN = re.compile(r"^\s*(?:---|\+\+\+)(.*?)(?:---|\+\+\+)\s*(.+)$", re.S | re.M)
H1_TAG_PATTERN = re.compile("<h1>([^<]*)")
IMAGE_TAG_PATTERN = re.compile(r"""<img[^>]*src\s?=\s?['"]([^'"]*)['"]""")
CLEANUP_PATTERN_1 = re.compile(r'[~!@#$%^&*+()<>,."\'\?]')
CLEANUP_PATTERN_2 = re.compile("[:/]")
CLEANUP_PATTERN_3 = re.compile(r"(-)\1+")


def delete_page_cache(path=None):
	if path:
		mrinimitable.cache.delete_value(f"{WEBSITE_PAGE_CACHE_PREFIX}{path}")
	else:
		mrinimitable.cache.delete_keys(WEBSITE_PAGE_CACHE_PREFIX)


def find_first_image(html):
	m = IMAGE_TAG_PATTERN.finditer(html)
	try:
		return next(m).groups()[0]
	except StopIteration:
		return None


def can_cache(no_cache=False):
	if mrinimitable.flags.force_website_cache:
		return True
	if mrinimitable.conf.disable_website_cache or mrinimitable.conf.developer_mode:
		return False
	if getattr(mrinimitable.local, "no_cache", False):
		return False
	if mrinimitable.request and mrinimitable.request.query_string:
		return False
	return not no_cache


def get_comment_list(doctype, name):
	comments = mrinimitable.get_all(
		"Comment",
		fields=["name", "creation", "owner", "comment_email", "comment_by", "content"],
		filters=dict(
			reference_doctype=doctype,
			reference_name=name,
			comment_type="Comment",
		),
		or_filters=[["owner", "=", mrinimitable.session.user], ["published", "=", 1]],
	)

	communications = mrinimitable.get_all(
		"Communication",
		fields=[
			"name",
			"creation",
			"owner",
			"owner as comment_email",
			"sender_full_name as comment_by",
			"content",
			"recipients",
		],
		filters=dict(
			reference_doctype=doctype,
			reference_name=name,
		),
		or_filters=[
			["recipients", "like", f"%{mrinimitable.session.user}%"],
			["cc", "like", f"%{mrinimitable.session.user}%"],
			["bcc", "like", f"%{mrinimitable.session.user}%"],
		],
	)

	return sorted((comments + communications), key=lambda comment: comment["creation"], reverse=True)


def get_home_page():
	if mrinimitable.local.flags.home_page and not mrinimitable.in_test:
		return mrinimitable.local.flags.home_page

	def _get_home_page():
		home_page = None

		# for user
		if mrinimitable.session.user != "Guest":
			# by role
			for role in mrinimitable.get_roles():
				home_page = mrinimitable.db.get_value("Role", role, "home_page")
				if home_page:
					break

			# portal default
			if not home_page:
				home_page = mrinimitable.db.get_single_value("Portal Settings", "default_portal_home")

		# by hooks
		if not home_page:
			home_page = get_home_page_via_hooks()

		# global
		if not home_page:
			home_page = mrinimitable.db.get_single_value("Website Settings", "home_page")

		if not home_page:
			home_page = "login" if mrinimitable.session.user == "Guest" else "me"

		home_page = home_page.strip("/")

		return home_page

	if mrinimitable._dev_server:
		# dont return cached homepage in development
		return _get_home_page()

	return mrinimitable.cache.hget("home_page", mrinimitable.session.user, _get_home_page)


def get_home_page_via_hooks():
	home_page = None

	home_page_method = mrinimitable.get_hooks("get_website_user_home_page")
	if home_page_method:
		home_page = mrinimitable.get_attr(home_page_method[-1])(mrinimitable.session.user)
	elif mrinimitable.get_hooks("website_user_home_page"):
		home_page = mrinimitable.get_hooks("website_user_home_page")[-1]

	if not home_page:
		role_home_page = mrinimitable.get_hooks("role_home_page")
		if role_home_page:
			for role in mrinimitable.get_roles():
				if role in role_home_page:
					home_page = role_home_page[role][-1]
					break

	if not home_page:
		home_page = mrinimitable.get_hooks("home_page")
		if home_page:
			home_page = home_page[-1]

	if home_page:
		home_page = home_page.strip("/")

	return home_page


def get_boot_data():
	from mrinimitable.integrations.mrinimitable_providers.mrinimitablecloud_billing import is_fc_site
	from mrinimitable.locale import get_date_format, get_first_day_of_the_week, get_number_format, get_time_format

	apps = get_apps()

	return {
		"lang": mrinimitable.local.lang or "en",
		"apps_data": {
			"apps": apps or [],
			"is_desk_apps": 1 if bool(is_desk_apps(apps)) else 0,
			"default_path": get_default_path() or "",
		},
		"sysdefaults": {
			"float_precision": cint(mrinimitable.get_system_settings("float_precision")) or 3,
			"date_format": get_date_format(),
			"time_format": get_time_format(),
			"first_day_of_the_week": get_first_day_of_the_week(),
			"number_format": get_number_format().string,
			"currency": mrinimitable.get_system_settings("currency"),
		},
		"time_zone": {
			"system": get_system_timezone(),
			"user": mrinimitable.get_cached_value("User", mrinimitable.session.user, "time_zone")
			or get_system_timezone(),
		},
		"assets_json": get_assets_json(),
		"sitename": mrinimitable.local.site,
		"is_fc_site": 1 if is_fc_site() else 0,
	}


def is_signup_disabled():
	return mrinimitable.get_website_settings("disable_signup")


def cleanup_page_name(title: str) -> str:
	"""make page name from title"""
	if not title:
		return ""

	name = title.lower()
	name = CLEANUP_PATTERN_1.sub("", name)
	name = CLEANUP_PATTERN_2.sub("-", name)
	name = "-".join(name.split())
	# replace repeating hyphens
	name = CLEANUP_PATTERN_3.sub(r"\1", name)
	return name[:140]


def abs_url(path):
	"""Deconstructs and Reconstructs a URL into an absolute URL or a URL relative from root '/'"""
	if not path:
		return
	if path.startswith("http://") or path.startswith("https://"):
		return path
	if path.startswith("tel:"):
		return path
	if path.startswith("data:"):
		return path
	if not path.startswith("/"):
		path = "/" + path
	return path


def get_toc(route, url_prefix=None, app=None):
	"""Insert full index (table of contents) for {index} tag"""

	full_index = get_full_index(app=app)

	return mrinimitable.get_template("templates/includes/full_index.html").render(
		{"full_index": full_index, "url_prefix": url_prefix or "/", "route": route.rstrip("/")}
	)


def get_next_link(route, url_prefix=None, app=None):
	# insert next link
	next_item = None
	route = route.rstrip("/")
	children_map = get_full_index(app=app)
	parent_route = os.path.dirname(route)
	children = children_map.get(parent_route, None)

	if parent_route and children:
		for i, c in enumerate(children):
			if c.route == route and i < (len(children) - 1):
				next_item = children[i + 1]
				next_item.url_prefix = url_prefix or "/"

	if next_item:
		if next_item.route and next_item.title:
			return (
				'<p class="btn-next-wrapper">'
				+ mrinimitable._("Next")
				+ ': <a class="btn-next" href="{url_prefix}{route}">{title}</a></p>'
			).format(**next_item)
	return ""


def get_full_index(route=None, app=None):
	"""Return full index of the website for www upto the n-th level."""
	from mrinimitable.website.router import get_pages

	if not mrinimitable.local.flags.children_map:

		def _build():
			children_map = {}
			added = []
			pages = get_pages(app=app)

			# make children map
			for route, page_info in pages.items():
				parent_route = os.path.dirname(route)
				if parent_route not in added:
					children_map.setdefault(parent_route, []).append(page_info)

			# order as per index if present
			for route, children in children_map.items():
				if route not in pages:
					# no parent (?)
					continue

				page_info = pages[route]
				if page_info.index or ("index" in page_info.template):
					new_children = []
					page_info.extn = ""
					for name in page_info.index or []:
						child_route = page_info.route + "/" + name
						if child_route in pages:
							if child_route not in added:
								new_children.append(pages[child_route])
								added.append(child_route)

					# add remaining pages not in index.txt
					_children = sorted(children, key=lambda x: os.path.basename(x.route))

					for child_route in _children:
						if child_route not in new_children:
							if child_route not in added:
								new_children.append(child_route)
								added.append(child_route)

					children_map[route] = new_children

			return children_map

		children_map = mrinimitable.cache.get_value("website_full_index", _build)

		mrinimitable.local.flags.children_map = children_map

	return mrinimitable.local.flags.children_map


def extract_title(source, path):
	"""Return title from `&lt;!-- title --&gt;` or &lt;h1&gt; or path."""
	title = extract_comment_tag(source, "title")

	if not title and "<h1>" in source:
		# extract title from h1
		match = H1_TAG_PATTERN.search(source).group()
		title_content = match.strip()[:300]
		if "{{" not in title_content:
			title = title_content

	if not title:
		# make title from name
		title = (
			os.path.basename(
				path.rsplit(
					".",
				)[0].rstrip("/")
			)
			.replace("_", " ")
			.replace("-", " ")
			.title()
		)

	return title


def extract_comment_tag(source: str, tag: str):
	"""Extract custom tags in comments from source.

	:param source: raw template source in HTML
	:param title: tag to search, example "title"
	"""
	matched_pattern = re.search(f"<!-- {tag}:([^>]*) -->", source)
	return matched_pattern.groups()[0].strip() if matched_pattern else None


def get_html_content_based_on_type(doc, fieldname, content_type):
	"""
	Set content based on content_type
	"""
	content = doc.get(fieldname)

	if content_type == "Markdown":
		content = md_to_html(doc.get(fieldname + "_md"))
	elif content_type == "HTML":
		content = doc.get(fieldname + "_html")

	if content is None:
		content = ""

	return content


def clear_cache(path=None):
	"""Clear website caches
	:param path: (optional) for the given path"""
	from mrinimitable.website.router import clear_routing_cache

	clear_routing_cache()

	keys = [
		"website_generator_routes",
		"website_pages",
		"website_full_index",
		"languages_with_name",
		"languages",
		"website_404",
	]

	if path:
		mrinimitable.cache.hdel("website_redirects", path)
		delete_page_cache(path)
	else:
		mrinimitable.clear_cache("Guest")
		delete_page_cache()
		keys += [
			"portal_menu_items",
			"home_page",
			"website_route_rules",
			"doctypes_with_web_view",
			"website_redirects",
		]

	mrinimitable.cache.delete_value(keys)

	for method in mrinimitable.get_hooks("website_clear_cache"):
		mrinimitable.get_attr(method)(path)


def clear_website_cache(path=None):
	clear_cache(path)


def get_frontmatter(string):
	"Reference: https://github.com/jonbeebe/frontmatter"
	frontmatter = ""
	body = ""
	result = FRONTMATTER_PATTERN.search(string)

	if result:
		frontmatter = result.group(1)
		body = result.group(2)

	return {
		"attributes": yaml.safe_load(frontmatter) if frontmatter else "",
		"body": body,
	}


def get_sidebar_items(parent_sidebar, basepath=None):
	import mrinimitable.www.list

	sidebar_items = []

	hooks = mrinimitable.get_hooks("look_for_sidebar_json")
	look_for_sidebar_json = hooks[0] if hooks else mrinimitable.flags.look_for_sidebar

	if basepath and look_for_sidebar_json:
		sidebar_items = get_sidebar_items_from_sidebar_file(basepath, look_for_sidebar_json)

	if not sidebar_items and parent_sidebar:
		sidebar_items = mrinimitable.get_all(
			"Website Sidebar Item",
			filters=dict(parent=parent_sidebar),
			fields=["title", "route", "`group`"],
			order_by="idx asc",
		)

	if not sidebar_items:
		sidebar_items = get_portal_sidebar_items()

	return sidebar_items


def get_portal_sidebar_items():
	sidebar_items = mrinimitable.cache.hget("portal_menu_items", mrinimitable.session.user)
	if sidebar_items is None:
		sidebar_items = []
		roles = mrinimitable.get_roles()
		portal_settings = mrinimitable.get_doc("Portal Settings", "Portal Settings")

		def add_items(sidebar_items, items):
			for d in items:
				if d.get("enabled") and ((not d.get("role")) or d.get("role") in roles):
					sidebar_items.append(d.as_dict() if isinstance(d, Document) else d)

		if not portal_settings.hide_standard_menu:
			add_items(sidebar_items, portal_settings.get("menu"))

		if portal_settings.custom_menu:
			add_items(sidebar_items, portal_settings.get("custom_menu"))

		items_via_hooks = mrinimitable.get_hooks("portal_menu_items")
		if items_via_hooks:
			for i in items_via_hooks:
				i["enabled"] = 1
			add_items(sidebar_items, items_via_hooks)

		mrinimitable.cache.hset("portal_menu_items", mrinimitable.session.user, sidebar_items)

	return sidebar_items


def get_sidebar_items_from_sidebar_file(basepath, look_for_sidebar_json):
	sidebar_items = []
	sidebar_json_path = get_sidebar_json_path(basepath, look_for_sidebar_json)
	if not sidebar_json_path:
		return sidebar_items

	with open(sidebar_json_path) as sidebarfile:
		try:
			sidebar_json = sidebarfile.read()
			sidebar_items = json.loads(sidebar_json)
		except json.decoder.JSONDecodeError:
			mrinimitable.throw("Invalid Sidebar JSON at " + sidebar_json_path)

	return sidebar_items


def get_sidebar_json_path(path, look_for=False):
	"""Get _sidebar.json path from directory path
	:param path: path of the current diretory
	:param look_for: if True, look for _sidebar.json going upwards from given path
	:return: _sidebar.json path
	"""
	if os.path.split(path)[1] == "www" or path == "/" or not path:
		return ""

	sidebar_json_path = os.path.join(path, "_sidebar.json")
	if os.path.exists(sidebar_json_path):
		return sidebar_json_path
	else:
		if look_for:
			return get_sidebar_json_path(os.path.split(path)[0], look_for)
		else:
			return ""


WEBSITE_PAGE_CACHE_PREFIX = "website_page::"


def cache_html(func):
	@wraps(func)
	def cache_html_decorator(*args, **kwargs):
		cache_key = f"{WEBSITE_PAGE_CACHE_PREFIX}{args[0].path}"

		cache_headers = {"Cache-Control": "private,max-age=300,stale-while-revalidate=10800"}
		no_cache = mrinimitable.request and mrinimitable.request.cache_control.no_cache
		if can_cache(no_cache):
			html = None
			page_cache = mrinimitable.cache.get_value(cache_key)
			if page_cache and mrinimitable.local.lang in page_cache:
				html = page_cache[mrinimitable.local.lang]
			if html:
				mrinimitable.local.response.from_cache = True
				mrinimitable.local.response_headers.update(cache_headers)
				return html
		html = func(*args, **kwargs)
		context = args[0].context
		if can_cache(context.no_cache):
			page_cache = mrinimitable.cache.get_value(cache_key) or {}
			page_cache[mrinimitable.local.lang] = html
			mrinimitable.cache.set_value(cache_key, page_cache, expires_in_sec=30 * 60)
			mrinimitable.local.response_headers.update(cache_headers)

		return html

	return cache_html_decorator


def build_response(path, data, http_status_code, headers: dict | None = None):
	# build response
	response = Response()
	response.data = set_content_type(response, data, path)
	response.status_code = http_status_code
	response.headers["X-Page-Name"] = cstr(cstr(path).encode("ascii", errors="xmlcharrefreplace"))
	response.headers["X-From-Cache"] = mrinimitable.local.response.from_cache or False

	if http_status_code != 404:
		add_preload_for_bundled_assets(response)

	if headers:
		for key, val in headers.items():
			response.headers[key] = cstr(cstr(val).encode("ascii", errors="xmlcharrefreplace"))

	return response


def set_content_type(response, data, path):
	if isinstance(data, dict):
		response.mimetype = "application/json"
		data = json.dumps(data)
		return data

	response.mimetype = "text/html"

	# ignore paths ending with .com to avoid unnecessary download
	# https://bugs.python.org/issue22347
	if "." in path and not path.endswith(".com"):
		content_type, encoding = mimetypes.guess_type(path)
		if content_type:
			response.mimetype = content_type
			if encoding:
				response.charset = encoding

	return data


def add_preload_for_bundled_assets(response):
	links = [f"<{css}>; rel=preload; as=style" for css in mrinimitable.local.preload_assets["style"]]
	links.extend(f"<{js}>; rel=preload; as=script" for js in mrinimitable.local.preload_assets["script"])

	version = get_build_version()
	links.extend(
		f"<{svg}?v={version}>; rel=preload; as=fetch; crossorigin"
		for svg in mrinimitable.local.preload_assets["icons"]
	)

	if links:
		response.headers["Link"] = ",".join(links)


@lru_cache
def is_binary_file(path):
	# ref: https://stackoverflow.com/a/7392391/10309266
	textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})
	with open(path, "rb") as f:
		content = f.read(1024)
		return bool(content.translate(None, textchars))
