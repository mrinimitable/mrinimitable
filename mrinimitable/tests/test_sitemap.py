import mrinimitable
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.utils import get_html_for_route


class TestSitemap(IntegrationTestCase):
	def test_sitemap(self):
		xml = get_html_for_route("sitemap.xml")
		self.assertTrue("/about</loc>" in xml)
		self.assertTrue("/contact</loc>" in xml)
