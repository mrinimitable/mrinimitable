import mrinimitable
from mrinimitable.model.rename_doc import rename_doc


def execute():
	if mrinimitable.db.table_exists("Workflow Action") and not mrinimitable.db.table_exists("Workflow Action Master"):
		rename_doc("DocType", "Workflow Action", "Workflow Action Master")
		mrinimitable.reload_doc("workflow", "doctype", "workflow_action_master")
