# Copyright (c) 2024, Mrinimitable Technologies and contributors
# For license information, please see license.txt

import json

import mrinimitable
from mrinimitable.model.document import Document


class WorkspaceSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		workspace_setup_completed: DF.Check
		workspace_visibility_json: DF.JSON
	# end: auto-generated types

	pass

	def on_update(self):
		mrinimitable.clear_cache()


@mrinimitable.whitelist()
def set_sequence(sidebar_items):
	if not WorkspaceSettings("Workspace Settings").has_permission():
		mrinimitable.throw_permission_error()

	cnt = 1
	for item in json.loads(sidebar_items):
		mrinimitable.db.set_value("Workspace", item.get("name"), "sequence_id", cnt)
		mrinimitable.db.set_value("Workspace", item.get("name"), "parent_page", item.get("parent") or "")
		cnt += 1

	mrinimitable.clear_cache()
	mrinimitable.toast(mrinimitable._("Updated"))
