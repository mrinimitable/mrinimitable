import json

import mrinimitable


@mrinimitable.whitelist()
def get_onboarding_status():
	onboarding_status = mrinimitable.db.get_value("User", mrinimitable.session.user, "onboarding_status")
	return mrinimitable.parse_json(onboarding_status) if onboarding_status else {}


@mrinimitable.whitelist()
def update_user_onboarding_status(steps: str, appName: str):
	steps = json.loads(steps)

	# get the current onboarding status
	onboarding_status = mrinimitable.db.get_value("User", mrinimitable.session.user, "onboarding_status")
	onboarding_status = mrinimitable.parse_json(onboarding_status)

	# update the onboarding status
	onboarding_status[appName + "_onboarding_status"] = steps

	mrinimitable.db.set_value(
		"User", mrinimitable.session.user, "onboarding_status", json.dumps(onboarding_status), update_modified=False
	)
