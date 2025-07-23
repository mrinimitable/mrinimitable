# Copyright (c) 2015, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import time

import mrinimitable
from mrinimitable.auth import CookieManager, LoginManager
from mrinimitable.tests import IntegrationTestCase


class TestActivityLog(IntegrationTestCase):
	def setUp(self) -> None:
		mrinimitable.set_user("Administrator")

	def test_activity_log(self):
		# test user login log
		mrinimitable.local.form_dict = mrinimitable._dict(
			{
				"cmd": "login",
				"sid": "Guest",
				"pwd": self.ADMIN_PASSWORD or "admin",
				"usr": "Administrator",
			}
		)

		mrinimitable.local.request_ip = "127.0.0.1"
		mrinimitable.local.cookie_manager = CookieManager()
		mrinimitable.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertFalse(mrinimitable.form_dict.pwd)
		self.assertEqual(auth_log.status, "Success")

		# test user logout log
		mrinimitable.local.login_manager.logout()
		auth_log = self.get_auth_log(operation="Logout")
		self.assertEqual(auth_log.status, "Success")

		# test invalid login
		mrinimitable.form_dict.update({"pwd": "password"})
		self.assertRaises(mrinimitable.AuthenticationError, LoginManager)
		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, "Failed")

		mrinimitable.local.form_dict = mrinimitable._dict()

	def get_auth_log(self, operation="Login"):
		names = mrinimitable.get_all(
			"Activity Log",
			filters={
				"user": "Administrator",
				"operation": operation,
			},
			order_by="`creation` DESC",
		)

		name = names[0]
		return mrinimitable.get_doc("Activity Log", name)

	def test_brute_security(self):
		update_system_settings({"allow_consecutive_login_attempts": 3, "allow_login_after_fail": 5})

		mrinimitable.local.form_dict = mrinimitable._dict(
			{"cmd": "login", "sid": "Guest", "pwd": self.ADMIN_PASSWORD, "usr": "Administrator"}
		)

		mrinimitable.local.request_ip = "127.0.0.1"
		mrinimitable.local.cookie_manager = CookieManager()
		mrinimitable.local.login_manager = LoginManager()

		auth_log = self.get_auth_log()
		self.assertEqual(auth_log.status, "Success")

		# test user logout log
		mrinimitable.local.login_manager.logout()
		auth_log = self.get_auth_log(operation="Logout")
		self.assertEqual(auth_log.status, "Success")

		# test invalid login
		mrinimitable.form_dict.update({"pwd": "password"})
		self.assertRaises(mrinimitable.AuthenticationError, LoginManager)
		self.assertRaises(mrinimitable.AuthenticationError, LoginManager)
		self.assertRaises(mrinimitable.AuthenticationError, LoginManager)

		# REMOVE ME: current logic allows allow_consecutive_login_attempts+1 attempts
		# before raising security exception, remove below line when that is fixed.
		self.assertRaises(mrinimitable.AuthenticationError, LoginManager)
		self.assertRaises(mrinimitable.SecurityException, LoginManager)
		time.sleep(5)
		self.assertRaises(mrinimitable.AuthenticationError, LoginManager)

		mrinimitable.local.form_dict = mrinimitable._dict()


def update_system_settings(args):
	doc = mrinimitable.get_doc("System Settings")
	doc.update(args)
	doc.flags.ignore_mandatory = 1
	doc.save()
