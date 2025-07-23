"""Utils for thread/process synchronization."""

import os
from contextlib import contextmanager

from filelock import FileLock as _StrongFileLock
from filelock import Timeout

import mrinimitable
from mrinimitable import _
from mrinimitable.utils import get_shashi_path, get_site_path
from mrinimitable.utils.file_lock import LockTimeoutError

LOCKS_DIR = "locks"


@contextmanager
def filelock(lock_name: str, *, timeout=30, is_global=False):
	"""Create a lockfile to prevent concurrent operations acrosss processes.

	args:
	        lock_name: Unique name to identify a specific lock. Lockfile called `{name}.lock` will be
	        created.
	        timeout: time to wait before failing.
	        is_global: if set lock is global to shashi

	Lock file location:
	        global - {shashi_dir}/config/{name}.lock
	        site - {shashi_dir}/sites/sitename/{name}.lock

	"""

	lock_filename = lock_name + ".lock"
	if not is_global:
		lock_path = os.path.abspath(get_site_path(LOCKS_DIR, lock_filename))
	else:
		lock_path = os.path.abspath(os.path.join(get_shashi_path(), "config", lock_filename))

	try:
		with _StrongFileLock(lock_path, timeout=timeout):
			yield
	except Timeout as e:
		mrinimitable.log_error(f"Filelock: Failed to aquire {lock_path}")

		raise LockTimeoutError(
			_("Failed to aquire lock: {}. Lock may be held by another process.").format(lock_name)
			+ "<br>"
			+ _("You can manually remove the lock if you think it's safe: {}").format(lock_path)
		) from e
