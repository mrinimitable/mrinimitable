# Copyright (c) 2023, Mrinimitable Technologies and contributors
# For license information, please see license.txt

import mrinimitable
from mrinimitable import _
from mrinimitable.model.document import Document
from mrinimitable.utils import cint
from mrinimitable.utils.data import add_to_date, get_datetime, now_datetime


class Reminder(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		description: DF.SmallText
		notified: DF.Check
		remind_at: DF.Datetime
		reminder_docname: DF.DynamicLink | None
		reminder_doctype: DF.Link | None
		user: DF.Link
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=30):
		from mrinimitable.query_builder import Interval
		from mrinimitable.query_builder.functions import Now

		table = mrinimitable.qb.DocType("Reminder")
		mrinimitable.db.delete(table, filters=(table.remind_at < (Now() - Interval(days=days))))

	def validate(self):
		self.user = mrinimitable.session.user
		if get_datetime(self.remind_at) < now_datetime():
			mrinimitable.throw(_("Reminder cannot be created in past."))

	def send_reminder(self):
		if self.notified:
			return

		self.db_set("notified", 1, update_modified=False)

		try:
			notification = mrinimitable.new_doc("Notification Log")
			notification.for_user = self.user
			notification.set("type", "Alert")
			notification.document_type = self.reminder_doctype
			notification.document_name = self.reminder_docname
			notification.subject = self.description
			notification.insert()
		except Exception:
			self.log_error("Failed to send reminder")


@mrinimitable.whitelist()
def create_new_reminder(
	remind_at: str,
	description: str,
	reminder_doctype: str | None = None,
	reminder_docname: str | None = None,
):
	reminder = mrinimitable.new_doc("Reminder")

	reminder.description = description
	reminder.remind_at = remind_at
	reminder.reminder_doctype = reminder_doctype
	reminder.reminder_docname = reminder_docname

	return reminder.insert()


def send_reminders():
	# Ensure that we send all reminders that might be before next job execution.
	job_freq = 15 * 60  # 15 minutes, as specified in hooks.py
	upper_threshold = add_to_date(now_datetime(), seconds=job_freq, as_string=True, as_datetime=True)
	lower_threshold = add_to_date(now_datetime(), hours=-1, as_string=True, as_datetime=True)

	pending_reminders = mrinimitable.get_all(
		"Reminder",
		filters=[
			("remind_at", "<=", upper_threshold),
			("remind_at", ">=", lower_threshold),  # dont send too old reminders if failed to send
			("notified", "=", 0),
		],
		pluck="name",
		ignore_ifnull=True,
	)

	for reminder in pending_reminders:
		mrinimitable.get_doc("Reminder", reminder).send_reminder()
