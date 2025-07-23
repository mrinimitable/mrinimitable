# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import suppress

import mrinimitable
from mrinimitable import _
from mrinimitable.rate_limiter import rate_limit
from mrinimitable.utils import escape_html, validate_email_address

sitemap = 1


def get_context(context):
	doc = mrinimitable.get_doc("Contact Us Settings", "Contact Us Settings")

	if doc.query_options:
		query_options = [opt.strip() for opt in doc.query_options.replace(",", "\n").split("\n") if opt]
	else:
		query_options = ["Sales", "Support", "General"]

	out = {"query_options": query_options, "parents": [{"name": _("Home"), "route": "/"}]}
	out.update(doc.as_dict())

	return out


@mrinimitable.whitelist(allow_guest=True)
@rate_limit(limit=1000, seconds=60 * 60)
def send_message(sender, message, subject="Website Query"):
	sender = validate_email_address(sender, throw=True)

	message = escape_html(message)

	with suppress(mrinimitable.OutgoingEmailError):
		if forward_to_email := mrinimitable.db.get_single_value("Contact Us Settings", "forward_to_email"):
			mrinimitable.sendmail(recipients=forward_to_email, reply_to=sender, content=message, subject=subject)

		reply = _(
			"""Thank you for reaching out to us. We will get back to you at the earliest.


Your query:

{0}"""
		).format(message)
		mrinimitable.sendmail(
			recipients=sender,
			content=f"<div style='white-space: pre-wrap'>{reply}</div>",
			subject=_("We've received your query!"),
		)

	# for clearing outgoing email error message
	mrinimitable.clear_last_message()

	system_language = mrinimitable.db.get_single_value("System Settings", "language")
	# add to to-do ?
	mrinimitable.get_doc(
		doctype="Communication",
		sender=sender,
		subject=_("New Message from Website Contact Page", system_language),
		sent_or_received="Received",
		content=message,
		status="Open",
	).insert(ignore_permissions=True)
