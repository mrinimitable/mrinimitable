# Copyright (c) 2015, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import json

import mrinimitable
from mrinimitable import _
from mrinimitable.desk.doctype.bulk_update.bulk_update import show_progress
from mrinimitable.model.document import Document
from mrinimitable.model.workflow import get_workflow_name


class DeletedDocument(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		data: DF.Code | None
		deleted_doctype: DF.Data | None
		deleted_name: DF.Data | None
		new_name: DF.ReadOnly | None
		restored: DF.Check
	# end: auto-generated types

	no_feed_on_delete = True

	@staticmethod
	def clear_old_logs(days=180):
		from mrinimitable.query_builder import Interval
		from mrinimitable.query_builder.functions import Now

		table = mrinimitable.qb.DocType("Deleted Document")
		mrinimitable.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@mrinimitable.whitelist()
def restore(name, alert=True):
	deleted = mrinimitable.get_doc("Deleted Document", name)

	if deleted.restored:
		mrinimitable.throw(_("Document {0} Already Restored").format(name), exc=mrinimitable.DocumentAlreadyRestored)

	doc = mrinimitable.get_doc(json.loads(deleted.data))

	try:
		doc.insert()
	except mrinimitable.DocstatusTransitionError:
		mrinimitable.msgprint(_("Cancelled Document restored as Draft"))
		doc.docstatus = 0
		active_workflow = get_workflow_name(doc.doctype)
		if active_workflow:
			workflow_state_fieldname = mrinimitable.get_value("Workflow", active_workflow, "workflow_state_field")
			if doc.get(workflow_state_fieldname):
				doc.set(workflow_state_fieldname, None)
		doc.insert()

	doc.add_comment("Edit", _("restored {0} as {1}").format(deleted.deleted_name, doc.name))

	deleted.new_name = doc.name
	deleted.restored = 1
	deleted.db_update()

	if alert:
		mrinimitable.msgprint(_("Document Restored"))


@mrinimitable.whitelist()
def bulk_restore(docnames):
	docnames = mrinimitable.parse_json(docnames)
	message = _("Restoring Deleted Document")
	restored, invalid, failed = [], [], []

	for i, d in enumerate(docnames):
		try:
			show_progress(docnames, message, i + 1, d)
			restore(d, alert=False)
			mrinimitable.db.commit()
			restored.append(d)

		except mrinimitable.DocumentAlreadyRestored:
			mrinimitable.clear_last_message()
			invalid.append(d)

		except Exception:
			mrinimitable.clear_last_message()
			failed.append(d)
			mrinimitable.db.rollback()

	return {"restored": restored, "invalid": invalid, "failed": failed}
