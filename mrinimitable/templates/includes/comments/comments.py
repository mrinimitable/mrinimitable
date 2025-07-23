# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re

import mrinimitable
from mrinimitable import _, scrub
from mrinimitable.rate_limiter import rate_limit
from mrinimitable.utils.html_utils import clean_html
from mrinimitable.website.doctype.blog_settings.blog_settings import get_comment_limit
from mrinimitable.website.utils import clear_cache

URLS_COMMENT_PATTERN = re.compile(
	r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", re.IGNORECASE
)
EMAIL_PATTERN = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", re.IGNORECASE)


@mrinimitable.whitelist(allow_guest=True)
@rate_limit(key="reference_name", limit=get_comment_limit, seconds=60 * 60)
def add_comment(comment, comment_email, comment_by, reference_doctype, reference_name, route):
	if mrinimitable.session.user == "Guest":
		if reference_doctype not in ("Blog Post", "Web Page"):
			return

		if reference_doctype == "Blog Post" and not mrinimitable.db.get_single_value(
			"Blog Settings", "allow_guest_to_comment"
		):
			return

		if mrinimitable.db.exists("User", comment_email):
			mrinimitable.throw(_("Please login to post a comment."))

	if not comment.strip():
		mrinimitable.msgprint(_("The comment cannot be empty"))
		return False

	if URLS_COMMENT_PATTERN.search(comment) or EMAIL_PATTERN.search(comment):
		mrinimitable.msgprint(_("Comments cannot have links or email addresses"))
		return False

	doc = mrinimitable.get_doc(reference_doctype, reference_name)
	comment = doc.add_comment(text=clean_html(comment), comment_email=comment_email, comment_by=comment_by)

	comment.db_set("published", 1)

	# since comments are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	if doc.get("route"):
		url = f"{mrinimitable.utils.get_request_site_address()}/{doc.route}#{comment.name}"
	else:
		url = f"{mrinimitable.utils.get_request_site_address()}/app/{scrub(doc.doctype)}/{doc.name}#comment-{comment.name}"

	content = comment.content + "<p><a href='{}' style='font-size: 80%'>{}</a></p>".format(
		url, _("View Comment")
	)

	if doc.doctype != "Blog Post" or doc.enable_email_notification:
		# notify creator
		creator_email = mrinimitable.db.get_value("User", doc.owner, "email") or doc.owner
		subject = _("New Comment on {0}: {1}").format(doc.doctype, doc.get_title())

		mrinimitable.sendmail(
			recipients=creator_email,
			subject=subject,
			message=content,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)

	# revert with template if all clear (no backlinks)
	template = mrinimitable.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment.as_dict()})
