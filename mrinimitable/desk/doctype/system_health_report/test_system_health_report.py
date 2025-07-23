# Copyright (c) 2024, Mrinimitable Technologies and Contributors
# See license.txt

import mrinimitable
from mrinimitable.tests import IntegrationTestCase


class TestSystemHealthReport(IntegrationTestCase):
	def test_it_works(self):
		mrinimitable.get_doc("System Health Report")
