# Copyright (c) 2019, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
import mrinimitable.cache_manager
from mrinimitable.model import log_types
from mrinimitable.model.document import Document


class MilestoneTracker(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		disabled: DF.Check
		document_type: DF.Link
		track_field: DF.Literal[None]
	# end: auto-generated types

	def on_update(self):
		mrinimitable.cache_manager.clear_doctype_map("Milestone Tracker", self.document_type)

	def on_trash(self):
		mrinimitable.cache_manager.clear_doctype_map("Milestone Tracker", self.document_type)

	def apply(self, doc):
		before_save = doc.get_doc_before_save()
		from_value = (before_save and before_save.get(self.track_field)) or None
		if from_value != doc.get(self.track_field):
			mrinimitable.get_doc(
				doctype="Milestone",
				reference_type=doc.doctype,
				reference_name=doc.name,
				track_field=self.track_field,
				from_value=from_value,
				value=doc.get(self.track_field),
				milestone_tracker=self.name,
			).insert(ignore_permissions=True)


def evaluate_milestone(doc, event):
	if (
		mrinimitable.flags.in_install
		or mrinimitable.flags.in_migrate
		or mrinimitable.flags.in_setup_wizard
		or doc.doctype in log_types
	):
		return

	# track milestones related to this doctype
	for d in get_milestone_trackers(doc.doctype):
		mrinimitable.get_doc("Milestone Tracker", d.get("name")).apply(doc)


def get_milestone_trackers(doctype):
	return mrinimitable.cache_manager.get_doctype_map(
		"Milestone Tracker", doctype, dict(document_type=doctype, disabled=0)
	)
