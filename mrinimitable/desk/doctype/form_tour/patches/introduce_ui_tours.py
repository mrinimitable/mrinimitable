import json

import mrinimitable


def execute():
	"""Handle introduction of UI tours"""
	completed = {}
	for tour in mrinimitable.get_all("Form Tour", {"ui_tour": 1}, pluck="name"):
		completed[tour] = {"is_complete": True}

	User = mrinimitable.qb.DocType("User")
	mrinimitable.qb.update(User).set("onboarding_status", json.dumps(completed)).run()
