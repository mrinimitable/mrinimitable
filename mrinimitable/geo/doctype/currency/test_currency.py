# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# pre loaded

import mrinimitable
from mrinimitable.tests import IntegrationTestCase


class TestUser(IntegrationTestCase):
	def test_default_currency_on_setup(self):
		usd = mrinimitable.get_doc("Currency", "USD")
		self.assertDocumentEqual({"enabled": 1, "fraction": "Cent"}, usd)
