# Copyright (c) 2017, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import time

import pyotp

import mrinimitable
from mrinimitable.auth import HTTPRequest, get_login_attempt_tracker, validate_ip_address
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.twofactor import (
	ExpiredLoginException,
	authenticate_for_2factor,
	confirm_otp_token,
	get_cached_user_pass,
	get_default,
	get_otpsecret_for_,
	get_verification_obj,
	should_run_2fa,
	two_factor_is_enabled_for_,
)
from mrinimitable.utils import cint, set_request


class TestTwoFactor(IntegrationTestCase):
	def setUp(self):
		self.http_requests = create_http_request()
		self.login_manager = mrinimitable.local.login_manager
		self.user = self.login_manager.user
		self.enterContext(self.change_settings("System Settings", {"allow_consecutive_login_attempts": 2}))

	def tearDown(self):
		mrinimitable.local.response["verification"] = None
		mrinimitable.local.response["tmp_id"] = None
		disable_2fa()
		mrinimitable.clear_cache(user=self.user)

	def test_should_run_2fa(self):
		"""Should return true if enabled."""
		toggle_2fa_all_role(state=True)
		self.assertTrue(should_run_2fa(self.user))
		toggle_2fa_all_role(state=False)
		self.assertFalse(should_run_2fa(self.user))

	def test_get_cached_user_pass(self):
		"""Cached data should not contain user and pass before 2fa."""
		user, pwd = get_cached_user_pass()
		self.assertTrue(all([not user, not pwd]))

	def test_authenticate_for_2factor(self):
		"""Verification obj and tmp_id should be set in mrinimitable.local."""
		authenticate_for_2factor(self.user)
		verification_obj = mrinimitable.local.response["verification"]
		tmp_id = mrinimitable.local.response["tmp_id"]
		self.assertTrue(verification_obj)
		self.assertTrue(tmp_id)
		for k in ["_usr", "_pwd", "_otp_secret"]:
			self.assertTrue(mrinimitable.cache.get(f"{tmp_id}{k}"), f"{k} not available")

	def test_two_factor_is_enabled(self):
		"""
		1. Should return true, if enabled and not bypass_2fa_for_retricted_ip_users
		2. Should return false, if not enabled
		3. Should return true, if enabled and not bypass_2fa_for_retricted_ip_users and ip in restrict_ip
		4. Should return true, if enabled and bypass_2fa_for_retricted_ip_users and not restrict_ip
		5. Should return false, if enabled and bypass_2fa_for_retricted_ip_users and ip in restrict_ip
		"""

		# Scenario 1
		enable_2fa()
		self.assertTrue(should_run_2fa(self.user))

		# Scenario 2
		disable_2fa()
		self.assertFalse(should_run_2fa(self.user))

		# Scenario 3
		enable_2fa()
		user = mrinimitable.get_doc("User", self.user)
		user.restrict_ip = mrinimitable.local.request_ip
		user.save()
		self.assertTrue(should_run_2fa(self.user))

		# Scenario 4
		user = mrinimitable.get_doc("User", self.user)
		user.restrict_ip = ""
		user.save()
		enable_2fa(1)
		self.assertTrue(should_run_2fa(self.user))

		# Scenario 5
		user = mrinimitable.get_doc("User", self.user)
		user.restrict_ip = mrinimitable.local.request_ip
		user.save()
		enable_2fa(1)
		self.assertFalse(should_run_2fa(self.user))

	def test_two_factor_is_enabled_for_user(self):
		"""Should return true if enabled for user."""
		toggle_2fa_all_role(state=True)
		self.assertTrue(two_factor_is_enabled_for_(self.user))
		self.assertFalse(two_factor_is_enabled_for_("Administrator"))
		toggle_2fa_all_role(state=False)
		self.assertFalse(two_factor_is_enabled_for_(self.user))

	def test_get_otpsecret_for_user(self):
		"""OTP secret should be set for user."""
		self.assertTrue(get_otpsecret_for_(self.user))
		self.assertTrue(get_default(self.user + "_otpsecret"))

	def test_confirm_otp_token(self):
		"""Ensure otp is confirmed"""
		mrinimitable.flags.otp_expiry = 2
		authenticate_for_2factor(self.user)
		tmp_id = mrinimitable.local.response["tmp_id"]
		otp = "wrongotp"
		with self.assertRaises(mrinimitable.AuthenticationError):
			confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id)

		# Freeze the time to avoid expiry during test
		with self.freeze_time(datetime.datetime.now()):
			otp = get_otp(self.user)
			self.assertTrue(confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id))

		mrinimitable.flags.otp_expiry = None
		print("Sleeping for 2 secs to confirm token expires..")
		time.sleep(2)
		with self.assertRaises(ExpiredLoginException):
			confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id)

	def test_get_verification_obj(self):
		"""Confirm verification object is returned."""
		otp_secret = get_otpsecret_for_(self.user)
		token = int(pyotp.TOTP(otp_secret).now())
		self.assertTrue(get_verification_obj(self.user, token, otp_secret))

	def test_render_string_template(self):
		"""String template renders as expected with variables."""
		args = {"issuer_name": "Mrinimitable Technologies"}
		_str = "Verification Code from {{issuer_name}}"
		_str = mrinimitable.render_template(_str, args)
		self.assertEqual(_str, "Verification Code from Mrinimitable Technologies")

	def test_bypass_restict_ip(self):
		"""
		1. Raise error if user not login from one of the restrict_ip, Bypass restrict ip check disabled by default
		2. Bypass restrict ip check enabled in System Settings
		3. Bypass restrict ip check enabled for User
		"""

		# 1
		user = mrinimitable.get_doc("User", self.user)
		user.restrict_ip = "192.168.255.254"  # Dummy IP
		user.bypass_restrict_ip_check_if_2fa_enabled = 0
		user.save()
		enable_2fa(bypass_restrict_ip_check=0)
		with self.assertRaises(mrinimitable.AuthenticationError):
			validate_ip_address(self.user)

		# 2
		enable_2fa(bypass_restrict_ip_check=1)
		self.assertIsNone(validate_ip_address(self.user))

		# 3
		user = mrinimitable.get_doc("User", self.user)
		user.bypass_restrict_ip_check_if_2fa_enabled = 1
		user.save()
		enable_2fa()
		self.assertIsNone(validate_ip_address(self.user))

	def test_otp_attempt_tracker(self):
		"""Check that OTP login attempts are tracked."""
		authenticate_for_2factor(self.user)
		tmp_id = mrinimitable.local.response["tmp_id"]
		otp = "wrongotp"
		with self.assertRaises(mrinimitable.AuthenticationError):
			confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id)

		with self.assertRaises(mrinimitable.AuthenticationError):
			confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id)

		# REMOVE ME: current logic allows allow_consecutive_login_attempts+1 attempts
		# before raising security exception, remove below line when that is fixed.
		with self.assertRaises(mrinimitable.AuthenticationError):
			confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id)

		with self.assertRaises(mrinimitable.SecurityException):
			confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id)

		# Remove tracking cache so that user can try loging in again
		tracker = get_login_attempt_tracker(self.user, raise_locked_exception=False)
		tracker.add_success_attempt()

		# Freeze the time to avoid expiry during test
		with self.freeze_time(datetime.datetime.now()):
			otp = get_otp(self.user)
			self.assertTrue(confirm_otp_token(self.login_manager, otp=otp, tmp_id=tmp_id))


def create_http_request():
	"""Get http request object."""
	set_request(method="POST", path="login")
	enable_2fa()
	mrinimitable.form_dict["usr"] = "test@example.com"
	mrinimitable.form_dict["pwd"] = "Eastern_43A1W"
	mrinimitable.local.form_dict["cmd"] = "login"
	return HTTPRequest()


def enable_2fa(bypass_two_factor_auth=0, bypass_restrict_ip_check=0):
	"""Enable Two factor in system settings."""
	system_settings = mrinimitable.get_doc("System Settings")
	system_settings.enable_two_factor_auth = 1
	system_settings.bypass_2fa_for_retricted_ip_users = cint(bypass_two_factor_auth)
	system_settings.bypass_restrict_ip_check_if_2fa_enabled = cint(bypass_restrict_ip_check)
	system_settings.two_factor_method = "OTP App"
	system_settings.flags.ignore_mandatory = True
	system_settings.save(ignore_permissions=True)
	mrinimitable.db.commit()


def disable_2fa():
	system_settings = mrinimitable.get_doc("System Settings")
	system_settings.enable_two_factor_auth = 0
	system_settings.flags.ignore_mandatory = True
	system_settings.save(ignore_permissions=True)
	mrinimitable.db.commit()


def toggle_2fa_all_role(state=None):
	"""Enable or disable 2fa for 'all' role on the system."""
	all_role = mrinimitable.get_doc("Role", "All")
	state = state if state is not None else False
	if not isinstance(state, bool):
		return

	all_role.two_factor_auth = cint(state)
	all_role.save(ignore_permissions=True)
	mrinimitable.db.commit()


def get_otp(user):
	otp_secret = get_otpsecret_for_(user)
	otp = pyotp.TOTP(otp_secret)
	return otp.now()
