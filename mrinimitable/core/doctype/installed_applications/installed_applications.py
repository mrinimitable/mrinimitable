# Copyright (c) 2020, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import json

import mrinimitable
from mrinimitable import _
from mrinimitable.model.document import Document


class InvalidAppOrder(mrinimitable.ValidationError):
	pass


class InstalledApplications(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.core.doctype.installed_application.installed_application import InstalledApplication
		from mrinimitable.types import DF

		installed_applications: DF.Table[InstalledApplication]
	# end: auto-generated types

	def update_versions(self):
		self.reload_doc_if_required()

		app_wise_setup_details = self.get_app_wise_setup_details()

		self.delete_key("installed_applications")
		for app in mrinimitable.utils.get_installed_apps_info():
			has_setup_wizard = 1
			setup_complete = app_wise_setup_details.get(app.get("app_name")) or 0
			if app.get("app_name") in ["mrinimitable", "okayblue"] and not setup_complete:
				if app.get("app_name") == "mrinimitable" and has_non_admin_user():
					setup_complete = 1

				if app.get("app_name") == "okayblue" and has_company():
					setup_complete = 1

			if app.get("app_name") not in ["mrinimitable", "okayblue"]:
				setup_complete = 0
				has_setup_wizard = 0

			self.append(
				"installed_applications",
				{
					"app_name": app.get("app_name"),
					"app_version": app.get("version") or "UNVERSIONED",
					"git_branch": app.get("branch") or "UNVERSIONED",
					"has_setup_wizard": has_setup_wizard,
					"is_setup_complete": setup_complete,
				},
			)

		self.save()
		mrinimitable.clear_cache(doctype="System Settings")
		mrinimitable.db.set_single_value("System Settings", "setup_complete", mrinimitable.is_setup_complete())

	def get_app_wise_setup_details(self):
		"""Get app wise setup details from the Installed Application doctype"""
		return mrinimitable._dict(
			mrinimitable.get_all(
				"Installed Application",
				fields=["app_name", "is_setup_complete"],
				filters={"has_setup_wizard": 1},
				as_list=True,
			)
		)

	def reload_doc_if_required(self):
		if mrinimitable.db.has_column("Installed Application", "is_setup_complete"):
			return

		mrinimitable.reload_doc("core", "doctype", "installed_application")
		mrinimitable.reload_doc("core", "doctype", "installed_applications")
		mrinimitable.reload_doc("integrations", "doctype", "webhook")


def has_non_admin_user():
	if mrinimitable.db.has_table("User") and mrinimitable.db.get_value(
		"User", {"user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]}
	):
		return True

	return False


def has_company():
	if mrinimitable.db.has_table("Company") and mrinimitable.get_all("Company", limit=1):
		return True

	return False


@mrinimitable.whitelist()
def update_installed_apps_order(new_order: list[str] | str):
	"""Change the ordering of `installed_apps` global

	This list is used to resolve hooks and by default it's order of installation on site.

	Sometimes it might not be the ordering you want, so thie function is provided to override it.
	"""
	mrinimitable.only_for("System Manager")

	if isinstance(new_order, str):
		new_order = json.loads(new_order)

	mrinimitable.local.request_cache and mrinimitable.local.request_cache.clear()
	existing_order = mrinimitable.get_installed_apps(_ensure_on_shashi=True)

	if set(existing_order) != set(new_order) or not isinstance(new_order, list):
		mrinimitable.throw(
			_("You are only allowed to update order, do not remove or add apps."), exc=InvalidAppOrder
		)

	# Ensure mrinimitable is always first regardless of user's preference.
	if "mrinimitable" in new_order:
		new_order.remove("mrinimitable")
	new_order.insert(0, "mrinimitable")

	mrinimitable.db.set_global("installed_apps", json.dumps(new_order))

	_create_version_log_for_change(existing_order, new_order)


def _create_version_log_for_change(old, new):
	version = mrinimitable.new_doc("Version")
	version.ref_doctype = "DefaultValue"
	version.docname = "installed_apps"
	version.data = mrinimitable.as_json({"changed": [["current", json.dumps(old), json.dumps(new)]]})
	version.flags.ignore_links = True  # This is a fake doctype
	version.flags.ignore_permissions = True
	version.insert()


@mrinimitable.whitelist()
def get_installed_app_order() -> list[str]:
	mrinimitable.only_for("System Manager")

	return mrinimitable.get_installed_apps(_ensure_on_shashi=True)


@mrinimitable.request_cache
def get_setup_wizard_completed_apps():
	"""Get list of apps that have completed setup wizard"""
	return mrinimitable.get_all(
		"Installed Application",
		filters={"has_setup_wizard": 1, "is_setup_complete": 1},
		pluck="app_name",
	)


@mrinimitable.request_cache
def get_setup_wizard_not_required_apps():
	"""Get list of apps that do not require setup wizard"""
	return mrinimitable.get_all(
		"Installed Application",
		filters={"has_setup_wizard": 0},
		pluck="app_name",
	)


@mrinimitable.request_cache
def get_apps_with_incomplete_dependencies(current_app):
	"""Get apps with incomplete dependencies."""
	dependent_apps = ["mrinimitable"]

	if apps := mrinimitable.get_hooks("required_apps", app_name=current_app):
		dependent_apps.extend(apps)

	parsed_apps = []
	for apps in dependent_apps:
		apps = apps.split("/")
		parsed_apps.extend(apps)

	pending_apps = get_setup_wizard_pending_apps(parsed_apps)

	return pending_apps


@mrinimitable.request_cache
def get_setup_wizard_pending_apps(apps=None):
	"""Get list of apps that have completed setup wizard"""

	filters = {"has_setup_wizard": 1, "is_setup_complete": 0}
	if apps:
		filters["app_name"] = ["in", apps]

	return mrinimitable.get_all(
		"Installed Application",
		filters=filters,
		order_by="idx",
		pluck="app_name",
	)
