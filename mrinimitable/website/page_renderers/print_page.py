import mrinimitable
from mrinimitable.website.page_renderers.template_page import TemplatePage


class PrintPage(TemplatePage):
	"""
	default path returns a printable object (based on permission)
	/Quotation/Q-0001
	"""

	def can_render(self):
		parts = self.path.split("/", 1)
		if len(parts) != 2 or not mrinimitable.db.exists("DocType", parts[0], True):
			return False

		return True

	def render(self):
		parts = self.path.split("/", 1)
		mrinimitable.form_dict.doctype = parts[0]
		mrinimitable.form_dict.name = parts[1]
		self.set_standard_path("printview")
		return super().render()
