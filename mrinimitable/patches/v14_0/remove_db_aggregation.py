import re

import mrinimitable
from mrinimitable.query_builder import DocType


def execute():
	"""Replace temporarily available Database Aggregate APIs on mrinimitable (develop)

	APIs changed:
	        * mrinimitable.db.max => mrinimitable.qb.max
	        * mrinimitable.db.min => mrinimitable.qb.min
	        * mrinimitable.db.sum => mrinimitable.qb.sum
	        * mrinimitable.db.avg => mrinimitable.qb.avg
	"""
	ServerScript = DocType("Server Script")
	server_scripts = (
		mrinimitable.qb.from_(ServerScript)
		.where(
			ServerScript.script.like("%mrinimitable.db.max(%")
			| ServerScript.script.like("%mrinimitable.db.min(%")
			| ServerScript.script.like("%mrinimitable.db.sum(%")
			| ServerScript.script.like("%mrinimitable.db.avg(%")
		)
		.select("name", "script")
		.run(as_dict=True)
	)

	for server_script in server_scripts:
		name, script = server_script["name"], server_script["script"]

		for agg in ["avg", "max", "min", "sum"]:
			script = re.sub(f"mrinimitable.db.{agg}\\(", f"mrinimitable.qb.{agg}(", script)

		mrinimitable.db.set_value("Server Script", name, "script", script)
