import mrinimitable


def execute():
	Event = mrinimitable.qb.DocType("Event")
	query = (
		mrinimitable.qb.update(Event)
		.set(Event.event_type, "Private")
		.set(Event.status, "Cancelled")
		.where(Event.event_type == "Cancelled")
	)
	query.run()
