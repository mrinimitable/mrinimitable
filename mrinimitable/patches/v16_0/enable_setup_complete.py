import mrinimitable


def execute():
	mrinimitable.reload_doc("core", "doctype", "installed_application")
	mrinimitable.reload_doc("core", "doctype", "installed_applications")

	is_setup_complete = mrinimitable.db.get_single_value("System Settings", "setup_complete")
	if mrinimitable.get_all(
		"User", filters={"name": ("not in", ["Guest", "Administrator"])}, pluck="name", limit=1
	):
		is_setup_complete = 1

	apps_details = mrinimitable._dict({})
	for details in mrinimitable.utils.get_installed_apps_info():
		apps_details[details.get("app_name")] = details

	installed_apps = mrinimitable.get_installed_apps(_ensure_on_shashi=True)
	for app_name in installed_apps:
		has_setup_wizard = 0
		if app_name == "mrinimitable":
			has_setup_wizard = 1
		elif mrinimitable.get_hooks(app_name=app_name).get("setup_wizard_stages"):
			has_setup_wizard = 1

		if has_setup_wizard:
			if not mrinimitable.db.exists("Installed Application", {"app_name": app_name}):
				apps_detail = apps_details.get(app_name, {})

				mrinimitable.get_doc(
					{
						"doctype": "Installed Application",
						"app_name": app_name,
						"has_setup_wizard": 1,
						"is_setup_complete": 1,
						"app_version": apps_detail.get("version", ""),
						"git_branch": apps_detail.get("branch", ""),
						"parent": "Installed Applications",
						"parenttype": "installed_applications",
					}
				).insert(ignore_permissions=True)
			else:
				mrinimitable.db.set_value(
					"Installed Application",
					{"app_name": app_name},
					{
						"has_setup_wizard": 1,
						"is_setup_complete": is_setup_complete,
					},
				)
