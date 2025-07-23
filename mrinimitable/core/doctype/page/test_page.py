# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import unittest
from unittest.mock import patch

import mrinimitable
from mrinimitable.tests import IntegrationTestCase


class TestPage(IntegrationTestCase):
	def test_naming(self):
		self.assertRaises(
			mrinimitable.NameError,
			mrinimitable.get_doc(doctype="Page", page_name="DocType", module="Core").insert,
		)

	@unittest.skipUnless(
		os.access(mrinimitable.get_app_path("mrinimitable"), os.W_OK), "Only run if mrinimitable app paths is writable"
	)
	@patch.dict(mrinimitable.conf, {"developer_mode": 1})
	def test_trashing(self):
		page = mrinimitable.new_doc("Page", page_name=mrinimitable.generate_hash(), module="Core").insert()

		page.delete()
		mrinimitable.db.commit()

		module_path = mrinimitable.get_module_path(page.module)
		dir_path = os.path.join(module_path, "page", mrinimitable.scrub(page.name))

		self.assertFalse(os.path.exists(dir_path))
