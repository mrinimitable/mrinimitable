# Copyright (c) 2025, Mrinimitable Technologies and Contributors
# See license.txt

import re

import mrinimitable
import mrinimitable.utils
from mrinimitable.core.api.user_invitation import (
	_accept_invitation,
	cancel_invitation,
	get_pending_invitations,
	invite_by_email,
)
from mrinimitable.core.doctype.user_invitation.user_invitation import mark_expired_invitations
from mrinimitable.tests import IntegrationTestCase

emails = [
	"test_user_invite1@example.com",
	"test_user_invite2@example.com",
	"test_user_invite3@example.com",
	"test_user_invite4@example.com",
	"test_user_invite5@example.com",
	"test_user_invite6@example.com",
]


class IntegrationTestUserInvitation(IntegrationTestCase):
	"""
	Integration tests for UserInvitation.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		user = mrinimitable.new_doc("User")
		user.first_name = "Test"
		user.last_name = "123"
		user.email = emails[0]
		user.append_roles("System Manager")
		user.insert()
		mrinimitable.set_user(emails[0])

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		IntegrationTestUserInvitation.delete_all_invitations()
		IntegrationTestUserInvitation.delete_all_user_roles()
		mrinimitable.db.delete("Email Queue")
		for user_email in emails:
			if mrinimitable.db.exists("User", user_email):
				mrinimitable.delete_doc("User", user_email)
		mrinimitable.set_user("Administrator")
		# some of the code under test commit internally
		mrinimitable.db.commit()  # nosemgrep

	@classmethod
	def delete_all_user_roles(cls):
		mrinimitable.db.sql("DELETE FROM `tabUser Role`")

	@classmethod
	def delete_all_invitations(cls):
		mrinimitable.db.sql("DELETE FROM `tabUser Invitation`")

	@classmethod
	def delete_invitation(cls, name: str):
		mrinimitable.db.sql(f'DELETE FROM `tabUser Invitation` WHERE name = "{name}"')

	def setUp(self):
		super().setUp()
		IntegrationTestUserInvitation.delete_all_invitations()
		IntegrationTestUserInvitation.delete_all_user_roles()
		mrinimitable.db.delete("Email Queue")

	def test_insert_invitation(self):
		invitation = self.get_dummy_invitation()
		self.assertEqual(len(self.get_email_names()), 0)
		invitation.insert()
		self.assertEqual(invitation.invited_by, mrinimitable.session.user)
		self.assertEqual(invitation.status, "Pending")
		self.assertIsInstance(invitation.email_sent_at, str)
		self.assertIsInstance(invitation.key, str)
		self.assertIsInstance(invitation.roles, list)
		sent_emails = self.get_email_messages()
		self.assertEqual(len(sent_emails), 1)
		self.assertIn("invited", sent_emails[0].message.lower())

	def test_update_invitation_status_to_expired(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_email_names()), 1)
		invitation.expire()
		emails = self.get_email_messages(False)
		self.assertEqual(len(emails), 2)
		self.assertIn("expired", emails[0].message.lower())

	def test_cancel_pending_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_email_names(False)), 1)
		self.assertEqual(invitation.status, "Pending")
		invitation.cancel_invite()
		sent_emails = self.get_email_messages(False)
		self.assertEqual(len(sent_emails), 2)
		self.assertIn("cancelled", sent_emails[0].message.lower())

	def test_cancel_accepted_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_email_names(False)), 1)
		invitation.status = "Accepted"
		invitation.save()
		invitation.cancel_invite()
		self.assertEqual(len(self.get_email_names(False)), 1)

	def test_cancel_expired_invitation(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		self.assertEqual(len(self.get_email_names(False)), 1)
		invitation.expire()
		self.assertEqual(len(self.get_email_names(False)), 2)
		invitation.cancel_invite()
		self.assertEqual(len(self.get_email_names(False)), 2)

	def test_mark_expired_invitations(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		# the status of invitations older than 3 days should be set to expired
		invitation.db_set("creation", mrinimitable.utils.add_days(mrinimitable.utils.now(), -4))
		mark_expired_invitations()
		invitation.reload()
		self.assertEqual(invitation.status, "Expired")

	def test_invite_by_email_api(self):
		accepted_invite_email = emails[1]
		invitation = mrinimitable.get_doc(
			doctype="User Invitation",
			email=accepted_invite_email,
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="mrinimitable",
		).insert()
		invitation.accept()
		self.assertEqual(len(self.get_email_names(False)), 1)
		pending_invite_email = emails[2]
		mrinimitable.get_doc(
			doctype="User Invitation",
			email=pending_invite_email,
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="mrinimitable",
		).insert()
		self.assertEqual(len(self.get_email_names(False)), 2)
		email_to_invite = emails[3]
		res = invite_by_email(
			emails=", ".join([accepted_invite_email, pending_invite_email, email_to_invite]),
			roles=["System Manager"],
			redirect_to_path="/xyz",
		)
		self.assertSequenceEqual(res["disabled_user_emails"], [])
		self.assertSequenceEqual(res["accepted_invite_emails"], [accepted_invite_email])
		self.assertSequenceEqual(res["pending_invite_emails"], [pending_invite_email])
		self.assertSequenceEqual(res["invited_emails"], [email_to_invite])
		self.assertEqual(len(self.get_email_names(False)), 3)
		user = mrinimitable.get_doc("User", invitation.email)
		IntegrationTestUserInvitation.delete_invitation(invitation.name)
		mrinimitable.delete_doc("User", user.name)

	def test_invite_by_email_api_disabled_user(self):
		user = mrinimitable.new_doc("User")
		user.first_name = "Random"
		user.last_name = "User"
		user.email = emails[5]
		user.append_roles("System Manager")
		user.insert()
		user.reload()
		user.enabled = 0
		user.save()
		res = invite_by_email(
			emails=user.email,
			roles=["System Manager"],
			redirect_to_path="/xyz",
		)
		self.assertSequenceEqual(res["disabled_user_emails"], [user.email])
		self.assertSequenceEqual(res["accepted_invite_emails"], [])
		self.assertSequenceEqual(res["pending_invite_emails"], [])
		self.assertSequenceEqual(res["invited_emails"], [])
		mrinimitable.delete_doc("User", user.email)

	def test_accept_invitation_api_pass_redirect(self):
		invitation = mrinimitable.get_doc(
			doctype="User Invitation",
			email=emails[1],
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="mrinimitable",
		).insert()
		self.assertEqual(len(mrinimitable.get_all("User", filters={"email": invitation.email}, pluck="name")), 0)
		self.assertEqual(len(self.get_email_names(False)), 1)
		key = invitation._after_insert()
		self.assertEqual(len(self.get_email_names(False)), 2)
		_accept_invitation(key, True)
		res = mrinimitable.local.response
		self.assertEqual(res.type, "redirect")
		pattern = f"^{re.escape(mrinimitable.utils.get_url(''))}/update-password\\?key=.+&redirect_to=/abc$"
		self.assertRegex(res.location, pattern)
		user = mrinimitable.get_doc("User", invitation.email)
		IntegrationTestUserInvitation.delete_invitation(invitation.name)
		mrinimitable.delete_doc("User", user.name)

	def test_accept_invitation_api_direct_redirect(self):
		invitation = mrinimitable.get_doc(
			doctype="User Invitation",
			email=emails[1],
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="mrinimitable",
		).insert()
		self.assertEqual(len(mrinimitable.get_all("User", filters={"email": invitation.email}, pluck="name")), 0)
		original_disable_user_pass_login = mrinimitable.get_system_settings("disable_user_pass_login")
		mrinimitable.db.set_single_value("System Settings", "disable_user_pass_login", 1)
		self.assertEqual(len(self.get_email_names(False)), 1)
		key = invitation._after_insert()
		self.assertEqual(len(self.get_email_names(False)), 2)
		_accept_invitation(key, True)
		mrinimitable.db.set_single_value(
			"System Settings", "disable_user_pass_login", original_disable_user_pass_login
		)
		res = mrinimitable.local.response
		self.assertEqual(res.type, "redirect")
		pattern = f"^{re.escape(mrinimitable.utils.get_url(''))}/abc$"
		self.assertRegex(res.location, pattern)
		user = mrinimitable.get_doc("User", invitation.email)
		IntegrationTestUserInvitation.delete_invitation(invitation.name)
		mrinimitable.delete_doc("User", user.name)

	def test_get_pending_invitations_api(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		invitation.reload()
		pending_invitations = get_pending_invitations("mrinimitable")
		self.assertEqual(len(pending_invitations), 1)
		pending_invitation = pending_invitations[0]
		self.assertEqual(pending_invitation["name"], invitation.name)
		self.assertEqual(pending_invitation["email"], invitation.email)
		roles = pending_invitation["roles"]
		self.assertIsInstance(roles, list)
		self.assertSequenceEqual(roles, [r.role for r in invitation.roles])

	def test_cancel_invitation_api(self):
		invitation = self.get_dummy_invitation()
		invitation.insert()
		invitation.reload()
		self.assertEqual(invitation.status, "Pending")
		self.assertEqual(len(self.get_email_names()), 1)
		res = cancel_invitation(invitation.name, "mrinimitable")
		self.assertTrue(res["cancelled_now"])
		invitation.reload()
		self.assertEqual(invitation.status, "Cancelled")
		self.assertEqual(len(self.get_email_names()), 2)
		res = cancel_invitation(invitation.name, "mrinimitable")
		self.assertFalse(res["cancelled_now"])
		self.assertEqual(len(self.get_email_names()), 2)

	def get_dummy_invitation(self):
		return mrinimitable.get_doc(
			doctype="User Invitation",
			email=emails[1],
			roles=[dict(role="System Manager")],
			redirect_to_path="/abc",
			app_name="mrinimitable",
		)

	def get_email_names(self, sent_only=True):
		filters = {"status": "Sent"} if sent_only else None
		return mrinimitable.db.get_all("Email Queue", filters=filters, fields=["name"])

	def get_email_messages(self, sent_only=True):
		filters = {"status": "Sent"} if sent_only else None
		return mrinimitable.db.get_all("Email Queue", filters=filters, fields=["message"])
