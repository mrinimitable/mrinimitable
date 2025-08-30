import mrinimitable


def execute():
	mrinimitable.reload_doc("workflow", "doctype", "workflow_transition")
	mrinimitable.db.sql("update `tabWorkflow Transition` set allow_self_approval=1")
