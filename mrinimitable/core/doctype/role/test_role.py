# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.core.doctype.role.role import get_info_based_on_role
from mrinimitable.tests import IntegrationTestCase


class TestUser(IntegrationTestCase):
	def test_disable_role(self):
		mrinimitable.get_doc("User", "test@example.com").add_roles("_Test Role 3")

		role = mrinimitable.get_doc("Role", "_Test Role 3")
		role.disabled = 1
		role.save()

		self.assertTrue("_Test Role 3" not in mrinimitable.get_roles("test@example.com"))

		role = mrinimitable.get_doc("Role", "_Test Role 3")
		role.disabled = 0
		role.save()

		mrinimitable.get_doc("User", "test@example.com").add_roles("_Test Role 3")
		self.assertTrue("_Test Role 3" in mrinimitable.get_roles("test@example.com"))

	def test_change_desk_access(self):
		"""if we change desk acecss from role, remove from user"""
		mrinimitable.delete_doc_if_exists("User", "test-user-for-desk-access@example.com")
		mrinimitable.delete_doc_if_exists("Role", "desk-access-test")
		user = mrinimitable.get_doc(
			doctype="User", email="test-user-for-desk-access@example.com", first_name="test"
		).insert()
		role = mrinimitable.get_doc(doctype="Role", role_name="desk-access-test", desk_access=0).insert()
		user.add_roles(role.name)
		user.save()
		self.assertTrue(user.user_type == "Website User")
		role.desk_access = 1
		role.save()
		user.reload()
		self.assertTrue(user.user_type == "System User")
		role.desk_access = 0
		role.save()
		user.reload()
		self.assertTrue(user.user_type == "Website User")

	def test_get_users_by_role(self):
		role = "System Manager"
		sys_managers = get_info_based_on_role(role, field="name")

		for user in sys_managers:
			self.assertIn(role, mrinimitable.get_roles(user))
