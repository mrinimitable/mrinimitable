# Settings saved per user basis
# such as page_limit, filters, last_view

import json

import mrinimitable
from mrinimitable import safe_decode

# dict for mapping the index and index type for the filters of different views
filter_dict = {"doctype": 0, "docfield": 1, "operator": 2, "value": 3}


def get_user_settings(doctype, for_update=False):
	user_settings = mrinimitable.cache.hget("_user_settings", f"{doctype}::{mrinimitable.session.user}")

	if user_settings is None:
		user_settings = mrinimitable.db.sql(
			"""select data from `__UserSettings`
			where `user`=%s and `doctype`=%s""",
			(mrinimitable.session.user, doctype),
		)
		user_settings = (user_settings and user_settings[0][0]) or "{}"

		if not for_update:
			update_user_settings(doctype, user_settings, True)

	return user_settings or "{}"


def update_user_settings(doctype, user_settings, for_update=False):
	"""update user settings in cache"""

	if for_update:
		current = json.loads(user_settings)
	else:
		current = json.loads(get_user_settings(doctype, for_update=True))

		if isinstance(current, str):
			# corrupt due to old code, remove this in a future release
			current = {}

		current.update(user_settings)

	mrinimitable.cache.hset("_user_settings", f"{doctype}::{mrinimitable.session.user}", json.dumps(current))


def sync_user_settings():
	"""Sync from cache to database (called asynchronously via the browser)"""
	for key, data in mrinimitable.cache.hgetall("_user_settings").items():
		key = safe_decode(key)
		doctype, user = key.split("::")  # WTF?
		mrinimitable.db.multisql(
			{
				"mariadb": """INSERT INTO `__UserSettings`(`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)
				ON DUPLICATE key UPDATE `data`=%s""",
				"postgres": """INSERT INTO `__UserSettings` (`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)
				ON CONFLICT ("user", "doctype") DO UPDATE SET `data`=%s""",
				"sqlite": """INSERT OR REPLACE INTO `__UserSettings` (`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)""",
			},
			(user, doctype, data, data),
			as_dict=1,
		)


@mrinimitable.whitelist()
def save(doctype, user_settings):
	user_settings = json.loads(user_settings or "{}")
	update_user_settings(doctype, user_settings)
	return user_settings


@mrinimitable.whitelist()
def get(doctype):
	return get_user_settings(doctype)


def update_user_settings_data(
	user_setting, fieldname, old, new, condition_fieldname=None, condition_values=None
):
	data = user_setting.get("data")
	if data:
		update = False
		data = json.loads(data)
		for view in ["List", "Gantt", "Kanban", "Calendar", "Image", "Inbox", "Report"]:
			view_settings = data.get(view)
			if view_settings and view_settings.get("filters"):
				view_filters = view_settings.get("filters")
				for view_filter in view_filters:
					if (
						condition_fieldname
						and view_filter[filter_dict[condition_fieldname]] != condition_values
					):
						continue
					if view_filter[filter_dict[fieldname]] == old:
						view_filter[filter_dict[fieldname]] = new
						update = True
		if update:
			mrinimitable.db.sql(
				"update __UserSettings set data=%s where doctype=%s and user=%s",
				(json.dumps(data), user_setting.doctype, user_setting.user),
			)

			# clear that user settings from the redis cache
			mrinimitable.cache.hset("_user_settings", f"{user_setting.doctype}::{user_setting.user}", None)
