import os

from . import __version__ as app_version

app_name = "mrinimitable"
app_title = "Mrinimitable Framework"
app_publisher = "Mrinimitable Technologies"
app_description = "Full stack web framework with Python, Javascript, MariaDB, Redis, Node"
app_license = "MIT"
app_logo_url = "/assets/mrinimitable/images/mrinimitable-framework-logo.svg"
develop_version = "15.x.x-develop"
app_home = "/app/build"

app_email = "developers@mrinimitable.io"

before_install = "mrinimitable.utils.install.before_install"
after_install = "mrinimitable.utils.install.after_install"

page_js = {"setup-wizard": "public/js/mrinimitable/setup_wizard.js"}

# website
app_include_js = [
	"libs.bundle.js",
	"desk.bundle.js",
	"list.bundle.js",
	"form.bundle.js",
	"controls.bundle.js",
	"report.bundle.js",
	"telemetry.bundle.js",
	"billing.bundle.js",
]

app_include_css = [
	"desk.bundle.css",
	"report.bundle.css",
]
app_include_icons = [
	"/assets/mrinimitable/icons/timeless/icons.svg",
	"/assets/mrinimitable/icons/espresso/icons.svg",
]

doctype_js = {
	"Web Page": "public/js/mrinimitable/utils/web_template.js",
	"Website Settings": "public/js/mrinimitable/utils/web_template.js",
}

web_include_js = ["website_script.js"]
web_include_css = []
web_include_icons = [
	"/assets/mrinimitable/icons/timeless/icons.svg",
	"/assets/mrinimitable/icons/espresso/icons.svg",
]

email_css = ["email.bundle.css"]

website_route_rules = [
	{"from_route": "/kb/<category>", "to_route": "Help Article"},
	{"from_route": "/profile", "to_route": "me"},
	{"from_route": "/app/<path:app_path>", "to_route": "app"},
]

website_redirects = [
	{"source": r"/desk(.*)", "target": r"/app\1"},
]

base_template = "templates/base.html"

write_file_keys = ["file_url", "file_name"]

notification_config = "mrinimitable.core.notifications.get_notification_config"

before_tests = "mrinimitable.utils.install.before_tests"

email_append_to = ["Event", "ToDo", "Communication"]

calendars = ["Event"]

# login

on_session_creation = [
	"mrinimitable.core.doctype.activity_log.feed.login_feed",
	"mrinimitable.core.doctype.user.user.notify_admin_access_to_system_manager",
]

on_login = "mrinimitable.desk.doctype.note.note._get_unseen_notes"
on_logout = "mrinimitable.core.doctype.session_default_settings.session_default_settings.clear_session_defaults"

# PDF
pdf_header_html = "mrinimitable.utils.pdf.pdf_header_html"
pdf_body_html = "mrinimitable.utils.pdf.pdf_body_html"
pdf_footer_html = "mrinimitable.utils.pdf.pdf_footer_html"

# permissions

permission_query_conditions = {
	"Event": "mrinimitable.desk.doctype.event.event.get_permission_query_conditions",
	"ToDo": "mrinimitable.desk.doctype.todo.todo.get_permission_query_conditions",
	"User": "mrinimitable.core.doctype.user.user.get_permission_query_conditions",
	"Dashboard Settings": "mrinimitable.desk.doctype.dashboard_settings.dashboard_settings.get_permission_query_conditions",
	"Notification Log": "mrinimitable.desk.doctype.notification_log.notification_log.get_permission_query_conditions",
	"Dashboard": "mrinimitable.desk.doctype.dashboard.dashboard.get_permission_query_conditions",
	"Dashboard Chart": "mrinimitable.desk.doctype.dashboard_chart.dashboard_chart.get_permission_query_conditions",
	"Number Card": "mrinimitable.desk.doctype.number_card.number_card.get_permission_query_conditions",
	"Notification Settings": "mrinimitable.desk.doctype.notification_settings.notification_settings.get_permission_query_conditions",
	"Note": "mrinimitable.desk.doctype.note.note.get_permission_query_conditions",
	"Kanban Board": "mrinimitable.desk.doctype.kanban_board.kanban_board.get_permission_query_conditions",
	"Contact": "mrinimitable.contacts.address_and_contact.get_permission_query_conditions_for_contact",
	"Address": "mrinimitable.contacts.address_and_contact.get_permission_query_conditions_for_address",
	"Communication": "mrinimitable.core.doctype.communication.communication.get_permission_query_conditions_for_communication",
	"Workflow Action": "mrinimitable.workflow.doctype.workflow_action.workflow_action.get_permission_query_conditions",
	"Prepared Report": "mrinimitable.core.doctype.prepared_report.prepared_report.get_permission_query_condition",
	"File": "mrinimitable.core.doctype.file.file.get_permission_query_conditions",
	"User Invitation": "mrinimitable.core.doctype.user_invitation.user_invitation.get_permission_query_conditions",
}

has_permission = {
	"Event": "mrinimitable.desk.doctype.event.event.has_permission",
	"ToDo": "mrinimitable.desk.doctype.todo.todo.has_permission",
	"Note": "mrinimitable.desk.doctype.note.note.has_permission",
	"User": "mrinimitable.core.doctype.user.user.has_permission",
	"Dashboard Chart": "mrinimitable.desk.doctype.dashboard_chart.dashboard_chart.has_permission",
	"Number Card": "mrinimitable.desk.doctype.number_card.number_card.has_permission",
	"Kanban Board": "mrinimitable.desk.doctype.kanban_board.kanban_board.has_permission",
	"Contact": "mrinimitable.contacts.address_and_contact.has_permission",
	"Address": "mrinimitable.contacts.address_and_contact.has_permission",
	"Communication": "mrinimitable.core.doctype.communication.communication.has_permission",
	"Workflow Action": "mrinimitable.workflow.doctype.workflow_action.workflow_action.has_permission",
	"File": "mrinimitable.core.doctype.file.file.has_permission",
	"Prepared Report": "mrinimitable.core.doctype.prepared_report.prepared_report.has_permission",
	"Notification Settings": "mrinimitable.desk.doctype.notification_settings.notification_settings.has_permission",
	"User Invitation": "mrinimitable.core.doctype.user_invitation.user_invitation.has_permission",
}

has_website_permission = {"Address": "mrinimitable.contacts.doctype.address.address.has_website_permission"}

jinja = {
	"methods": "mrinimitable.utils.jinja_globals",
	"filters": [
		"mrinimitable.utils.data.global_date_format",
		"mrinimitable.utils.markdown",
		"mrinimitable.website.utils.abs_url",
	],
}

standard_queries = {"User": "mrinimitable.core.doctype.user.user.user_query"}

doc_events = {
	"*": {
		"on_update": [
			"mrinimitable.desk.notifications.clear_doctype_notifications",
			"mrinimitable.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"mrinimitable.core.doctype.file.utils.attach_files_to_document",
			"mrinimitable.automation.doctype.assignment_rule.assignment_rule.apply",
			"mrinimitable.automation.doctype.assignment_rule.assignment_rule.update_due_date",
			"mrinimitable.core.doctype.user_type.user_type.apply_permissions_for_non_standard_user_type",
			"mrinimitable.core.doctype.permission_log.permission_log.make_perm_log",
			"mrinimitable.search.sqlite_search.update_doc_index",
		],
		"after_rename": "mrinimitable.desk.notifications.clear_doctype_notifications",
		"on_cancel": [
			"mrinimitable.desk.notifications.clear_doctype_notifications",
			"mrinimitable.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"mrinimitable.automation.doctype.assignment_rule.assignment_rule.apply",
		],
		"on_trash": [
			"mrinimitable.desk.notifications.clear_doctype_notifications",
			"mrinimitable.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"mrinimitable.search.sqlite_search.delete_doc_index",
		],
		"on_update_after_submit": [
			"mrinimitable.workflow.doctype.workflow_action.workflow_action.process_workflow_actions",
			"mrinimitable.automation.doctype.assignment_rule.assignment_rule.apply",
			"mrinimitable.automation.doctype.assignment_rule.assignment_rule.update_due_date",
			"mrinimitable.core.doctype.file.utils.attach_files_to_document",
		],
		"on_change": [
			"mrinimitable.automation.doctype.milestone_tracker.milestone_tracker.evaluate_milestone",
		],
		"after_delete": ["mrinimitable.core.doctype.permission_log.permission_log.make_perm_log"],
	},
	"Event": {
		"after_insert": "mrinimitable.integrations.doctype.google_calendar.google_calendar.insert_event_in_google_calendar",
		"on_update": "mrinimitable.integrations.doctype.google_calendar.google_calendar.update_event_in_google_calendar",
		"on_trash": "mrinimitable.integrations.doctype.google_calendar.google_calendar.delete_event_from_google_calendar",
	},
	"Contact": {
		"after_insert": "mrinimitable.integrations.doctype.google_contacts.google_contacts.insert_contacts_to_google_contacts",
		"on_update": "mrinimitable.integrations.doctype.google_contacts.google_contacts.update_contacts_to_google_contacts",
	},
	"DocType": {
		"on_update": "mrinimitable.cache_manager.build_domain_restricted_doctype_cache",
	},
	"Page": {
		"on_update": "mrinimitable.cache_manager.build_domain_restricted_page_cache",
	},
}

scheduler_events = {
	"cron": {
		# 5 minutes
		"0/5 * * * *": [
			"mrinimitable.email.doctype.notification.notification.trigger_offset_alerts",
		],
		# 15 minutes
		"0/15 * * * *": [
			"mrinimitable.email.doctype.email_account.email_account.notify_unreplied",
			"mrinimitable.utils.global_search.sync_global_search",
			"mrinimitable.deferred_insert.save_to_db",
			"mrinimitable.automation.doctype.reminder.reminder.send_reminders",
			"mrinimitable.model.utils.link_count.update_link_count",
			"mrinimitable.search.sqlite_search.build_index_if_not_exists",
		],
		# 10 minutes
		"0/10 * * * *": [
			"mrinimitable.email.doctype.email_account.email_account.pull",
		],
		# Hourly but offset by 30 minutes
		"30 * * * *": [],
		# Daily but offset by 45 minutes
		"45 0 * * *": [],
	},
	"all": [
		"mrinimitable.email.queue.flush",
		"mrinimitable.email.queue.retry_sending_emails",
		"mrinimitable.monitor.flush",
		"mrinimitable.integrations.doctype.google_calendar.google_calendar.sync",
	],
	"hourly": [],
	# Maintenance queue happen roughly once an hour but don't align with wall-clock time of *:00
	# Use these for when you don't care about when the job runs but just need some guarantee for
	# frequency.
	"hourly_maintenance": [
		"mrinimitable.model.utils.user_settings.sync_user_settings",
		"mrinimitable.desk.page.backups.backups.delete_downloadable_backups",
		"mrinimitable.desk.form.document_follow.send_hourly_updates",
		"mrinimitable.website.doctype.personal_data_deletion_request.personal_data_deletion_request.process_data_deletion_request",
		"mrinimitable.core.doctype.prepared_report.prepared_report.expire_stalled_report",
		"mrinimitable.twofactor.delete_all_barcodes_for_users",
		"mrinimitable.oauth.delete_oauth2_data",
		"mrinimitable.website.doctype.web_page.web_page.check_publish_status",
	],
	"daily": [
		"mrinimitable.desk.doctype.event.event.send_event_digest",
		"mrinimitable.email.doctype.notification.notification.trigger_daily_alerts",
		"mrinimitable.desk.form.document_follow.send_daily_updates",
	],
	"daily_long": [],
	"daily_maintenance": [
		"mrinimitable.email.doctype.auto_email_report.auto_email_report.send_daily",
		"mrinimitable.desk.notifications.clear_notifications",
		"mrinimitable.sessions.clear_expired_sessions",
		"mrinimitable.website.doctype.personal_data_deletion_request.personal_data_deletion_request.remove_unverified_record",
		"mrinimitable.automation.doctype.auto_repeat.auto_repeat.make_auto_repeat_entry",
		"mrinimitable.core.doctype.log_settings.log_settings.run_log_clean_up",
		"mrinimitable.core.doctype.user_invitation.user_invitation.mark_expired_invitations",
	],
	"weekly_long": [
		"mrinimitable.desk.form.document_follow.send_weekly_updates",
		"mrinimitable.utils.change_log.check_for_update",
		"mrinimitable.desk.doctype.changelog_feed.changelog_feed.fetch_changelog_feed",
	],
	"monthly": [
		"mrinimitable.email.doctype.auto_email_report.auto_email_report.send_monthly",
	],
}

sounds = [
	{"name": "email", "src": "/assets/mrinimitable/sounds/email.mp3", "volume": 0.1},
	{"name": "submit", "src": "/assets/mrinimitable/sounds/submit.mp3", "volume": 0.1},
	{"name": "cancel", "src": "/assets/mrinimitable/sounds/cancel.mp3", "volume": 0.1},
	{"name": "delete", "src": "/assets/mrinimitable/sounds/delete.mp3", "volume": 0.05},
	{"name": "click", "src": "/assets/mrinimitable/sounds/click.mp3", "volume": 0.05},
	{"name": "error", "src": "/assets/mrinimitable/sounds/error.mp3", "volume": 0.1},
	{"name": "alert", "src": "/assets/mrinimitable/sounds/alert.mp3", "volume": 0.2},
	# {"name": "chime", "src": "/assets/mrinimitable/sounds/chime.mp3"},
]

setup_wizard_exception = [
	"mrinimitable.desk.page.setup_wizard.setup_wizard.email_setup_wizard_exception",
	"mrinimitable.desk.page.setup_wizard.setup_wizard.log_setup_wizard_exception",
]

before_migrate = ["mrinimitable.core.doctype.patch_log.patch_log.before_migrate"]
after_migrate = [
	"mrinimitable.website.doctype.website_theme.website_theme.after_migrate",
	"mrinimitable.search.sqlite_search.build_index_in_background",
]

otp_methods = ["OTP App", "Email", "SMS"]

user_data_fields = [
	{"doctype": "Access Log", "strict": True},
	{"doctype": "Activity Log", "strict": True},
	{"doctype": "Comment", "strict": True},
	{
		"doctype": "Contact",
		"filter_by": "email_id",
		"redact_fields": ["first_name", "last_name", "phone", "mobile_no"],
		"rename": True,
	},
	{"doctype": "Contact Email", "filter_by": "email_id"},
	{
		"doctype": "Address",
		"filter_by": "email_id",
		"redact_fields": [
			"address_title",
			"address_line1",
			"address_line2",
			"city",
			"county",
			"state",
			"pincode",
			"phone",
			"fax",
		],
	},
	{
		"doctype": "Communication",
		"filter_by": "sender",
		"redact_fields": ["sender_full_name", "phone_no", "content"],
	},
	{"doctype": "Communication", "filter_by": "recipients"},
	{"doctype": "Email Group Member", "filter_by": "email"},
	{"doctype": "Email Unsubscribe", "filter_by": "email", "partial": True},
	{"doctype": "Email Queue", "filter_by": "sender"},
	{"doctype": "Email Queue Recipient", "filter_by": "recipient"},
	{
		"doctype": "File",
		"filter_by": "attached_to_name",
		"redact_fields": ["file_name", "file_url"],
	},
	{
		"doctype": "User",
		"filter_by": "name",
		"redact_fields": [
			"email",
			"username",
			"first_name",
			"middle_name",
			"last_name",
			"full_name",
			"birth_date",
			"user_image",
			"phone",
			"mobile_no",
			"location",
			"banner_image",
			"interest",
			"bio",
			"email_signature",
		],
	},
	{"doctype": "Version", "strict": True},
]

global_search_doctypes = {
	"Default": [
		{"doctype": "Contact"},
		{"doctype": "Address"},
		{"doctype": "ToDo"},
		{"doctype": "Note"},
		{"doctype": "Event"},
		{"doctype": "Dashboard"},
		{"doctype": "Country"},
		{"doctype": "Currency"},
		{"doctype": "Letter Head"},
		{"doctype": "Workflow"},
		{"doctype": "Web Page"},
		{"doctype": "Web Form"},
	]
}

override_whitelisted_methods = {
	# Legacy File APIs
	"mrinimitable.utils.file_manager.download_file": "download_file",
	"mrinimitable.core.doctype.file.file.download_file": "download_file",
	"mrinimitable.core.doctype.file.file.unzip_file": "mrinimitable.core.api.file.unzip_file",
	"mrinimitable.core.doctype.file.file.get_attached_images": "mrinimitable.core.api.file.get_attached_images",
	"mrinimitable.core.doctype.file.file.get_files_in_folder": "mrinimitable.core.api.file.get_files_in_folder",
	"mrinimitable.core.doctype.file.file.get_files_by_search_text": "mrinimitable.core.api.file.get_files_by_search_text",
	"mrinimitable.core.doctype.file.file.get_max_file_size": "mrinimitable.core.api.file.get_max_file_size",
	"mrinimitable.core.doctype.file.file.create_new_folder": "mrinimitable.core.api.file.create_new_folder",
	"mrinimitable.core.doctype.file.file.move_file": "mrinimitable.core.api.file.move_file",
	"mrinimitable.core.doctype.file.file.zip_files": "mrinimitable.core.api.file.zip_files",
	# Legacy (& Consistency) OAuth2 APIs
	"mrinimitable.www.login.login_via_google": "mrinimitable.integrations.oauth2_logins.login_via_google",
	"mrinimitable.www.login.login_via_github": "mrinimitable.integrations.oauth2_logins.login_via_github",
	"mrinimitable.www.login.login_via_facebook": "mrinimitable.integrations.oauth2_logins.login_via_facebook",
	"mrinimitable.www.login.login_via_mrinimitable": "mrinimitable.integrations.oauth2_logins.login_via_mrinimitable",
	"mrinimitable.www.login.login_via_office365": "mrinimitable.integrations.oauth2_logins.login_via_office365",
	"mrinimitable.www.login.login_via_salesforce": "mrinimitable.integrations.oauth2_logins.login_via_salesforce",
	"mrinimitable.www.login.login_via_fairlogin": "mrinimitable.integrations.oauth2_logins.login_via_fairlogin",
}

ignore_links_on_delete = [
	"Communication",
	"ToDo",
	"DocShare",
	"Email Unsubscribe",
	"Activity Log",
	"File",
	"Version",
	"Document Follow",
	"Comment",
	"View Log",
	"Tag Link",
	"Notification Log",
	"Email Queue",
	"Document Share Key",
	"Integration Request",
	"Unhandled Email",
	"Webhook Request Log",
	"Workspace",
	"Route History",
	"Access Log",
	"Permission Log",
]

# Request Hooks
before_request = [
	"mrinimitable.recorder.record",
	"mrinimitable.monitor.start",
	"mrinimitable.rate_limiter.apply",
	"mrinimitable.integrations.oauth2.set_cors_for_privileged_requests",
]

after_request = [
	"mrinimitable.monitor.stop",
]

# Background Job Hooks
before_job = [
	"mrinimitable.recorder.record",
	"mrinimitable.monitor.start",
]

if os.getenv("MRINIMITABLE_SENTRY_DSN") and (
	os.getenv("ENABLE_SENTRY_DB_MONITORING")
	or os.getenv("SENTRY_TRACING_SAMPLE_RATE")
	or os.getenv("SENTRY_PROFILING_SAMPLE_RATE")
):
	before_request.append("mrinimitable.utils.sentry.set_sentry_context")
	before_job.append("mrinimitable.utils.sentry.set_sentry_context")

after_job = [
	"mrinimitable.recorder.dump",
	"mrinimitable.monitor.stop",
	"mrinimitable.utils.file_lock.release_document_locks",
]

extend_bootinfo = [
	"mrinimitable.utils.telemetry.add_bootinfo",
	"mrinimitable.core.doctype.user_permission.user_permission.send_user_permissions",
]

get_changelog_feed = "mrinimitable.desk.doctype.changelog_feed.changelog_feed.get_feed"

export_python_type_annotations = True

standard_navbar_items = [
	{
		"item_label": "User Settings",
		"item_type": "Action",
		"action": "mrinimitable.ui.toolbar.route_to_user()",
		"is_standard": 1,
	},
	{
		"item_label": "Workspace Settings",
		"item_type": "Action",
		"action": "mrinimitable.quick_edit('Workspace Settings')",
		"is_standard": 1,
	},
	{
		"item_label": "Session Defaults",
		"item_type": "Action",
		"action": "mrinimitable.ui.toolbar.setup_session_defaults()",
		"is_standard": 1,
	},
	{
		"item_label": "Reload",
		"item_type": "Action",
		"action": "mrinimitable.ui.toolbar.clear_cache()",
		"is_standard": 1,
	},
	{
		"item_label": "View Website",
		"item_type": "Action",
		"action": "mrinimitable.ui.toolbar.view_website()",
		"is_standard": 1,
	},
	{
		"item_label": "Apps",
		"item_type": "Route",
		"route": "/apps",
		"is_standard": 1,
	},
	{
		"item_label": "Toggle Full Width",
		"item_type": "Action",
		"action": "mrinimitable.ui.toolbar.toggle_full_width()",
		"is_standard": 1,
	},
	{
		"item_label": "Toggle Theme",
		"item_type": "Action",
		"action": "new mrinimitable.ui.ThemeSwitcher().show()",
		"is_standard": 1,
	},
	{
		"item_type": "Separator",
		"is_standard": 1,
		"item_label": "",
	},
	{
		"item_label": "Log out",
		"item_type": "Action",
		"action": "mrinimitable.app.logout()",
		"is_standard": 1,
	},
]

standard_help_items = [
	{
		"item_label": "About",
		"item_type": "Action",
		"action": "mrinimitable.ui.toolbar.show_about()",
		"is_standard": 1,
	},
	{
		"item_label": "Keyboard Shortcuts",
		"item_type": "Action",
		"action": "mrinimitable.ui.toolbar.show_shortcuts(event)",
		"is_standard": 1,
	},
	{
		"item_label": "System Health",
		"item_type": "Route",
		"route": "/app/system-health-report",
		"is_standard": 1,
	},
	{
		"item_label": "Mrinimitable Support",
		"item_type": "Route",
		"route": "https://mrinimitable.io/support",
		"is_standard": 1,
	},
]

# log doctype cleanups to automatically add in log settings
default_log_clearing_doctypes = {
	"Error Log": 14,
	"Email Queue": 30,
	"Scheduled Job Log": 7,
	"Submission Queue": 7,
	"Prepared Report": 14,
	"Webhook Request Log": 30,
	"Unhandled Email": 30,
	"Reminder": 30,
	"Integration Request": 90,
	"Activity Log": 90,
	"Route History": 90,
	"OAuth Bearer Token": 30,
	"API Request Log": 90,
}

# These keys will not be erased when doing mrinimitable.clear_cache()
persistent_cache_keys = [
	"changelog-*",  # version update notifications
	"insert_queue_for_*",  # Deferred Insert
	"recorder-*",  # Recorder
	"global_search_queue",
	"monitor-transactions",
	"rate-limit-counter-*",
	"rl:*",
]

user_invitation = {
	"allowed_roles": {
		"System Manager": [],
	},
}
