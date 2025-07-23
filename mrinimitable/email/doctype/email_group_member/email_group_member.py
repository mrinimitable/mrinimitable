# Copyright (c) 2015, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.model.document import Document


class EmailGroupMember(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		email: DF.Data
		email_group: DF.Link
		unsubscribed: DF.Check
	# end: auto-generated types

	def after_delete(self):
		email_group = mrinimitable.get_doc("Email Group", self.email_group)
		email_group.update_total_subscribers()

	def after_insert(self):
		email_group = mrinimitable.get_doc("Email Group", self.email_group)
		email_group.update_total_subscribers()


def after_doctype_insert():
	mrinimitable.db.add_unique("Email Group Member", ("email_group", "email"))
