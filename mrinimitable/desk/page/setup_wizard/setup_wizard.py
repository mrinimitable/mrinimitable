# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import mrinimitable
from mrinimitable import _
from mrinimitable.core.doctype.installed_applications.installed_applications import get_setup_wizard_completed_apps
from mrinimitable.geo.country_info import get_country_info
from mrinimitable.permissions import AUTOMATIC_ROLES
from mrinimitable.translate import send_translations, set_default_language
from mrinimitable.utils import cint, now, strip
from mrinimitable.utils.password import update_password

from . import install_fixtures


def get_setup_stages(args):  # nosemgrep
	# App setup stage functions should not include mrinimitable.db.commit
	# That is done by mrinimitable after successful completion of all stages
	stages = [
		{
			"status": _("Updating global settings"),
			"fail_msg": _("Failed to update global settings"),
			"tasks": [
				{
					"fn": update_global_settings,
					"args": args,
					"fail_msg": "Failed to update global settings",
					"app_name": "mrinimitable",
				}
			],
		}
	]

	stages += get_stages_hooks(args) + get_setup_complete_hooks(args)

	stages.append(
		{
			# post executing hooks
			"status": _("Wrapping up"),
			"fail_msg": _("Failed to complete setup"),
			"tasks": [{"fn": run_post_setup_complete, "args": args, "fail_msg": "Failed to complete setup"}],
		}
	)

	return stages


@mrinimitable.whitelist()
def setup_complete(args):
	"""Calls hooks for `setup_wizard_complete`, sets home page as `desktop`
	and clears cache. If wizard breaks, calls `setup_wizard_exception` hook"""

	# Setup complete: do not throw an exception, let the user continue to desk
	if mrinimitable.is_setup_complete():
		return {"status": "ok"}

	kwargs = parse_args(sanitize_input(args))
	stages = get_setup_stages(kwargs)
	is_background_task = mrinimitable.conf.get("trigger_site_setup_in_background")

	if is_background_task:
		process_setup_stages.enqueue(stages=stages, user_input=kwargs, is_background_task=True, at_front=True)
		return {"status": "registered"}
	else:
		return process_setup_stages(stages, kwargs)


@mrinimitable.whitelist()
def initialize_system_settings_and_user(system_settings_data, user_data):
	system_settings = mrinimitable.get_single("System Settings")

	if cint(system_settings.setup_complete):
		return

	system_settings_data = parse_args(sanitize_input(system_settings_data))
	system_settings.update(
		{
			"language": system_settings_data.get("language"),
			"country": system_settings_data.get("country"),
			"currency": system_settings_data.get("currency"),
			"time_zone": system_settings_data.get("time_zone"),
		}
	)
	system_settings.save()

	user_data = parse_args(sanitize_input(user_data))
	create_or_update_user(user_data)


@mrinimitable.task()
def process_setup_stages(stages, user_input, is_background_task=False):
	from mrinimitable.utils.telemetry import capture

	setup_wizard_completed_apps = get_setup_wizard_completed_apps()

	capture("initated_server_side", "setup")
	try:
		mrinimitable.flags.in_setup_wizard = True
		current_task = None
		for idx, stage in enumerate(stages):
			mrinimitable.publish_realtime(
				"setup_task",
				{"progress": [idx, len(stages)], "stage_status": stage.get("status")},
				user=mrinimitable.session.user,
			)

			for task in stage.get("tasks"):
				current_task = task
				if task.get("app_name") and task.get("app_name") in setup_wizard_completed_apps:
					continue

				if "mrinimitable" in setup_wizard_completed_apps:
					set_missing_values(task)

				task.get("fn")(task.get("args"))

				if task.get("app_name"):
					enable_setup_wizard_complete(task.get("app_name"))
				else:
					enable_setup_wizard_complete("mrinimitable")
	except Exception:
		handle_setup_exception(user_input)
		message = current_task.get("fail_msg") if current_task else "Failed to complete setup"
		mrinimitable.log_error(title=f"Setup failed: {message}")
		if not is_background_task:
			mrinimitable.response["setup_wizard_failure_message"] = message
			raise
		mrinimitable.publish_realtime(
			"setup_task",
			{"status": "fail", "fail_msg": message},
			user=mrinimitable.session.user,
		)
	else:
		run_setup_success(user_input)
		capture("completed_server_side", "setup")
		if not is_background_task:
			return {"status": "ok"}
		mrinimitable.publish_realtime("setup_task", {"status": "ok"}, user=mrinimitable.session.user)
	finally:
		mrinimitable.flags.in_setup_wizard = False


def set_missing_values(task):
	if task and task.get("args"):
		doc = mrinimitable.get_doc("System Settings")
		task["args"].update(
			{
				"country": doc.country,
				"time_zone": doc.time_zone,
				"time_format": doc.time_format,
				"currency": doc.currency,
			}
		)


def enable_setup_wizard_complete(app_name):
	mrinimitable.db.set_value("Installed Application", {"app_name": app_name}, "is_setup_complete", 1)


def update_global_settings(args):  # nosemgrep
	if args.language and args.language != "English":
		set_default_language(get_language_code(args.lang))
		mrinimitable.db.commit()
	mrinimitable.clear_cache()

	update_system_settings(args)
	create_or_update_user(args)
	set_timezone(args)


def run_post_setup_complete(args):  # nosemgrep
	disable_future_access()
	mrinimitable.db.commit()
	mrinimitable.clear_cache()
	# HACK: due to race condition sometimes old doc stays in cache.
	# Remove this when we have reliable cache reset for docs
	mrinimitable.get_cached_doc("System Settings") and mrinimitable.get_doc("System Settings")


def run_setup_success(args):  # nosemgrep
	for hook in mrinimitable.get_hooks("setup_wizard_success"):
		mrinimitable.get_attr(hook)(args)
	install_fixtures.install()


def get_stages_hooks(args):  # nosemgrep
	stages = []

	installed_apps = mrinimitable.get_installed_apps(_ensure_on_shashi=True)
	for app_name in installed_apps:
		setup_wizard_stages = mrinimitable.get_hooks(app_name=app_name).get("setup_wizard_stages")
		if not setup_wizard_stages:
			continue

		for method in setup_wizard_stages:
			_stages = mrinimitable.get_attr(method)(args)
			update_app_details_in_stages(_stages, app_name)
			stages += _stages

	return stages


def update_app_details_in_stages(_stages, app_name):
	for stage in _stages:
		for key in stage:
			if key != "tasks":
				continue

			for task in stage[key]:
				if task.get("app_name") is None:
					task["app_name"] = app_name


def get_setup_complete_hooks(args):  # nosemgrep
	return [
		{
			"status": "Executing method",
			"fail_msg": "Failed to execute method",
			"tasks": [
				{
					"fn": mrinimitable.get_attr(method),
					"args": args,
					"fail_msg": "Failed to execute method",
					"app_name": method.split(".")[0],
				}
			],
		}
		for method in mrinimitable.get_hooks("setup_wizard_complete")
	]


def handle_setup_exception(args):  # nosemgrep
	mrinimitable.db.rollback()
	if args:
		traceback = mrinimitable.get_traceback(with_context=True)
		print(traceback)
		for hook in mrinimitable.get_hooks("setup_wizard_exception"):
			mrinimitable.get_attr(hook)(traceback, args)


def update_system_settings(args):  # nosemgrep
	if not args.get("country"):
		return

	number_format = get_country_info(args.get("country")).get("number_format", "#,###.##")

	# replace these as float number formats, as they have 0 precision
	# and are currency number formats and not for floats
	if number_format == "#.###":
		number_format = "#.###,##"
	elif number_format == "#,###":
		number_format = "#,###.##"

	system_settings = mrinimitable.get_doc("System Settings", "System Settings")
	system_settings.update(
		{
			"country": args.get("country"),
			"language": get_language_code(args.get("language")) or "en",
			"time_zone": args.get("timezone"),
			"currency": args.get("currency"),
			"float_precision": 3,
			"rounding_method": "Banker's Rounding",
			"date_format": mrinimitable.db.get_value("Country", args.get("country"), "date_format"),
			"time_format": mrinimitable.db.get_value("Country", args.get("country"), "time_format"),
			"number_format": number_format,
			"enable_scheduler": 1 if not mrinimitable.in_test else 0,
			"backup_limit": 3,  # Default for downloadable backups
			"enable_telemetry": cint(args.get("enable_telemetry")),
		}
	)
	system_settings.save()
	if args.get("allow_recording_first_session"):
		mrinimitable.db.set_default("session_recording_start", now())


def create_or_update_user(args):  # nosemgrep
	email = args.get("email")
	if not email:
		return

	first_name, last_name = args.get("full_name", ""), ""
	if " " in first_name:
		first_name, last_name = first_name.split(" ", 1)

	if user := mrinimitable.db.get_value("User", email, ["first_name", "last_name"], as_dict=True):
		if user.first_name != first_name or user.last_name != last_name:
			(
				mrinimitable.qb.update("User")
				.set("first_name", first_name)
				.set("last_name", last_name)
				.set("full_name", args.get("full_name"))
			).run()
	else:
		_mute_emails, mrinimitable.flags.mute_emails = mrinimitable.flags.mute_emails, True

		user = mrinimitable.new_doc("User")
		user.update(
			{
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
			}
		)
		user.append_roles(*_get_default_roles())
		user.append_roles("System Manager")
		user.flags.no_welcome_mail = True
		user.insert()

		mrinimitable.flags.mute_emails = _mute_emails

	if args.get("password"):
		update_password(email, args.get("password"))


def set_timezone(args):  # nosemgrep
	if args.get("timezone"):
		for name in mrinimitable.STANDARD_USERS:
			mrinimitable.db.set_value("User", name, "time_zone", args.get("timezone"))


def parse_args(args):  # nosemgrep
	if not args:
		args = mrinimitable.local.form_dict
	if isinstance(args, str):
		args = json.loads(args)

	args = mrinimitable._dict(args)

	# strip the whitespace
	for key, value in args.items():
		if isinstance(value, str):
			args[key] = strip(value)

	return args


def sanitize_input(args):
	from mrinimitable.utils import is_html, strip_html_tags

	if isinstance(args, str):
		args = json.loads(args)

	for key, value in args.items():
		if is_html(value):
			args[key] = strip_html_tags(value)

	return args


def add_all_roles_to(name):
	user = mrinimitable.get_doc("User", name)
	user.append_roles(*_get_default_roles())
	user.save()


def _get_default_roles() -> set[str]:
	skip_roles = {
		"Administrator",
		"Customer",
		"Supplier",
		"Partner",
		"Employee",
	}.union(AUTOMATIC_ROLES)
	return set(mrinimitable.get_all("Role", pluck="name")) - skip_roles


def disable_future_access():
	mrinimitable.db.set_default("desktop:home_page", "workspace")
	# Enable onboarding after install
	mrinimitable.clear_cache(doctype="System Settings")
	mrinimitable.db.set_single_value("System Settings", "enable_onboarding", 1)
	mrinimitable.db.set_single_value("System Settings", "setup_complete", mrinimitable.is_setup_complete())


@mrinimitable.whitelist()
def load_messages(language):
	"""Load translation messages for given language from all `setup_wizard_requires`
	javascript files"""
	from mrinimitable.translate import get_messages_for_boot

	mrinimitable.clear_cache()
	set_default_language(get_language_code(language))
	mrinimitable.db.commit()
	send_translations(get_messages_for_boot())
	return mrinimitable.local.lang


@mrinimitable.whitelist()
def load_languages():
	language_codes = mrinimitable.db.sql(
		"select language_code, language_name from tabLanguage order by name", as_dict=True
	)
	codes_to_names = {}
	for d in language_codes:
		codes_to_names[d.language_code] = d.language_name
	return {
		"default_language": mrinimitable.db.get_value("Language", mrinimitable.local.lang, "language_name")
		or mrinimitable.local.lang,
		"languages": sorted(mrinimitable.db.sql_list("select language_name from tabLanguage order by name")),
		"codes_to_names": codes_to_names,
	}


@mrinimitable.whitelist()
def load_user_details():
	return {
		"full_name": mrinimitable.cache.hget("full_name", "signup"),
		"email": mrinimitable.cache.hget("email", "signup"),
	}


def prettify_args(args):  # nosemgrep
	# remove attachments
	for key, val in args.items():
		if isinstance(val, str) and "data:image" in val:
			filename = val.split("data:image", 1)[0].strip(", ")
			size = round((len(val) * 3 / 4) / 1048576.0, 2)
			args[key] = f"Image Attached: '{filename}' of size {size} MB"

	pretty_args = []
	pretty_args.extend(f"{key} = {args[key]}" for key in sorted(args))
	return pretty_args


def email_setup_wizard_exception(traceback, args):  # nosemgrep
	if not mrinimitable.conf.setup_wizard_exception_email:
		return

	pretty_args = prettify_args(args)
	message = """

#### Traceback

<pre>{traceback}</pre>

---

#### Setup Wizard Arguments

<pre>{args}</pre>

---

#### Request Headers

<pre>{headers}</pre>

---

#### Basic Information

- **Site:** {site}
- **User:** {user}""".format(
		site=mrinimitable.local.site,
		traceback=traceback,
		args="\n".join(pretty_args),
		user=mrinimitable.session.user,
		headers=mrinimitable.request.headers if mrinimitable.request else "[no request]",
	)

	mrinimitable.sendmail(
		recipients=mrinimitable.conf.setup_wizard_exception_email,
		sender=mrinimitable.session.user,
		subject=f"Setup failed: {mrinimitable.local.site}",
		message=message,
		delayed=False,
	)


def log_setup_wizard_exception(traceback, args):  # nosemgrep
	with open("../logs/setup-wizard.log", "w+") as setup_log:
		setup_log.write(traceback)
		setup_log.write(json.dumps(args))


def get_language_code(lang):
	return mrinimitable.db.get_value("Language", {"language_name": lang})


def enable_twofactor_all_roles():
	all_role = mrinimitable.get_doc("Role", {"role_name": "All"})
	all_role.two_factor_auth = True
	all_role.save(ignore_permissions=True)


def make_records(records, debug=False):
	from mrinimitable import _dict
	from mrinimitable.modules import scrub

	if debug:
		print("make_records: in DEBUG mode")

	# LOG every success and failure
	for record in records:
		doctype = record.get("doctype")
		condition = record.get("__condition")

		if condition and not condition():
			continue

		doc = mrinimitable.new_doc(doctype)
		doc.update(record)

		# ignore mandatory for root
		parent_link_field = "parent_" + scrub(doc.doctype)
		if doc.meta.get_field(parent_link_field) and not doc.get(parent_link_field):
			doc.flags.ignore_mandatory = True

		savepoint = "setup_fixtures_creation"
		try:
			mrinimitable.db.savepoint(savepoint)
			doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
		except Exception as e:
			mrinimitable.clear_last_message()
			mrinimitable.db.rollback(save_point=savepoint)
			exception = record.get("__exception")
			if exception:
				config = _dict(exception)
				if isinstance(e, config.exception):
					config.handler()
				else:
					show_document_insert_error()
			else:
				show_document_insert_error()


def show_document_insert_error():
	print("Document Insert Error")
	print(mrinimitable.get_traceback())
	mrinimitable.log_error("Exception during Setup")
