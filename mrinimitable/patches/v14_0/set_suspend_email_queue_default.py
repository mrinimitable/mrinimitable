import mrinimitable
from mrinimitable.cache_manager import clear_defaults_cache


def execute():
	mrinimitable.db.set_default(
		"suspend_email_queue",
		mrinimitable.db.get_default("hold_queue", "Administrator") or 0,
		parent="__default",
	)

	mrinimitable.db.delete("DefaultValue", {"defkey": "hold_queue"})
	clear_defaults_cache()
