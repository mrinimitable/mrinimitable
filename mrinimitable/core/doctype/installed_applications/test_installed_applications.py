# Copyright (c) 2020, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.core.doctype.installed_applications.installed_applications import (
	InvalidAppOrder,
	update_installed_apps_order,
)
from mrinimitable.tests import IntegrationTestCase


class TestInstalledApplications(IntegrationTestCase):
	def test_order_change(self):
		update_installed_apps_order(["mrinimitable"])
		self.assertRaises(InvalidAppOrder, update_installed_apps_order, [])
		self.assertRaises(InvalidAppOrder, update_installed_apps_order, ["mrinimitable", "deepmind"])
