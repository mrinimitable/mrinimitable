import mrinimitable
from mrinimitable.utils import cint


def execute():
	mrinimitable.reload_doctype("Dropbox Settings")
	check_dropbox_enabled = cint(mrinimitable.db.get_single_value("Dropbox Settings", "enabled"))
	if check_dropbox_enabled == 1:
		mrinimitable.db.set_single_value("Dropbox Settings", "file_backup", 1)
