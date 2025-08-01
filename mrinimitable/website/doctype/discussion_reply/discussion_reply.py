# Copyright (c) 2021, Mrinimitable Technologies and contributors
# For license information, please see license.txt

import mrinimitable
from mrinimitable.model.document import Document
from mrinimitable.realtime import get_website_room


class DiscussionReply(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		reply: DF.TextEditor | None
		topic: DF.Link | None
	# end: auto-generated types

	def on_update(self):
		mrinimitable.publish_realtime(
			event="update_message",
			room=get_website_room(),
			message={"reply": mrinimitable.utils.md_to_html(self.reply), "reply_name": self.name},
			after_commit=True,
		)

	def after_insert(self):
		replies = mrinimitable.db.count("Discussion Reply", {"topic": self.topic})
		topic_info = mrinimitable.get_all(
			"Discussion Topic",
			{"name": self.topic},
			["reference_doctype", "reference_docname", "name", "title", "owner", "creation"],
		)

		template = mrinimitable.render_template(
			"mrinimitable/templates/discussions/reply_card.html",
			{
				"reply": self,
				"topic": {"name": self.topic},
				"loop": {"index": replies},
				"single_thread": True if not topic_info[0].title else False,
			},
		)

		sidebar = mrinimitable.render_template(
			"mrinimitable/templates/discussions/sidebar.html", {"topic": topic_info[0]}
		)

		new_topic_template = mrinimitable.render_template(
			"mrinimitable/templates/discussions/reply_section.html", {"topic": topic_info[0]}
		)

		mrinimitable.publish_realtime(
			event="publish_message",
			room=get_website_room(),
			message={
				"template": template,
				"topic_info": topic_info[0],
				"sidebar": sidebar,
				"new_topic_template": new_topic_template,
				"reply_owner": self.owner,
			},
			after_commit=True,
		)

	def after_delete(self):
		mrinimitable.publish_realtime(
			event="delete_message",
			room=get_website_room(),
			message={"reply_name": self.name},
			after_commit=True,
		)


@mrinimitable.whitelist()
def delete_message(reply_name):
	owner = mrinimitable.db.get_value("Discussion Reply", reply_name, "owner")
	if owner == mrinimitable.session.user:
		mrinimitable.delete_doc("Discussion Reply", reply_name)
