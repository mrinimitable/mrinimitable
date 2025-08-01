import json

import mrinimitable


def execute():
	if mrinimitable.db.exists("Social Login Key", "github"):
		mrinimitable.db.set_value(
			"Social Login Key", "github", "auth_url_data", json.dumps({"scope": "user:email"})
		)
