import mrinimitable

MRINIMITABLE_CLOUD_DOMAINS = ("mrinimitable.cloud", "okayblue.com", "mrinimitablehr.com", "mrinimitable.dev")


def on_mrinimitablecloud() -> bool:
	"""Returns true if running on Mrinimitable Cloud.


	Useful for modifying few features for better UX."""
	return mrinimitable.local.site.endswith(MRINIMITABLE_CLOUD_DOMAINS)
