import mrinimitable
from mrinimitable.utils import get_datetime


def execute():
	weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

	weekly_events = mrinimitable.get_list(
		"Event",
		filters={"repeat_this_event": 1, "repeat_on": "Every Week"},
		fields=["name", "starts_on"],
	)
	mrinimitable.reload_doc("desk", "doctype", "event")

	# Initially Daily Events had option to choose days, but now Weekly does, so just changing from Daily -> Weekly does the job
	mrinimitable.db.sql(
		"""UPDATE `tabEvent` SET `tabEvent`.repeat_on='Weekly' WHERE `tabEvent`.repeat_on='Every Day'"""
	)
	mrinimitable.db.sql(
		"""UPDATE `tabEvent` SET `tabEvent`.repeat_on='Weekly' WHERE `tabEvent`.repeat_on='Every Week'"""
	)
	mrinimitable.db.sql(
		"""UPDATE `tabEvent` SET `tabEvent`.repeat_on='Monthly' WHERE `tabEvent`.repeat_on='Every Month'"""
	)
	mrinimitable.db.sql(
		"""UPDATE `tabEvent` SET `tabEvent`.repeat_on='Yearly' WHERE `tabEvent`.repeat_on='Every Year'"""
	)

	for weekly_event in weekly_events:
		# Set WeekDay based on the starts_on so that event can repeat Weekly
		mrinimitable.db.set_value(
			"Event",
			weekly_event.name,
			weekdays[get_datetime(weekly_event.starts_on).weekday()],
			1,
			update_modified=False,
		)
