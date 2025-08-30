# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re

import mrinimitable
from mrinimitable import _, scrub
from mrinimitable.rate_limiter import rate_limit
from mrinimitable.utils.html_utils import clean_html
from mrinimitable.website.utils import clear_cache

URLS_COMMENT_PATTERN = re.compile(
	r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", re.IGNORECASE
)
EMAIL_PATTERN = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", re.IGNORECASE)


def get_limit():
	method = mrinimitable.get_hooks("comment_rate_limit")
	if not method:
		return 5
	else:
		limit = mrinimitable.call(method[0])
		return limit


@mrinimitable.whitelist(allow_guest=True)
# @rate_limit(key="reference_name", limit=get_limit, seconds=60 * 60)
def add_comment(comment, comment_email, comment_by, reference_doctype, reference_name, route):
	if mrinimitable.session.user == "Guest":
		allowed_doctypes = ["Web Page"]
		comments_permission_config = mrinimitable.get_hooks("has_comment_permission")
		guest_allowed = False
		if len(comments_permission_config):
			if comments_permission_config["doctype"]:
				allowed_doctypes.append(comments_permission_config["doctype"][0])
				check_permission_method = comments_permission_config["method"]
				guest_allowed = mrinimitable.call(check_permission_method[0], ref_doctype=reference_doctype)
		if reference_doctype not in allowed_doctypes:
			return

		if not guest_allowed:
			mrinimitable.throw(_("Please login to post a comment."))

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

	# revert with template if all clear (no backlinks)
	template = mrinimitable.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment.as_dict()})
