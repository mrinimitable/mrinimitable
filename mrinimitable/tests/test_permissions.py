# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Use blog post test to test user permissions logic"""

import mrinimitable
import mrinimitable.defaults
import mrinimitable.model.meta
import mrinimitable.permissions
from mrinimitable.core.doctype.doctype.test_doctype import new_doctype
from mrinimitable.core.doctype.user_permission.user_permission import clear_user_permissions
from mrinimitable.core.page.permission_manager.permission_manager import add, remove, reset, update
from mrinimitable.desk.form.load import getdoc
from mrinimitable.installer import _delete_doctypes
from mrinimitable.permissions import (
	ALL_USER_ROLE,
	AUTOMATIC_ROLES,
	GUEST_ROLE,
	SYSTEM_USER_ROLE,
	add_permission,
	add_user_permission,
	clear_user_permissions_for_doctype,
	get_doc_permissions,
	get_doctypes_with_read,
	remove_user_permission,
	update_permission_property,
)
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.tests.test_helpers import setup_for_tests
from mrinimitable.tests.utils import make_test_records_for_doctype
from mrinimitable.utils.data import now_datetime

EXTRA_TEST_RECORD_DEPENDENCIES = ["User", "Contact", "Salutation"]


class TestPermissions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_for_tests()
		mrinimitable.clear_cache(doctype="Test Blog Post")
		user = mrinimitable.get_doc("User", "test1@example.com")
		user.add_roles("Website Manager")
		user.add_roles("System Manager")

		user = mrinimitable.get_doc("User", "test2@example.com")
		user.add_roles("Blogger")

		user = mrinimitable.get_doc("User", "test3@example.com")
		user.add_roles("Sales User")

		user = mrinimitable.get_doc("User", "testperm@example.com")
		user.add_roles("Website Manager")

	def setUp(self):
		mrinimitable.clear_cache(doctype="Test Blog Post")

		reset("Test Blogger")
		reset("Test Blog Post")

		mrinimitable.db.delete("User Permission")

		mrinimitable.set_user("test1@example.com")

	def tearDown(self):
		mrinimitable.set_user("Administrator")
		mrinimitable.db.set_value("Test Blogger", "_Test Blogger 1", "user", None)

		clear_user_permissions_for_doctype("Test Blog Category")
		clear_user_permissions_for_doctype("Test Blog Post")
		clear_user_permissions_for_doctype("Test Blogger")

	@staticmethod
	def set_strict_user_permissions(ignore):
		ss = mrinimitable.get_doc("System Settings")
		ss.apply_strict_user_permissions = ignore
		ss.flags.ignore_mandatory = 1
		ss.save()

	def test_basic_permission(self):
		post = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(post.has_permission("read"))

	def test_select_permission(self):
		# grant only select perm to blog post
		add_permission("Test Blog Post", "Sales User", 0)
		update_permission_property("Test Blog Post", "Sales User", 0, "select", 1)
		update_permission_property("Test Blog Post", "Sales User", 0, "read", 0)
		update_permission_property("Test Blog Post", "Sales User", 0, "write", 0)

		mrinimitable.clear_cache(doctype="Test Blog Post")
		mrinimitable.set_user("test3@example.com")

		# validate select perm
		post = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(post.has_permission("select"))

		# validate does not have read and write perm
		self.assertFalse(post.has_permission("read"))
		self.assertRaises(mrinimitable.PermissionError, post.save)

		permitted_record = mrinimitable.get_list("Test Blog Post", fields="*", limit=1)[0]
		full_record = mrinimitable.get_all("Test Blog Post", fields="*", limit=1)[0]
		self.assertNotEqual(permitted_record, full_record)
		self.assertSequenceSubset(post.meta.get_search_fields(), permitted_record)

	def test_user_permissions_in_doc(self):
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		mrinimitable.set_user("test2@example.com")

		post = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertFalse(post.has_permission("read"))
		self.assertFalse(get_doc_permissions(post).get("read"))

		post1 = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertTrue(post1.has_permission("read"))
		self.assertTrue(get_doc_permissions(post1).get("read"))

	def test_user_permissions_in_report(self):
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		mrinimitable.set_user("test2@example.com")
		names = [d.name for d in mrinimitable.get_list("Test Blog Post", fields=["name", "blog_category"])]

		self.assertTrue("_Test Blog Post 1" in names)
		self.assertFalse("_Test Blog Post" in names)

	def test_default_values(self):
		doc = mrinimitable.new_doc("Test Blog Post")
		self.assertFalse(doc.get("blog_category"))

		# Fetch default based on single user permission
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		mrinimitable.set_user("test2@example.com")
		doc = mrinimitable.new_doc("Test Blog Post")
		self.assertEqual(doc.get("blog_category"), "_Test Blog Category 1")

		# Don't fetch default if user permissions is more than 1
		add_user_permission(
			"Test Blog Category", "_Test Blog Category", "test2@example.com", ignore_permissions=True
		)
		mrinimitable.clear_cache()
		doc = mrinimitable.new_doc("Test Blog Post")
		self.assertFalse(doc.get("blog_category"))

		# Fetch user permission set as default from multiple user permission
		add_user_permission(
			"Test Blog Category",
			"_Test Blog Category 2",
			"test2@example.com",
			ignore_permissions=True,
			is_default=1,
		)
		mrinimitable.clear_cache()
		doc = mrinimitable.new_doc("Test Blog Post")
		self.assertEqual(doc.get("blog_category"), "_Test Blog Category 2")

	def test_user_link_match_doc(self):
		blogger = mrinimitable.get_doc("Test Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()
		mrinimitable.permissions.add_user_permission("Test Blogger", blogger.name, blogger.user)

		mrinimitable.set_user("test2@example.com")

		post = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 2")
		self.assertTrue(post.has_permission("read"))
		post1 = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(post1.has_permission("read"))

	def test_user_link_match_report(self):
		blogger = mrinimitable.get_doc("Test Blogger", "_Test Blogger 1")
		blogger.user = "test2@example.com"
		blogger.save()
		mrinimitable.permissions.add_user_permission("Test Blogger", blogger.name, blogger.user)

		mrinimitable.set_user("test2@example.com")

		names = [d.name for d in mrinimitable.get_list("Test Blog Post", fields=["name", "owner"])]
		self.assertTrue("_Test Blog Post 2" in names)
		self.assertFalse("_Test Blog Post 1" in names)

	def test_set_user_permissions(self):
		mrinimitable.set_user("test1@example.com")
		add_user_permission("Test Blog Post", "_Test Blog Post", "test2@example.com")

	def test_not_allowed_to_set_user_permissions(self):
		mrinimitable.set_user("test2@example.com")

		# this user can't add user permissions
		self.assertRaises(
			mrinimitable.PermissionError,
			add_user_permission,
			"Test Blog Post",
			"_Test Blog Post",
			"test2@example.com",
		)

	def test_read_if_explicit_user_permissions_are_set(self):
		self.test_set_user_permissions()

		mrinimitable.set_user("test2@example.com")

		# user can only access permitted blog post
		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(doc.has_permission("read"))

		# and not this one
		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(doc.has_permission("read"))

	def test_not_allowed_to_remove_user_permissions(self):
		self.test_set_user_permissions()

		mrinimitable.set_user("test2@example.com")

		# user cannot remove their own user permissions
		self.assertRaises(
			mrinimitable.PermissionError,
			remove_user_permission,
			"Test Blog Post",
			"_Test Blog Post",
			"test2@example.com",
		)

	def test_user_permissions_if_applied_on_doc_being_evaluated(self):
		mrinimitable.set_user("test2@example.com")
		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertTrue(doc.has_permission("read"))

		mrinimitable.set_user("test1@example.com")
		add_user_permission("Test Blog Post", "_Test Blog Post", "test2@example.com")

		mrinimitable.set_user("test2@example.com")
		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(doc.has_permission("read"))

		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertTrue(doc.has_permission("read"))

	def test_set_standard_fields_manually(self):
		# check that creation and owner cannot be set manually
		from datetime import timedelta

		fake_creation = now_datetime() + timedelta(days=-7)
		fake_owner = mrinimitable.db.get_value("User", {"name": ("!=", mrinimitable.session.user)})

		d = mrinimitable.new_doc("ToDo")
		d.description = "ToDo created via test_set_standard_fields_manually"
		d.creation = fake_creation
		d.owner = fake_owner
		d.save()
		self.assertNotEqual(d.creation, fake_creation)
		self.assertNotEqual(d.owner, fake_owner)

	def test_dont_change_standard_constants(self):
		# check that Document.creation cannot be changed
		user = mrinimitable.get_doc("User", mrinimitable.session.user)
		user.creation = now_datetime()
		self.assertRaises(mrinimitable.CannotChangeConstantError, user.save)

		# check that Document.owner cannot be changed
		user.reload()
		user.owner = "Guest"
		self.assertRaises(mrinimitable.CannotChangeConstantError, user.save)

	def test_set_only_once(self):
		blog_post = mrinimitable.get_meta("Test Blog Post")
		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 1")
		doc.db_set("title", "Old")
		blog_post.get_field("title").set_only_once = 1
		doc.title = "New"
		self.assertRaises(mrinimitable.CannotChangeConstantError, doc.save)
		blog_post.get_field("title").set_only_once = 0

	def test_set_only_once_child_table_rows(self):
		doctype_meta = mrinimitable.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = mrinimitable.get_doc("DocType", "Test Blog Post")

		# remove last one
		doc.fields = doc.fields[:-1]
		self.assertRaises(mrinimitable.CannotChangeConstantError, doc.save)
		mrinimitable.clear_cache(doctype="DocType")

	def test_set_only_once_child_table_row_value(self):
		doctype_meta = mrinimitable.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = mrinimitable.get_doc("DocType", "Test Blog Post")
		# change one property from the child table
		doc.fields[-3].fieldtype = "Check"
		self.assertRaises(mrinimitable.CannotChangeConstantError, doc.save)
		mrinimitable.clear_cache(doctype="DocType")

	def test_set_only_once_child_table_okay(self):
		doctype_meta = mrinimitable.get_meta("DocType")
		doctype_meta.get_field("fields").set_only_once = 1
		doc = mrinimitable.get_doc("DocType", "Test Blog Post")

		doc.load_doc_before_save()
		self.assertFalse(doc.validate_set_only_once())
		mrinimitable.clear_cache(doctype="DocType")

	def test_user_permission_doctypes(self):
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")
		add_user_permission("Test Blogger", "_Test Blogger 1", "test2@example.com")

		mrinimitable.set_user("test2@example.com")

		mrinimitable.clear_cache(doctype="Test Blog Post")

		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post")
		self.assertFalse(doc.has_permission("read"))

		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 2")
		self.assertTrue(doc.has_permission("read"))

		mrinimitable.clear_cache(doctype="Test Blog Post")

	def if_owner_setup(self):
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)

		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")
		add_user_permission("Test Blogger", "_Test Blogger 1", "test2@example.com")

		mrinimitable.clear_cache(doctype="Test Blog Post")

	def test_insert_if_owner_with_user_permissions(self):
		"""If `If Owner` is checked for a Role, check if that document
		is allowed to be read, updated, submitted, etc. except be created,
		even if the document is restricted based on User Permissions."""
		mrinimitable.delete_doc("Test Blog Post", "-test-blog-post-title")

		self.if_owner_setup()

		mrinimitable.set_user("test2@example.com")

		doc = mrinimitable.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title",
				"content": "_Test Blog Post Content",
			}
		)

		self.assertRaises(mrinimitable.PermissionError, doc.insert)

		mrinimitable.set_user("test1@example.com")
		add_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")

		mrinimitable.set_user("test2@example.com")
		doc.insert()

		mrinimitable.set_user("Administrator")
		remove_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")
		mrinimitable.clear_cache()
		mrinimitable.set_user("test2@example.com")
		doc = mrinimitable.get_doc(doc.doctype, doc.name)

		self.assertTrue(doc.has_permission("read"))
		self.assertTrue(doc.has_permission("write"))
		self.assertFalse(doc.has_permission("create"))

		# delete created record
		mrinimitable.set_user("Administrator")
		mrinimitable.delete_doc("Test Blog Post", "_Test Blog Post Title")

	def test_ignore_user_permissions_if_missing(self):
		"""If there are no user permissions, then allow as per role"""

		add_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")
		mrinimitable.set_user("test2@example.com")

		doc = mrinimitable.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category 2",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title",
				"content": "_Test Blog Post Content",
			}
		)

		self.assertFalse(doc.has_permission("write"))

		mrinimitable.set_user("Administrator")
		remove_user_permission("Test Blog Category", "_Test Blog Category", "test2@example.com")

		mrinimitable.set_user("test2@example.com")
		self.assertTrue(doc.has_permission("write"))

	def test_strict_user_permissions(self):
		"""If `Strict User Permissions` is checked in System Settings,
		show records even if User Permissions are missing for a linked
		doctype"""

		mrinimitable.set_user("Administrator")
		mrinimitable.db.delete("Contact")
		mrinimitable.db.delete("Contact Email")
		mrinimitable.db.delete("Contact Phone")

		reset("Salutation")
		reset("Contact")

		make_test_records_for_doctype("Contact", force=True)

		add_user_permission("Salutation", "Mr", "test3@example.com")
		self.set_strict_user_permissions(0)

		allowed_contact = mrinimitable.get_doc("Contact", "_Test Contact For _Test Customer")
		other_contact = mrinimitable.get_doc("Contact", "_Test Contact For _Test Supplier")

		mrinimitable.set_user("test3@example.com")
		self.assertTrue(allowed_contact.has_permission("read"))
		self.assertTrue(other_contact.has_permission("read"))
		self.assertEqual(len(mrinimitable.get_list("Contact")), 2)

		mrinimitable.set_user("Administrator")
		self.set_strict_user_permissions(1)

		mrinimitable.set_user("test3@example.com")
		self.assertTrue(allowed_contact.has_permission("read"))
		self.assertFalse(other_contact.has_permission("read"))
		self.assertTrue(len(mrinimitable.get_list("Contact")), 1)

		# This is a temporary WIP doc that user is using run_doc_method on
		local_doc = mrinimitable.copy_doc(other_contact)
		self.assertTrue(local_doc.has_permission("read"))

		mrinimitable.set_user("Administrator")
		self.set_strict_user_permissions(0)

		clear_user_permissions_for_doctype("Salutation")
		clear_user_permissions_for_doctype("Contact")

	def test_user_permission_is_not_applied_if_user_roles_does_not_have_permission(self):
		add_user_permission("Test Blog Post", "_Test Blog Post 1", "test3@example.com")
		mrinimitable.set_user("test3@example.com")
		doc = mrinimitable.get_doc("Test Blog Post", "_Test Blog Post 1")
		self.assertFalse(doc.has_permission("read"))

		mrinimitable.set_user("Administrator")
		user = mrinimitable.get_doc("User", "test3@example.com")
		user.add_roles("Blogger")
		mrinimitable.set_user("test3@example.com")
		self.assertTrue(doc.has_permission("read"))

		mrinimitable.set_user("Administrator")
		user.remove_roles("Blogger")

	def test_contextual_user_permission(self):
		# should be applicable for across all doctypes
		add_user_permission("Test Blogger", "_Test Blogger", "test2@example.com")
		# should be applicable only while accessing Blog Post
		add_user_permission(
			"Test Blogger", "_Test Blogger 1", "test2@example.com", applicable_for="Test Blog Post"
		)
		# should be applicable only while accessing User
		add_user_permission("Test Blogger", "_Test Blogger 2", "test2@example.com", applicable_for="User")

		posts = mrinimitable.get_all("Test Blog Post", fields=["name", "blogger"])

		# Get all posts for admin
		self.assertEqual(len(posts), 4)

		mrinimitable.set_user("test2@example.com")

		posts = mrinimitable.get_list("Test Blog Post", fields=["name", "blogger"])

		# Should get only posts with allowed blogger via user permission
		# only '_Test Blogger', '_Test Blogger 1' are allowed in Blog Post
		self.assertEqual(len(posts), 3)

		for post in posts:
			self.assertIn(
				post.blogger,
				["_Test Blogger", "_Test Blogger 1"],
				f"A post from {post.blogger} is not expected.",
			)

	def test_if_owner_permission_overrides_properly(self):
		# check if user is not granted access if the user is not the owner of the doc
		# Blogger has only read access on the blog post unless he is the owner of the blog
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1, 1)
		update("Test Blog Post", "Blogger", 0, "write", 1, 1)
		update("Test Blog Post", "Blogger", 0, "delete", 1, 1)

		# currently test2 user has not created any document
		# still he should be able to do get_list query which should
		# not raise permission error but simply return empty list
		mrinimitable.set_user("test2@example.com")
		self.assertEqual(mrinimitable.get_list("Test Blog Post"), [])

		mrinimitable.set_user("Administrator")

		# creates a custom docperm with just read access
		# now any user can read any blog post (but other rights are limited to the blog post owner)
		add_permission("Test Blog Post", "Blogger")
		mrinimitable.clear_cache(doctype="Test Blog Post")

		mrinimitable.delete_doc("Test Blog Post", "_Test Blog Post Title")

		mrinimitable.set_user("test1@example.com")

		doc = mrinimitable.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title",
				"content": "_Test Blog Post Content",
			}
		)

		doc.insert()

		mrinimitable.set_user("test2@example.com")
		doc = mrinimitable.get_doc(doc.doctype, doc.name)

		self.assertTrue(doc.has_permission("read"))
		self.assertFalse(doc.has_permission("write"))
		self.assertFalse(doc.has_permission("delete"))

		# check if owner of the doc has the access that is available only for the owner of the doc
		mrinimitable.set_user("test1@example.com")
		doc = mrinimitable.get_doc(doc.doctype, doc.name)

		self.assertTrue(doc.has_permission("read"))
		self.assertTrue(doc.has_permission("write"))
		self.assertTrue(doc.has_permission("delete"))

		# delete the created doc
		mrinimitable.delete_doc("Test Blog Post", "_Test Blog Post Title")

	def test_if_owner_permission_on_getdoc(self):
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1)
		update("Test Blog Post", "Blogger", 0, "write", 1)
		update("Test Blog Post", "Blogger", 0, "delete", 1)
		mrinimitable.clear_cache(doctype="Test Blog Post")

		mrinimitable.set_user("test1@example.com")

		doc = mrinimitable.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test Blog Post Title New",
				"content": "_Test Blog Post Content",
			}
		)

		doc.insert()

		getdoc("Test Blog Post", doc.name)
		doclist = [d.name for d in mrinimitable.response.docs]
		self.assertTrue(doc.name in doclist)

		mrinimitable.set_user("test2@example.com")
		self.assertRaises(mrinimitable.PermissionError, getdoc, "Test Blog Post", doc.name)

	def test_if_owner_permission_on_get_list(self):
		doc = mrinimitable.get_doc(
			{
				"doctype": "Test Blog Post",
				"blog_category": "_Test Blog Category",
				"blogger": "_Test Blogger 1",
				"title": "_Test If Owner Permissions on Get List",
				"content": "_Test Blog Post Content",
			}
		)

		doc.insert(ignore_if_duplicate=True)

		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1)
		user = mrinimitable.get_doc("User", "test2@example.com")
		user.add_roles("Website Manager")
		mrinimitable.clear_cache(doctype="Test Blog Post")

		mrinimitable.set_user("test2@example.com")
		self.assertIn(doc.name, mrinimitable.get_list("Test Blog Post", pluck="name"))

		# Become system manager to remove role
		mrinimitable.set_user("test1@example.com")
		user.remove_roles("Website Manager")
		mrinimitable.clear_cache(doctype="Test Blog Post")

		mrinimitable.set_user("test2@example.com")
		self.assertNotIn(doc.name, mrinimitable.get_list("Test Blog Post", pluck="name"))

	def test_if_owner_permission_on_delete(self):
		update("Test Blog Post", "Blogger", 0, "if_owner", 1)
		update("Test Blog Post", "Blogger", 0, "read", 1, 1)
		update("Test Blog Post", "Blogger", 0, "write", 1, 1)
		update("Test Blog Post", "Blogger", 0, "delete", 1, 1)

		# Remove delete perm
		update("Test Blog Post", "Website Manager", 0, "delete", 0)

		mrinimitable.clear_cache(doctype="Test Blog Post")

		with self.set_user("test2@example.com"):
			doc = mrinimitable.get_doc(
				{
					"doctype": "Test Blog Post",
					"blog_category": "_Test Blog Category",
					"blogger": "_Test Blogger 1",
					"title": "_Test Blog Post Title New 1",
					"content": "_Test Blog Post Content",
				}
			)

			doc.insert()

			getdoc("Test Blog Post", doc.name)
			doclist = [d.name for d in mrinimitable.response.docs]
			self.assertTrue(doc.name in doclist)

		with self.set_user("testperm@example.com"):
			# Website Manager able to read
			getdoc("Test Blog Post", doc.name)
			doclist = [d.name for d in mrinimitable.response.docs]
			self.assertTrue(doc.name in doclist)

			# Website Manager should not be able to delete
			self.assertRaises(mrinimitable.PermissionError, mrinimitable.delete_doc, "Test Blog Post", doc.name)

		with self.set_user("test2@example.com"):
			mrinimitable.delete_doc("Test Blog Post", "_Test Blog Post Title New 1")

		update("Test Blog Post", "Website Manager", 0, "delete", 1, 1)

	def test_clear_user_permissions(self):
		current_user = mrinimitable.session.user
		mrinimitable.set_user("Administrator")
		clear_user_permissions_for_doctype("Test Blog Category", "test2@example.com")
		clear_user_permissions_for_doctype("Test Blog Post", "test2@example.com")

		add_user_permission("Test Blog Post", "_Test Blog Post 1", "test2@example.com")
		add_user_permission("Test Blog Post", "_Test Blog Post 2", "test2@example.com")
		add_user_permission("Test Blog Category", "_Test Blog Category 1", "test2@example.com")

		deleted_user_permission_count = clear_user_permissions("test2@example.com", "Test Blog Post")

		self.assertEqual(deleted_user_permission_count, 2)

		blog_post_user_permission_count = mrinimitable.db.count(
			"User Permission", filters={"user": "test2@example.com", "allow": "Test Blog Post"}
		)

		self.assertEqual(blog_post_user_permission_count, 0)

		blog_category_user_permission_count = mrinimitable.db.count(
			"User Permission", filters={"user": "test2@example.com", "allow": "Test Blog Category"}
		)

		self.assertEqual(blog_category_user_permission_count, 1)

		# reset the user
		mrinimitable.set_user(current_user)

	def test_child_permissions(self):
		mrinimitable.set_user("test3@example.com")
		self.assertIsInstance(mrinimitable.get_list("DefaultValue", parent_doctype="User", limit=1), list)

		# mrinimitable.get_list
		self.assertRaises(mrinimitable.PermissionError, mrinimitable.get_list, "DefaultValue")
		self.assertRaises(mrinimitable.PermissionError, mrinimitable.get_list, "DefaultValue", parent_doctype="ToDo")
		self.assertRaises(
			mrinimitable.PermissionError, mrinimitable.get_list, "DefaultValue", parent_doctype="DefaultValue"
		)

		# mrinimitable.get_doc
		user = mrinimitable.get_doc("User", mrinimitable.session.user)
		doc = user.append("defaults")
		doc.check_permission()

		# false due to missing parentfield
		doc = user.append("roles")
		doc.parentfield = None
		self.assertRaises(mrinimitable.PermissionError, doc.check_permission)

		# false due to invalid parentfield
		doc = user.append("roles")
		doc.parentfield = "first_name"
		self.assertRaises(mrinimitable.PermissionError, doc.check_permission)

		# false by permlevel
		doc = user.append("roles")
		self.assertRaises(mrinimitable.PermissionError, doc.check_permission)

		# false by user permission
		user = mrinimitable.get_doc("User", "Administrator")
		doc = user.append("defaults")
		self.assertRaises(mrinimitable.PermissionError, doc.check_permission)

	def test_select_user(self):
		"""If test3@example.com is restricted by a User Permission to see only
		users linked to a certain doctype (in this case: Gender "Female"), he
		should not be able to query other users (Gender "Male").
		"""
		# ensure required genders exist
		for gender in ("Male", "Female"):
			if mrinimitable.db.exists("Gender", gender):
				continue

			mrinimitable.get_doc({"doctype": "Gender", "gender": gender}).insert()

		# asssign gender to test users
		mrinimitable.db.set_value("User", "test1@example.com", "gender", "Male")
		mrinimitable.db.set_value("User", "test2@example.com", "gender", "Female")
		mrinimitable.db.set_value("User", "test3@example.com", "gender", "Female")

		# restrict test3@example.com to see only female users
		add_user_permission("Gender", "Female", "test3@example.com")

		# become user test3@example.com and see what users he can query
		mrinimitable.set_user("test3@example.com")
		users = mrinimitable.get_list("User", pluck="name")

		self.assertNotIn("test1@example.com", users)
		self.assertIn("test2@example.com", users)
		self.assertIn("test3@example.com", users)

	def test_automatic_permissions(self):
		def assertHasRole(*roles: str | tuple[str, ...]):
			for role in roles:
				self.assertIn(role, mrinimitable.get_roles())

		mrinimitable.set_user("Administrator")
		assertHasRole(*AUTOMATIC_ROLES)

		mrinimitable.set_user("Guest")
		assertHasRole(GUEST_ROLE)

		website_user = mrinimitable.db.get_value(
			"User",
			{"user_type": "Website User", "enabled": 1, "name": ("not in", AUTOMATIC_ROLES)},
		)
		mrinimitable.set_user(website_user)
		assertHasRole(GUEST_ROLE, ALL_USER_ROLE)

		system_user = mrinimitable.db.get_value(
			"User",
			{"user_type": "System User", "enabled": 1, "name": ("not in", AUTOMATIC_ROLES)},
		)
		mrinimitable.set_user(system_user)
		assertHasRole(GUEST_ROLE, ALL_USER_ROLE, SYSTEM_USER_ROLE)

	def test_get_doctypes_with_read(self):
		with self.set_user("Administrator"):
			doctype = new_doctype(permissions=[{"select": 1, "role": "_Test Role", "read": 0}]).insert().name

		with self.set_user("test@example.com"):
			self.assertNotIn(doctype, get_doctypes_with_read())

	def test_overrides_work_as_expected(self):
		"""custom docperms should completely override standard ones"""
		standard_role = "Desk User"
		custom_role = mrinimitable.new_doc("Role", role_name=mrinimitable.generate_hash()).insert().name
		with self.set_user("Administrator"):
			doctype = new_doctype(permissions=[{"role": standard_role, "read": 1}]).insert().name

		with self.set_user("test@example.com"):
			self.assertIn(doctype, get_doctypes_with_read())

		with self.set_user("Administrator"):
			# Allow perm to some other role and remove standard role
			add(doctype, custom_role, 0)
			remove(doctype, standard_role, 0)

		with self.set_user("test@example.com"):
			# No one has this role, so user shouldn't have permission.
			self.assertNotIn(doctype, get_doctypes_with_read())
