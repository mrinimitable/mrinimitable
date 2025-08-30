# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import time

from werkzeug.wrappers import Response

import mrinimitable
import mrinimitable.rate_limiter
from mrinimitable.rate_limiter import RateLimiter
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.utils import cint


class TestRateLimiter(IntegrationTestCase):
	def test_apply_with_limit(self):
		mrinimitable.conf.rate_limit = {"window": 86400, "limit": 1}
		mrinimitable.rate_limiter.apply()

		self.assertTrue(hasattr(mrinimitable.local, "rate_limiter"))
		self.assertIsInstance(mrinimitable.local.rate_limiter, RateLimiter)

		mrinimitable.cache.delete(mrinimitable.local.rate_limiter.key)
		delattr(mrinimitable.local, "rate_limiter")

	def test_apply_without_limit(self):
		mrinimitable.conf.rate_limit = None
		mrinimitable.rate_limiter.apply()

		self.assertFalse(hasattr(mrinimitable.local, "rate_limiter"))

	def test_respond_over_limit(self):
		limiter = RateLimiter(1, 86400)
		time.sleep(1)
		limiter.update()

		mrinimitable.conf.rate_limit = {"window": 86400, "limit": 1}
		self.assertRaises(mrinimitable.TooManyRequestsError, mrinimitable.rate_limiter.apply)
		mrinimitable.rate_limiter.update()

		response = mrinimitable.rate_limiter.respond()

		self.assertIsInstance(response, Response)
		self.assertEqual(response.status_code, 429)

		headers = mrinimitable.local.rate_limiter.headers()
		self.assertIn("Retry-After", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertIn("X-RateLimit-Limit", headers)
		self.assertIn("X-RateLimit-Remaining", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"]) <= 86400)
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 1000000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 0)

		mrinimitable.cache.delete(limiter.key)
		mrinimitable.cache.delete(mrinimitable.local.rate_limiter.key)
		delattr(mrinimitable.local, "rate_limiter")

	def test_respond_under_limit(self):
		mrinimitable.conf.rate_limit = {"window": 86400, "limit": 0.01}
		mrinimitable.rate_limiter.apply()
		mrinimitable.rate_limiter.update()
		response = mrinimitable.rate_limiter.respond()
		self.assertEqual(response, None)

		mrinimitable.cache.delete(mrinimitable.local.rate_limiter.key)
		delattr(mrinimitable.local, "rate_limiter")

	def test_headers_under_limit(self):
		mrinimitable.conf.rate_limit = {"window": 86400, "limit": 1}
		mrinimitable.rate_limiter.apply()
		mrinimitable.rate_limiter.update()
		headers = mrinimitable.local.rate_limiter.headers()
		self.assertNotIn("Retry-After", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"] < 86400))
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 1000000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 1000000)

		mrinimitable.cache.delete(mrinimitable.local.rate_limiter.key)
		delattr(mrinimitable.local, "rate_limiter")

	def test_reject_over_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.01, 86400)
		self.assertRaises(mrinimitable.TooManyRequestsError, limiter.apply)

		mrinimitable.cache.delete(limiter.key)

	def test_do_not_reject_under_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.02, 86400)
		self.assertEqual(limiter.apply(), None)

		mrinimitable.cache.delete(limiter.key)

	def test_update_method(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		self.assertEqual(limiter.duration, cint(mrinimitable.cache.get(limiter.key)))

		mrinimitable.cache.delete(limiter.key)

	def test_window_expires(self):
		limiter = RateLimiter(1000, 1)
		self.assertTrue(mrinimitable.cache.exists(limiter.key, shared=True))
		limiter.update()
		self.assertTrue(mrinimitable.cache.exists(limiter.key, shared=True))
		time.sleep(1.1)
		self.assertFalse(mrinimitable.cache.exists(limiter.key, shared=True))
		mrinimitable.cache.delete(limiter.key)
