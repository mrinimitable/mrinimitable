# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from werkzeug.wrappers import Response

import mrinimitable
from mrinimitable.app import process_response
from mrinimitable.tests import IntegrationTestCase

HEADERS = (
	"Access-Control-Allow-Origin",
	"Access-Control-Allow-Credentials",
	"Access-Control-Allow-Methods",
	"Access-Control-Allow-Headers",
	"Vary",
)


class TestCORS(IntegrationTestCase):
	def make_request_and_test(self, origin="http://example.com", absent=False):
		self.origin = origin

		headers = {}
		if origin:
			headers = {
				"Origin": origin,
				"Access-Control-Request-Method": "POST",
				"Access-Control-Request-Headers": "X-Test-Header",
			}

		mrinimitable.utils.set_request(method="OPTIONS", headers=headers)

		self.response = Response()
		process_response(self.response)

		for header in HEADERS:
			if absent:
				self.assertNotIn(header, self.response.headers)
			else:
				if header == "Access-Control-Allow-Origin":
					self.assertEqual(self.response.headers.get(header), self.origin)
				else:
					self.assertIn(header, self.response.headers)

	def test_cors_disabled(self):
		mrinimitable.conf.allow_cors = None
		self.make_request_and_test("http://example.com", True)

	def test_request_without_origin(self):
		mrinimitable.conf.allow_cors = "http://example.com"
		self.make_request_and_test(None, True)

	def test_valid_origin(self):
		mrinimitable.conf.allow_cors = "http://example.com"
		self.make_request_and_test()

		mrinimitable.conf.allow_cors = "*"
		self.make_request_and_test()

		mrinimitable.conf.allow_cors = ["http://example.com", "https://example.com"]
		self.make_request_and_test()

	def test_invalid_origin(self):
		mrinimitable.conf.allow_cors = "http://example1.com"
		self.make_request_and_test(absent=True)

		mrinimitable.conf.allow_cors = ["http://example1.com", "https://example.com"]
		self.make_request_and_test(absent=True)
