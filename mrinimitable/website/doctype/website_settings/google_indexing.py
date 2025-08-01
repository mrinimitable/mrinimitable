# Copyright (c) 2020, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE


from urllib.parse import quote

from googleapiclient.errors import HttpError

import mrinimitable
from mrinimitable import _
from mrinimitable.integrations.google_oauth import GoogleOAuth


@mrinimitable.whitelist(methods=["POST"])
def authorize_access(reauthorize=False, code=None):
	"""If no Authorization code get it from Google and then request for Refresh Token."""

	oauth_code = (
		mrinimitable.db.get_single_value("Website Settings", "indexing_authorization_code") if not code else code
	)

	oauth_obj = GoogleOAuth("indexing")

	if not oauth_code or reauthorize:
		return oauth_obj.get_authentication_url(
			{
				"redirect": f"/app/Form/{quote('Website Settings')}",
			},
		)

	res = oauth_obj.authorize(oauth_code)
	mrinimitable.db.set_single_value(
		"Website Settings",
		{"indexing_authorization_code": oauth_code, "indexing_refresh_token": res.get("refresh_token")},
	)


def get_google_indexing_object():
	"""Return an object of Google Indexing object."""
	account = mrinimitable.get_doc("Website Settings")
	oauth_obj = GoogleOAuth("indexing")

	return oauth_obj.get_google_service_object(
		account.get_access_token(),
		account.get_password(fieldname="indexing_refresh_token", raise_exception=False),
	)


def publish_site(url, operation_type="URL_UPDATED"):
	"""Send an update/remove url request."""

	google_indexing = get_google_indexing_object()
	body = {"url": url, "type": operation_type}
	try:
		google_indexing.urlNotifications().publish(body=body, x__xgafv="2").execute()
	except HttpError as e:
		mrinimitable.log_error(message=e, title="API Indexing Issue")
