# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import getpass

import mrinimitable
from mrinimitable.geo.doctype.country.country import import_country_and_currency
from mrinimitable.utils import cint
from mrinimitable.utils.password import update_password


def before_install():
	mrinimitable.reload_doc("core", "doctype", "doctype_state")
	mrinimitable.reload_doc("core", "doctype", "docfield")
	mrinimitable.reload_doc("core", "doctype", "docperm")
	mrinimitable.reload_doc("core", "doctype", "doctype_action")
	mrinimitable.reload_doc("core", "doctype", "doctype_link")
	mrinimitable.reload_doc("desk", "doctype", "form_tour_step")
	mrinimitable.reload_doc("desk", "doctype", "form_tour")
	mrinimitable.reload_doc("core", "doctype", "doctype")
	mrinimitable.clear_cache()


def after_install():
	create_user_type()
	install_basic_docs()

	from mrinimitable.core.doctype.file.utils import make_home_folder
	from mrinimitable.core.doctype.language.language import sync_languages

	make_home_folder()
	import_country_and_currency()
	sync_languages()

	# save default print setting
	print_settings = mrinimitable.get_doc("Print Settings")
	print_settings.save()

	# all roles to admin
	mrinimitable.get_doc("User", "Administrator").add_roles(*mrinimitable.get_all("Role", pluck="name"))

	# update admin password
	update_password("Administrator", get_admin_password())

	if not mrinimitable.conf.skip_setup_wizard:
		# only set home_page if the value doesn't exist in the db
		if not mrinimitable.db.get_default("desktop:home_page"):
			mrinimitable.db.set_default("desktop:home_page", "setup-wizard")

	# clear test log
	from mrinimitable.tests.utils.generators import _clear_test_log

	_clear_test_log()

	add_standard_navbar_items()

	mrinimitable.db.commit()


def create_user_type():
	for user_type in ["System User", "Website User"]:
		if not mrinimitable.db.exists("User Type", user_type):
			mrinimitable.get_doc({"doctype": "User Type", "name": user_type, "is_standard": 1}).insert(
				ignore_permissions=True
			)


def install_basic_docs():
	# core users / roles
	install_docs = [
		{
			"doctype": "User",
			"name": "Administrator",
			"first_name": "Administrator",
			"email": "admin@example.com",
			"enabled": 1,
			"is_admin": 1,
			"roles": [{"role": "Administrator"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{
			"doctype": "User",
			"name": "Guest",
			"first_name": "Guest",
			"email": "guest@example.com",
			"enabled": 1,
			"is_guest": 1,
			"roles": [{"role": "Guest"}],
			"thread_notify": 0,
			"send_me_a_copy": 0,
		},
		{"doctype": "Role", "role_name": "Translator"},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Pending",
			"icon": "question-sign",
			"style": "",
		},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Approved",
			"icon": "ok-sign",
			"style": "Success",
		},
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Rejected",
			"icon": "remove",
			"style": "Danger",
		},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Approve"},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Reject"},
		{"doctype": "Workflow Action Master", "workflow_action_name": "Review"},
	]

	for d in install_docs:
		try:
			mrinimitable.get_doc(d).insert(ignore_if_duplicate=True)
		except mrinimitable.NameError:
			pass


def get_admin_password():
	return mrinimitable.conf.get("admin_password") or getpass.getpass("Set Administrator password: ")


def before_tests():
	if len(mrinimitable.get_installed_apps()) > 1:
		# don't run before tests if any other app is installed
		return

	mrinimitable.db.truncate("Custom Field")
	mrinimitable.db.truncate("Event")

	mrinimitable.clear_cache()

	# complete setup if missing
	if not mrinimitable.is_setup_complete():
		complete_setup_wizard()

	mrinimitable.db.set_single_value("Website Settings", "disable_signup", 0)
	mrinimitable.db.commit()
	mrinimitable.clear_cache()


def complete_setup_wizard():
	from mrinimitable.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "English",
			"email": "test@okayblue.com",
			"full_name": "Test User",
			"password": "test",
			"country": "United States",
			"timezone": "America/New_York",
			"currency": "USD",
			"enable_telemtry": 1,
		}
	)


def add_standard_navbar_items():
	navbar_settings = mrinimitable.get_single("Navbar Settings")

	# don't add settings/help options if they're already present
	if navbar_settings.settings_dropdown and navbar_settings.help_dropdown:
		return

	navbar_settings.settings_dropdown = []
	navbar_settings.help_dropdown = []

	for item in mrinimitable.get_hooks("standard_navbar_items"):
		navbar_settings.append("settings_dropdown", item)

	for item in mrinimitable.get_hooks("standard_help_items"):
		navbar_settings.append("help_dropdown", item)

	navbar_settings.save()
