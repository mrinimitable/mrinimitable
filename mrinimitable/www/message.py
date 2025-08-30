# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.utils import strip_html_tags
from mrinimitable.utils.html_utils import clean_html

no_cache = 1


def get_context(context):
	message_context = mrinimitable._dict()
	if hasattr(mrinimitable.local, "message"):
		message_context["header"] = mrinimitable.local.message_title
		message_context["title"] = strip_html_tags(mrinimitable.local.message_title)
		message_context["message"] = mrinimitable.local.message
		if hasattr(mrinimitable.local, "message_success"):
			message_context["success"] = mrinimitable.local.message_success

	elif mrinimitable.local.form_dict.id:
		message_id = mrinimitable.local.form_dict.id
		key = f"message_id:{message_id}"
		message = mrinimitable.cache.get_value(key, expires=True)
		if message:
			message_context.update(message.get("context", {}))
			if message.get("http_status_code"):
				mrinimitable.local.response["http_status_code"] = message["http_status_code"]

	if not message_context.title:
		message_context.title = clean_html(mrinimitable.form_dict.title)

	if not message_context.message:
		message_context.message = clean_html(mrinimitable.form_dict.message)

	return message_context
