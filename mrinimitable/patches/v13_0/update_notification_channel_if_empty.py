# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	mrinimitable.reload_doc("Email", "doctype", "Notification")

	notifications = mrinimitable.get_all("Notification", {"is_standard": 1}, {"name", "channel"})
	for notification in notifications:
		if not notification.channel:
			mrinimitable.db.set_value("Notification", notification.name, "channel", "Email", update_modified=False)
			mrinimitable.db.commit()
