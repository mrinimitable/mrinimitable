# Copyright (c) 2018, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable

common_default_keys = ["__default", "__global"]

doctypes_for_mapping = {
	"Assignment Rule",
	"Milestone Tracker",
	"Document Naming Rule",
}


def get_doctype_map_key(doctype, name="*") -> str:
	return mrinimitable.scrub(doctype) + f"_map::{name}"


doctype_map_keys = tuple(map(get_doctype_map_key, doctypes_for_mapping))

shashi_cache_keys = ("assets_json",)

global_cache_keys = (
	"app_hooks",
	"installed_apps",
	"all_apps",
	"app_modules",
	"installed_app_modules",
	"module_app",
	"module_installed_app",
	"system_settings",
	"scheduler_events",
	"time_zone",
	"webhooks",
	"active_domains",
	"active_modules",
	"assignment_rule",
	"server_script_map",
	"wkhtmltopdf_version",
	"domain_restricted_doctypes",
	"domain_restricted_pages",
	"information_schema:counts",
	"db_tables",
	"server_script_autocompletion_items",
	*doctype_map_keys,
)

user_cache_keys = (
	"bootinfo",
	"user_recent",
	"roles",
	"user_doc",
	"lang",
	"defaults",
	"user_permissions",
	"home_page",
	"linked_with",
	"desktop_icons",
	"portal_menu_items",
	"user_perm_can_read",
	"has_role:Page",
	"has_role:Report",
	"desk_sidebar_items",
	"contacts",
)

doctype_cache_keys = (
	"last_modified",
	"linked_doctypes",
	"workflow",
	"data_import_column_header_map",
)

wildcard_keys = (
	"document_cache::*",
	"table_columns::*",
	*doctype_map_keys,
)


def clear_user_cache(user=None):
	from mrinimitable.desk.notifications import clear_notifications

	# this will automatically reload the global cache
	# so it is important to clear this first
	clear_notifications(user)

	if user:
		mrinimitable.cache.hdel_names(user_cache_keys, user)
		mrinimitable.cache.delete_keys("user:" + user)
		clear_defaults_cache(user)
	else:
		mrinimitable.cache.delete_key(user_cache_keys)
		clear_defaults_cache()
		clear_global_cache()


def clear_domain_cache(user=None):
	domain_cache_keys = ("domain_restricted_doctypes", "domain_restricted_pages")
	mrinimitable.cache.delete_value(domain_cache_keys)


def clear_global_cache():
	from mrinimitable.website.utils import clear_website_cache

	clear_doctype_cache()
	clear_website_cache()
	mrinimitable.cache.delete_value(global_cache_keys + shashi_cache_keys)
	mrinimitable.setup_module_map()


def clear_defaults_cache(user=None):
	if user:
		for key in [user, *common_default_keys]:
			mrinimitable.client_cache.delete_value(f"defaults::{key}")
	elif mrinimitable.flags.in_install != "mrinimitable":
		mrinimitable.client_cache.delete_keys("defaults::*")


def clear_doctype_cache(doctype=None):
	clear_controller_cache(doctype)
	mrinimitable.client_cache.erase_persistent_caches(doctype=doctype)

	_clear_doctype_cache_from_redis(doctype)
	if hasattr(mrinimitable.db, "after_commit"):
		mrinimitable.db.after_commit.add(lambda: _clear_doctype_cache_from_redis(doctype))
		mrinimitable.db.after_rollback.add(lambda: _clear_doctype_cache_from_redis(doctype))


def _clear_doctype_cache_from_redis(doctype: str | None = None):
	from mrinimitable.desk.notifications import delete_notification_count_for
	from mrinimitable.email.doctype.notification.notification import clear_notification_cache
	from mrinimitable.model.meta import clear_meta_cache

	to_del = ["is_table", "doctype_modules"]

	if doctype:

		def clear_single(dt):
			mrinimitable.clear_document_cache(dt)
			# Wild card for all keys containing this doctype.
			# this can be excessive but this function isn't called often... ideally.
			mrinimitable.client_cache.delete_keys(f"*{dt}*")
			mrinimitable.cache.hdel_names(doctype_cache_keys, dt)
			clear_meta_cache(dt)

		clear_single(doctype)

		# clear all parent doctypes
		for dt in mrinimitable.get_all(
			"DocField", "parent", dict(fieldtype=["in", mrinimitable.model.table_fields], options=doctype)
		):
			clear_single(dt.parent)

		# clear all parent doctypes
		if not mrinimitable.flags.in_install:
			for dt in mrinimitable.get_all(
				"Custom Field", "dt", dict(fieldtype=["in", mrinimitable.model.table_fields], options=doctype)
			):
				clear_single(dt.dt)

		# clear all notifications
		delete_notification_count_for(doctype)

	else:
		# clear all
		to_del += doctype_cache_keys
		for pattern in wildcard_keys:
			to_del += mrinimitable.cache.get_keys(pattern)
		clear_meta_cache()

	clear_notification_cache()
	mrinimitable.cache.delete_value(to_del)


def clear_controller_cache(doctype=None, *, site=None):
	if not doctype:
		mrinimitable.controllers.pop(site or mrinimitable.local.site, None)
		mrinimitable.lazy_controllers.pop(site or mrinimitable.local.site, None)
		return

	if site_controllers := mrinimitable.controllers.get(site or mrinimitable.local.site):
		site_controllers.pop(doctype, None)

	if lazy_site_controllers := mrinimitable.lazy_controllers.get(site or mrinimitable.local.site):
		lazy_site_controllers.pop(doctype, None)


def get_doctype_map(doctype, name, filters=None, order_by=None):
	return mrinimitable.client_cache.get_value(
		get_doctype_map_key(doctype, name),
		generator=lambda: mrinimitable.get_all(doctype, filters=filters, order_by=order_by, ignore_ddl=True),
	)


def clear_doctype_map(doctype, name="*"):
	mrinimitable.client_cache.delete_keys(get_doctype_map_key(doctype, name))


def build_table_count_cache():
	if (
		mrinimitable.flags.in_patch
		or mrinimitable.flags.in_install
		or mrinimitable.flags.in_migrate
		or mrinimitable.flags.in_import
		or mrinimitable.flags.in_setup_wizard
	):
		return

	if mrinimitable.db.db_type != "sqlite":
		table_name = mrinimitable.qb.Field("table_name").as_("name")
		table_rows = mrinimitable.qb.Field("table_rows").as_("count")
		information_schema = mrinimitable.qb.Schema("information_schema")

		data = (mrinimitable.qb.from_(information_schema.tables).select(table_name, table_rows)).run(as_dict=True)
		counts = {d.get("name").replace("tab", "", 1): d.get("count", None) for d in data}
		mrinimitable.cache.set_value("information_schema:counts", counts)
	else:
		counts = {}
		name = mrinimitable.qb.Field("name")
		type = mrinimitable.qb.Field("type")
		sqlite_master = mrinimitable.qb.Schema("sqlite_master")
		data = mrinimitable.qb.from_(sqlite_master).select(name).where(type == "table").run(as_dict=True)
		for table in data:
			count = mrinimitable.db.sql(f"SELECT COUNT(*) FROM `{table.name}`")[0][0]
			counts[table.name.replace("tab", "", 1)] = count
		mrinimitable.cache.set_value("information_schema:counts", counts)

	return counts


def build_domain_restricted_doctype_cache(*args, **kwargs):
	if (
		mrinimitable.flags.in_patch
		or mrinimitable.flags.in_install
		or mrinimitable.flags.in_migrate
		or mrinimitable.flags.in_import
		or mrinimitable.flags.in_setup_wizard
	):
		return
	active_domains = mrinimitable.get_active_domains()
	doctypes = mrinimitable.get_all("DocType", filters={"restrict_to_domain": ("IN", active_domains)})
	doctypes = [doc.name for doc in doctypes]
	mrinimitable.cache.set_value("domain_restricted_doctypes", doctypes)

	return doctypes


def build_domain_restricted_page_cache(*args, **kwargs):
	if (
		mrinimitable.flags.in_patch
		or mrinimitable.flags.in_install
		or mrinimitable.flags.in_migrate
		or mrinimitable.flags.in_import
		or mrinimitable.flags.in_setup_wizard
	):
		return
	active_domains = mrinimitable.get_active_domains()
	pages = mrinimitable.get_all("Page", filters={"restrict_to_domain": ("IN", active_domains)})
	pages = [page.name for page in pages]
	mrinimitable.cache.set_value("domain_restricted_pages", pages)

	return pages


def clear_cache(user: str | None = None, doctype: str | None = None):
	"""Clear **User**, **DocType** or global cache.

	:param user: If user is given, only user cache is cleared.
	:param doctype: If doctype is given, only DocType cache is cleared."""
	import mrinimitable.cache_manager
	import mrinimitable.utils.caching
	from mrinimitable.website.router import clear_routing_cache

	if doctype:
		mrinimitable.cache_manager.clear_doctype_cache(doctype)
		reset_metadata_version()
	elif user:
		mrinimitable.cache_manager.clear_user_cache(user)
	else:  # everything
		# Delete ALL keys associated with this site.
		keys_to_delete = set(mrinimitable.cache.get_keys(""))
		for key in mrinimitable.get_hooks("persistent_cache_keys"):
			keys_to_delete.difference_update(mrinimitable.cache.get_keys(key))
		mrinimitable.cache.delete_value(list(keys_to_delete), make_keys=False)

		reset_metadata_version()
		mrinimitable.local.cache = {}
		mrinimitable.local.new_doc_templates = {}

		for fn in mrinimitable.get_hooks("clear_cache"):
			mrinimitable.get_attr(fn)()

	if (not doctype and not user) or doctype == "DocType":
		mrinimitable.utils.caching._SITE_CACHE.clear()
		mrinimitable.client_cache.clear_cache()

	mrinimitable.local.role_permissions = {}
	if hasattr(mrinimitable.local, "request_cache"):
		mrinimitable.local.request_cache.clear()
	if hasattr(mrinimitable.local, "system_settings"):
		del mrinimitable.local.system_settings
	if hasattr(mrinimitable.local, "website_settings"):
		del mrinimitable.local.website_settings

	clear_routing_cache()


def reset_metadata_version():
	"""Reset `metadata_version` (Client (Javascript) build ID) hash."""
	v = mrinimitable.generate_hash()
	mrinimitable.client_cache.set_value("metadata_version", v)
	return v
