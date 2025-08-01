# Copyright (c) 2019, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable import _
from mrinimitable.model.document import Document


class GlobalSearchSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.desk.doctype.global_search_doctype.global_search_doctype import GlobalSearchDocType
		from mrinimitable.types import DF

		allowed_in_global_search: DF.Table[GlobalSearchDocType]
	# end: auto-generated types

	def validate(self):
		dts, core_dts, repeated_dts = [], [], []

		for dt in self.allowed_in_global_search:
			if dt.document_type in dts:
				repeated_dts.append(dt.document_type)

			if mrinimitable.get_meta(dt.document_type).module == "Core":
				core_dts.append(dt.document_type)

			dts.append(dt.document_type)

		if core_dts:
			core_dts = ", ".join(mrinimitable.bold(dt) for dt in core_dts)
			mrinimitable.throw(_("Core Modules {0} cannot be searched in Global Search.").format(core_dts))

		if repeated_dts:
			repeated_dts = ", ".join([mrinimitable.bold(dt) for dt in repeated_dts])
			mrinimitable.throw(_("Document Type {0} has been repeated.").format(repeated_dts))

		# reset cache
		mrinimitable.cache.hdel("global_search", "search_priorities")


def get_doctypes_for_global_search():
	def get_from_db():
		doctypes = mrinimitable.get_all("Global Search DocType", fields=["document_type"], order_by="idx ASC")
		return [d.document_type for d in doctypes] or []

	return mrinimitable.cache.hget("global_search", "search_priorities", get_from_db)


@mrinimitable.whitelist()
def reset_global_search_settings_doctypes():
	update_global_search_doctypes()


def update_global_search_doctypes():
	global_search_doctypes = []
	show_message(1, _("Fetching default Global Search documents."))

	installed_apps = [app for app in mrinimitable.get_installed_apps() if app]
	active_domains = [domain for domain in mrinimitable.get_active_domains() if domain]
	active_domains.append("Default")

	for app in installed_apps:
		search_doctypes = mrinimitable.get_hooks(hook="global_search_doctypes", app_name=app)
		if not search_doctypes:
			continue

		for domain in active_domains:
			if search_doctypes.get(domain):
				global_search_doctypes.extend(search_doctypes.get(domain))

	doctype_list = {dt.name for dt in mrinimitable.get_all("DocType")}
	allowed_in_global_search = []

	for dt in global_search_doctypes:
		if dt.get("index") is not None:
			allowed_in_global_search.insert(dt.get("index"), dt.get("doctype"))
			continue

		allowed_in_global_search.append(dt.get("doctype"))

	show_message(2, _("Setting up Global Search documents."))
	global_search_settings = mrinimitable.get_single("Global Search Settings")
	global_search_settings.allowed_in_global_search = []
	for dt in allowed_in_global_search:
		if dt not in doctype_list:
			continue

		global_search_settings.append("allowed_in_global_search", {"document_type": dt})
	global_search_settings.save(ignore_permissions=True)
	show_message(3, "Global Search Documents have been reset.")


def show_message(progress, msg):
	mrinimitable.publish_realtime(
		"global_search_settings",
		{"progress": progress, "total": 3, "msg": msg},
		user=mrinimitable.session.user,
	)
