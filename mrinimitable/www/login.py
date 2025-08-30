# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


from urllib.parse import urlparse

import mrinimitable
import mrinimitable.utils
from mrinimitable import _
from mrinimitable.apps import get_default_path
from mrinimitable.auth import LoginManager
from mrinimitable.core.doctype.navbar_settings.navbar_settings import get_app_logo
from mrinimitable.rate_limiter import rate_limit
from mrinimitable.utils import cint, get_url
from mrinimitable.utils.data import escape_html
from mrinimitable.utils.html_utils import get_icon_html
from mrinimitable.utils.jinja import guess_is_path
from mrinimitable.utils.oauth import get_oauth2_authorize_url, get_oauth_keys, redirect_post_login
from mrinimitable.utils.password import get_decrypted_password
from mrinimitable.website.utils import get_home_page

no_cache = True


def get_context(context):
	from mrinimitable.integrations.mrinimitable_providers.mrinimitablecloud_billing import get_site_login_url
	from mrinimitable.utils.mrinimitablecloud import on_mrinimitablecloud

	redirect_to = mrinimitable.local.request.args.get("redirect-to")
	redirect_to = sanitize_redirect(redirect_to)

	if mrinimitable.session.user != "Guest":
		if not redirect_to:
			if mrinimitable.session.data.user_type == "Website User":
				redirect_to = get_default_path() or get_home_page()
			else:
				redirect_to = get_default_path() or "/app"

		if redirect_to != "login":
			mrinimitable.local.flags.redirect_location = redirect_to
			raise mrinimitable.Redirect

	context.no_header = True
	context.for_test = "login.html"
	context["title"] = "Login"
	context["hide_login"] = True  # dont show login link on login page again.
	context["provider_logins"] = []
	context["disable_signup"] = cint(mrinimitable.get_website_settings("disable_signup"))
	context["show_footer_on_login"] = cint(mrinimitable.get_website_settings("show_footer_on_login"))
	context["disable_user_pass_login"] = cint(mrinimitable.get_system_settings("disable_user_pass_login"))
	context["logo"] = get_app_logo()
	context["app_name"] = (
		mrinimitable.get_website_settings("app_name") or mrinimitable.get_system_settings("app_name") or _("Mrinimitable")
	)

	signup_form_template = mrinimitable.get_hooks("signup_form_template")
	if signup_form_template and len(signup_form_template):
		path = signup_form_template[-1]
		if not guess_is_path(path):
			path = mrinimitable.get_attr(signup_form_template[-1])()
	else:
		path = "mrinimitable/templates/signup.html"

	if path:
		context["signup_form_template"] = mrinimitable.get_template(path).render()

	providers = mrinimitable.get_all(
		"Social Login Key",
		filters={"enable_social_login": 1},
		fields=["name", "client_id", "base_url", "provider_name", "icon"],
		order_by="name",
	)

	for provider in providers:
		client_secret = get_decrypted_password(
			"Social Login Key", provider.name, "client_secret", raise_exception=False
		)
		if not client_secret:
			continue

		icon = None
		if provider.icon:
			if provider.provider_name == "Custom":
				icon = get_icon_html(provider.icon, small=True)
			else:
				icon = f"<img src={escape_html(provider.icon)!r} alt={escape_html(provider.provider_name)!r}>"

		if provider.client_id and provider.base_url and get_oauth_keys(provider.name):
			context.provider_logins.append(
				{
					"name": provider.name,
					"provider_name": provider.provider_name,
					"auth_url": get_oauth2_authorize_url(provider.name, redirect_to),
					"icon": icon,
				}
			)
			context["social_login"] = True

	if cint(mrinimitable.db.get_value("LDAP Settings", "LDAP Settings", "enabled")):
		from mrinimitable.integrations.doctype.ldap_settings.ldap_settings import LDAPSettings

		context["ldap_settings"] = LDAPSettings.get_ldap_client_settings()

	login_label = [_("Email")]

	if mrinimitable.utils.cint(mrinimitable.get_system_settings("allow_login_using_mobile_number")):
		login_label.append(_("Mobile"))

	if mrinimitable.utils.cint(mrinimitable.get_system_settings("allow_login_using_user_name")):
		login_label.append(_("Username"))

	context["login_label"] = f" {_('or')} ".join(login_label)

	context["login_with_email_link"] = mrinimitable.get_system_settings("login_with_email_link")
	context["login_with_mrinimitable_cloud_url"] = (
		f"{get_site_login_url()}?site={mrinimitable.local.site}"
		if on_mrinimitablecloud() and mrinimitable.conf.get("fc_communication_secret")
		else None
	)

	return context


@mrinimitable.whitelist(allow_guest=True)
def login_via_token(login_token: str):
	sid = mrinimitable.cache.get_value(f"login_token:{login_token}", expires=True)
	if not sid:
		mrinimitable.respond_as_web_page(_("Invalid Request"), _("Invalid Login Token"), http_status_code=417)
		return

	mrinimitable.local.form_dict.sid = sid
	mrinimitable.local.login_manager = LoginManager()

	redirect_post_login(
		desk_user=mrinimitable.db.get_value("User", mrinimitable.session.user, "user_type") == "System User"
	)


def get_login_with_email_link_ratelimit() -> int:
	return mrinimitable.get_system_settings("rate_limit_email_link_login") or 5


@mrinimitable.whitelist(allow_guest=True)
@rate_limit(limit=get_login_with_email_link_ratelimit, seconds=60 * 60)
def send_login_link(email: str):
	if not mrinimitable.get_system_settings("login_with_email_link"):
		return

	expiry = mrinimitable.get_system_settings("login_with_email_link_expiry") or 10
	link = _generate_temporary_login_link(email, expiry)

	app_name = (
		mrinimitable.get_website_settings("app_name") or mrinimitable.get_system_settings("app_name") or _("Mrinimitable")
	)

	subject = _("Login To {0}").format(app_name)

	mrinimitable.sendmail(
		subject=subject,
		recipients=email,
		template="login_with_email_link",
		args={"link": link, "minutes": expiry, "app_name": app_name},
		now=True,
	)


def _generate_temporary_login_link(email: str, expiry: int):
	assert isinstance(email, str)

	if not mrinimitable.db.exists("User", email):
		mrinimitable.throw(_("User with email address {0} does not exist").format(email), mrinimitable.DoesNotExistError)
	key = mrinimitable.generate_hash()
	mrinimitable.cache.set_value(f"one_time_login_key:{key}", email, expires_in_sec=expiry * 60)

	return get_url(f"/api/method/mrinimitable.www.login.login_via_key?key={key}")


@mrinimitable.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=get_login_with_email_link_ratelimit, seconds=60 * 60)
def login_via_key(key: str):
	cache_key = f"one_time_login_key:{key}"
	email = mrinimitable.cache.get_value(cache_key)

	if email:
		mrinimitable.cache.delete_value(cache_key)
		mrinimitable.local.login_manager.login_as(email)

		redirect_post_login(
			desk_user=mrinimitable.db.get_value("User", mrinimitable.session.user, "user_type") == "System User"
		)
	else:
		mrinimitable.respond_as_web_page(
			_("Not Permitted"),
			_("The link you trying to login is invalid or expired."),
			http_status_code=403,
			indicator_color="red",
		)


def sanitize_redirect(redirect: str | None) -> str | None:
	"""Only allow redirect on same domain.

	Allowed redirects:
	- Same host e.g. https://mrinimitable.localhost/path
	- Just path e.g. /app
	"""
	if not redirect:
		return redirect

	parsed_redirect = urlparse(redirect)
	if not parsed_redirect.netloc:
		return redirect

	parsed_request_host = urlparse(mrinimitable.local.request.url)
	if parsed_request_host.netloc == parsed_redirect.netloc:
		return redirect

	return None
