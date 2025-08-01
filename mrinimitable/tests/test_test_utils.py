from datetime import timedelta

import mrinimitable
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.utils.data import now_datetime


class TestTestUtils(IntegrationTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_document_assertions(self):
		currency = mrinimitable.new_doc("Currency")
		currency.currency_name = "STONKS"
		currency.smallest_currency_fraction_value = 0.420_001
		currency.save()

		self.assertDocumentEqual(currency.as_dict(), currency)

	def test_thread_locals(self):
		mrinimitable.flags.temp_flag_to_be_discarded = True

	def test_temp_setting_changes(self):
		current_setting = mrinimitable.get_system_settings("logout_on_password_reset")

		with IntegrationTestCase.change_settings(
			"System Settings", {"logout_on_password_reset": int(not current_setting)}
		):
			updated_settings = mrinimitable.get_single_value("System Settings", "logout_on_password_reset")
			self.assertNotEqual(current_setting, updated_settings)

		restored_settings = mrinimitable.get_single_value("System Settings", "logout_on_password_reset")
		self.assertEqual(current_setting, restored_settings)

	def test_time_freezing(self):
		now = now_datetime()

		tomorrow = now + timedelta(days=1)
		with self.freeze_time(tomorrow):
			self.assertEqual(now_datetime(), tomorrow)


def tearDownModule():
	"""assertions for ensuring tests didn't leave state behind"""
	assert "temp_flag_to_be_discarded" not in mrinimitable.flags
	assert not mrinimitable.db.exists("Currency", "STONKS")
