# Copyright (c) 2015, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import mrinimitable
from mrinimitable.contacts.doctype.address_template.address_template import get_default_address_template
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.utils.jinja import validate_template


class TestAddressTemplate(IntegrationTestCase):
	def setUp(self) -> None:
		mrinimitable.db.delete("Address Template", {"country": "India"})
		mrinimitable.db.delete("Address Template", {"country": "Brazil"})

	def test_default_address_template(self):
		validate_template(get_default_address_template())

	def test_default_is_unset(self):
		mrinimitable.get_doc({"doctype": "Address Template", "country": "India", "is_default": 1}).insert()

		self.assertEqual(mrinimitable.db.get_value("Address Template", "India", "is_default"), 1)

		mrinimitable.get_doc({"doctype": "Address Template", "country": "Brazil", "is_default": 1}).insert()

		self.assertEqual(mrinimitable.db.get_value("Address Template", "India", "is_default"), 0)
		self.assertEqual(mrinimitable.db.get_value("Address Template", "Brazil", "is_default"), 1)

	def test_delete_address_template(self):
		india = mrinimitable.get_doc({"doctype": "Address Template", "country": "India", "is_default": 0}).insert()

		brazil = mrinimitable.get_doc(
			{"doctype": "Address Template", "country": "Brazil", "is_default": 1}
		).insert()

		india.reload()  # might have been modified by the second template
		india.delete()  # should not raise an error

		self.assertRaises(mrinimitable.ValidationError, brazil.delete)
