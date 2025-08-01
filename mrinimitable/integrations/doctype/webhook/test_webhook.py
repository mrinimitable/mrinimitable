# Copyright (c) 2017, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import json
from contextlib import contextmanager

import responses
from responses.matchers import json_params_matcher

import mrinimitable
from mrinimitable.integrations.doctype.webhook import flush_webhook_execution_queue
from mrinimitable.integrations.doctype.webhook.webhook import (
	enqueue_webhook,
	get_webhook_data,
	get_webhook_headers,
)
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.tests.classes.context_managers import timeout


@contextmanager
def get_test_webhook(config):
	wh = mrinimitable.get_doc(config)
	if not wh.name:
		wh.name = mrinimitable.generate_hash()
	wh.insert()
	wh.reload()
	try:
		yield wh
	finally:
		wh.delete()


class TestWebhook(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		# delete any existing webhooks
		mrinimitable.db.delete("Webhook")
		# Delete existing logs if any
		mrinimitable.db.delete("Webhook Request Log")
		super().setUpClass()
		# create test webhooks
		cls.create_sample_webhooks()

	@classmethod
	def create_sample_webhooks(cls):
		samples_webhooks_data = [
			{
				"name": mrinimitable.generate_hash(),
				"webhook_doctype": "User",
				"webhook_docevent": "after_insert",
				"request_url": "https://httpbin.org/post",
				"condition": "doc.email",
				"enabled": True,
			},
			{
				"name": mrinimitable.generate_hash(),
				"webhook_doctype": "User",
				"webhook_docevent": "after_insert",
				"request_url": "https://httpbin.org/post",
				"condition": "doc.first_name",
				"enabled": False,
			},
		]

		cls.sample_webhooks = []
		for wh_fields in samples_webhooks_data:
			wh = mrinimitable.new_doc("Webhook")
			wh.update(wh_fields)
			wh.insert()
			cls.sample_webhooks.append(wh)

	@classmethod
	def tearDownClass(cls):
		# delete any existing webhooks
		mrinimitable.db.rollback()
		mrinimitable.db.delete("Webhook")
		mrinimitable.db.commit()

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def setUp(self):
		# retrieve or create a User webhook for `after_insert`
		self.responses = responses.RequestsMock()
		self.responses.start()

		self.responses.add(
			responses.POST,
			"https://httpbin.org/post",
			status=200,
			json={},
		)

		webhook_fields = {
			"webhook_doctype": "User",
			"webhook_docevent": "after_insert",
			"request_url": "https://httpbin.org/post",
		}

		if mrinimitable.db.exists("Webhook", webhook_fields):
			self.webhook = mrinimitable.get_doc("Webhook", webhook_fields)
		else:
			self.webhook = mrinimitable.new_doc("Webhook")
			self.webhook.update(webhook_fields)

		# create a User document
		self.user = mrinimitable.new_doc("User")
		self.user.first_name = mrinimitable.mock("name")
		self.user.email = mrinimitable.mock("email")
		self.user.save()

		# Create another test user specific to this test
		self.test_user = mrinimitable.new_doc("User")
		self.test_user.email = "user1@integration.webhooks.test.com"
		self.test_user.first_name = "user1"
		self.test_user.send_welcome_email = False

	def tearDown(self) -> None:
		self.user.delete()
		self.test_user.delete()

		self.responses.stop()
		self.responses.reset()
		super().tearDown()

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_trigger_with_enabled_webhooks(self):
		"""Test webhook trigger for enabled webhooks"""

		mrinimitable.client_cache.delete_value("webhooks")

		# Insert the user to db
		self.test_user.insert()

		webhooks = mrinimitable.client_cache.get_value("webhooks")
		self.assertTrue("User" in webhooks)
		self.assertEqual(len(webhooks.get("User")), 1)

		# only 1 hook (enabled) must be queued
		self.assertEqual(len(mrinimitable.local._webhook_queue), 1)
		execution = mrinimitable.local._webhook_queue[0]
		self.assertEqual(execution.webhook.name, self.sample_webhooks[0].name)
		self.assertEqual(execution.doc.name, self.test_user.name)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_doc_events(self):
		"Test creating a submit-related webhook for a non-submittable DocType"

		self.webhook.webhook_docevent = "on_submit"
		self.assertRaises(mrinimitable.ValidationError, self.webhook.save)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_request_url(self):
		"Test validation for the webhook request URL"

		self.webhook.request_url = "httpbin.org?post"
		self.assertRaises(mrinimitable.ValidationError, self.webhook.save)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_headers(self):
		"Test validation for request headers"

		# test incomplete headers
		self.webhook.set("webhook_headers", [{"key": "Content-Type"}])
		self.webhook.save()
		headers = get_webhook_headers(doc=None, webhook=self.webhook)
		self.assertEqual(headers, {})

		# test complete headers
		self.webhook.set("webhook_headers", [{"key": "Content-Type", "value": "application/json"}])
		self.webhook.save()
		headers = get_webhook_headers(doc=None, webhook=self.webhook)
		self.assertEqual(headers, {"Content-Type": "application/json"})

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_request_body_form(self):
		"Test validation of Form URL-Encoded request body"

		self.webhook.request_structure = "Form URL-Encoded"
		self.webhook.set("webhook_data", [{"fieldname": "name", "key": "name"}])
		self.webhook.webhook_json = """{
			"name": "{{ doc.name }}"
		}"""
		self.webhook.save()
		self.assertEqual(self.webhook.webhook_json, None)

		data = get_webhook_data(doc=self.user, webhook=self.webhook)
		self.assertEqual(data, {"name": self.user.name})

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_request_body_json(self):
		"Test validation of JSON request body"

		self.webhook.request_structure = "JSON"
		self.webhook.set("webhook_data", [{"fieldname": "name", "key": "name"}])
		self.webhook.webhook_json = """{
			"name": "{{ doc.name }}"
		}"""
		self.webhook.save()
		self.assertEqual(self.webhook.webhook_data, [])

		data = get_webhook_data(doc=self.user, webhook=self.webhook)
		self.assertEqual(data, {"name": self.user.name})

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_req_log_creation(self):
		self.responses.add(
			responses.POST,
			"https://httpbin.org/post",
			status=200,
			json={},
		)

		if not mrinimitable.db.get_value("User", "user2@integration.webhooks.test.com"):
			user = mrinimitable.get_doc(
				{"doctype": "User", "email": "user2@integration.webhooks.test.com", "first_name": "user2"}
			).insert()
		else:
			user = mrinimitable.get_doc("User", "user2@integration.webhooks.test.com")

		webhook = mrinimitable.get_doc("Webhook", {"webhook_doctype": "User"})
		enqueue_webhook(user, webhook)

		self.assertTrue(mrinimitable.get_all("Webhook Request Log", pluck="name"))

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_with_array_body(self):
		"""Check if array request body are supported."""
		wh_config = {
			"doctype": "Webhook",
			"webhook_doctype": "Note",
			"webhook_docevent": "on_change",
			"enabled": 1,
			"request_url": "https://httpbin.org/post",
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": '[\r\n{% for n in range(3) %}\r\n    {\r\n        "title": "{{ doc.title }}"    }\r\n    {%- if not loop.last -%}\r\n        , \r\n    {%endif%}\r\n{%endfor%}\r\n]',
			"meets_condition": "Yes",
			"webhook_headers": [
				{
					"key": "Content-Type",
					"value": "application/json",
				}
			],
		}

		doc = mrinimitable.new_doc("Note")
		doc.title = "Test Webhook Note"
		final_title = mrinimitable.generate_hash()

		expected_req = [{"title": final_title} for _ in range(3)]
		self.responses.add(
			responses.POST,
			"https://httpbin.org/post",
			status=200,
			json=expected_req,
			match=[json_params_matcher(expected_req)],
		)

		with get_test_webhook(wh_config):
			# It should only execute once in a transaction
			doc.insert()
			doc.reload()
			doc.save()
			doc = mrinimitable.get_doc(doc.doctype, doc.name)
			doc.title = final_title
			doc.save()
			flush_webhook_execution_queue()
			log = mrinimitable.get_last_doc("Webhook Request Log")
			self.assertEqual(len(json.loads(log.response)), 3)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_with_dynamic_url_enabled(self):
		wh_config = {
			"doctype": "Webhook",
			"webhook_doctype": "Note",
			"webhook_docevent": "after_insert",
			"enabled": 1,
			"request_url": "https://httpbin.org/anything/{{ doc.doctype }}",
			"is_dynamic_url": 1,
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": "{}",
			"meets_condition": "Yes",
			"webhook_headers": [
				{
					"key": "Content-Type",
					"value": "application/json",
				}
			],
		}

		self.responses.add(
			responses.POST,
			"https://httpbin.org/anything/Note",
			status=200,
		)

		with get_test_webhook(wh_config) as wh:
			doc = mrinimitable.new_doc("Note")
			doc.title = "Test Webhook Note"
			enqueue_webhook(doc, wh)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_with_dynamic_url_disabled(self):
		wh_config = {
			"doctype": "Webhook",
			"webhook_doctype": "Note",
			"webhook_docevent": "after_insert",
			"enabled": 1,
			"request_url": "https://httpbin.org/anything/{{doc.doctype}}",
			"is_dynamic_url": 0,
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": "{}",
			"meets_condition": "Yes",
			"webhook_headers": [
				{
					"key": "Content-Type",
					"value": "application/json",
				}
			],
		}

		self.responses.add(
			responses.POST,
			"https://httpbin.org/anything/{{doc.doctype}}",
			status=200,
		)

		with get_test_webhook(wh_config) as wh:
			doc = mrinimitable.new_doc("Note")
			doc.title = "Test Webhook Note"
			enqueue_webhook(doc, wh)
