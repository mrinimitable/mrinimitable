# Copyright (c) 2018, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import hashlib

import mrinimitable
from mrinimitable.tests import IntegrationTestCase


class TestTransactionLog(IntegrationTestCase):
	def test_validate_chaining(self):
		mrinimitable.get_doc(
			{
				"doctype": "Transaction Log",
				"reference_doctype": "Test Doctype",
				"document_name": "Test Document 1",
				"data": "first_data",
			}
		).insert(ignore_permissions=True)

		second_log = mrinimitable.get_doc(
			{
				"doctype": "Transaction Log",
				"reference_doctype": "Test Doctype",
				"document_name": "Test Document 2",
				"data": "second_data",
			}
		).insert(ignore_permissions=True)

		third_log = mrinimitable.get_doc(
			{
				"doctype": "Transaction Log",
				"reference_doctype": "Test Doctype",
				"document_name": "Test Document 3",
				"data": "third_data",
			}
		).insert(ignore_permissions=True)

		sha = hashlib.sha256()
		sha.update(
			mrinimitable.safe_encode(str(third_log.transaction_hash))
			+ mrinimitable.safe_encode(str(second_log.chaining_hash))
		)

		self.assertEqual(sha.hexdigest(), third_log.chaining_hash)
