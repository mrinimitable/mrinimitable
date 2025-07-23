import mrinimitable
from mrinimitable.utils import cint

no_cache = 1


def get_context(context):
	mrinimitable.db.commit()  # nosemgrep
	context = mrinimitable._dict()
	context.boot = get_boot()
	return context


def get_boot():
	return mrinimitable._dict(
		{
			"site_name": mrinimitable.local.site,
			"read_only_mode": mrinimitable.flags.read_only,
			"csrf_token": mrinimitable.sessions.get_csrf_token(),
			"setup_complete": mrinimitable.is_setup_complete(),
		}
	)
