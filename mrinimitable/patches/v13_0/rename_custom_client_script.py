import mrinimitable
from mrinimitable.model.rename_doc import rename_doc


def execute():
	if mrinimitable.db.exists("DocType", "Client Script"):
		return

	mrinimitable.flags.ignore_route_conflict_validation = True
	rename_doc("DocType", "Custom Script", "Client Script")
	mrinimitable.flags.ignore_route_conflict_validation = False

	mrinimitable.reload_doctype("Client Script", force=True)
