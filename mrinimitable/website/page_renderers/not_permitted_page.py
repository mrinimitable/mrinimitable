from urllib.parse import quote_plus

import mrinimitable
from mrinimitable import _
from mrinimitable.utils import cstr
from mrinimitable.website.page_renderers.template_page import TemplatePage


class NotPermittedPage(TemplatePage):
	def __init__(self, path=None, http_status_code=None, exception=""):
		mrinimitable.local.message = cstr(exception)
		super().__init__(path=path, http_status_code=http_status_code)
		self.http_status_code = 403

	def can_render(self):
		return True

	def render(self):
		action = f"/login?redirect-to={quote_plus(mrinimitable.request.path)}"
		if mrinimitable.request.path.startswith("/app/") or mrinimitable.request.path == "/app":
			action = "/login"
		mrinimitable.local.message_title = _("Not Permitted")
		mrinimitable.local.response["context"] = dict(
			indicator_color="red", primary_action=action, primary_label=_("Login"), fullpage=True
		)
		self.set_standard_path("message")
		return super().render()
