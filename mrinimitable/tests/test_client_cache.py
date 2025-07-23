import time

import mrinimitable
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.utils.redis_wrapper import ClientCache

TEST_KEY = "42"


class TestClientCache(IntegrationTestCase):
	def setUp(self) -> None:
		mrinimitable.client_cache.delete_value(TEST_KEY)
		return super().setUp()

	def test_client_cache_is_used(self):
		mrinimitable.client_cache.set_value(TEST_KEY, 42)
		mrinimitable.client_cache.get_value(TEST_KEY)
		with self.assertRedisCallCounts(0):
			mrinimitable.client_cache.get_value(TEST_KEY)

	def test_client_cache_is_updated_instantly_noloop(self):
		val = mrinimitable.generate_hash()
		mrinimitable.client_cache.set_value(TEST_KEY, val)
		with self.assertRedisCallCounts(0):  # Locally set value should not be invalidated.
			self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY), val)

	def test_invalidation_from_another_client_works(self):
		mrinimitable.client_cache.reset_statistics()
		val = mrinimitable.generate_hash()
		mrinimitable.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY), val)

		# mrinimitable.cache is our "another client"
		val = mrinimitable.generate_hash()
		mrinimitable.cache.set_value(TEST_KEY, val)
		# This is almost instant, but obviously not as fast as running the next instruction in
		# current thread. So we wait.
		time.sleep(0.1)

		with self.assertRedisCallCounts(1, exact=True):
			self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY), val)

		self.assertEqual(mrinimitable.client_cache.statistics.hits, 1)
		self.assertEqual(mrinimitable.client_cache.statistics.misses, 1)
		self.assertEqual(mrinimitable.client_cache.statistics.hit_ratio, 0.5)

	def test_delete_invalidates(self):
		val = mrinimitable.generate_hash()
		mrinimitable.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY), val)

		val = mrinimitable.generate_hash()
		mrinimitable.cache.delete_value(TEST_KEY)
		# This is almost instant, but obviously not as fast as running the next instruction in
		# current thread. So we wait.
		time.sleep(0.1)

		with self.assertRedisCallCounts(1, exact=True):
			self.assertIsNone(mrinimitable.client_cache.get_value(TEST_KEY))

		# Flushall should have results
		mrinimitable.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY), val)
		mrinimitable.cache.flushall()
		time.sleep(0.1)
		with self.assertRedisCallCounts(1, exact=True):
			self.assertIsNone(mrinimitable.client_cache.get_value(TEST_KEY))

		# mrinimitable.clear_cache should have same results
		mrinimitable.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY), val)
		mrinimitable.clear_cache()
		time.sleep(0.1)
		with self.assertRedisCallCounts(1, exact=True):
			self.assertIsNone(mrinimitable.client_cache.get_value(TEST_KEY))

	def test_client_local_cache_ttl(self):
		c = ClientCache(ttl=1)
		c.set_value(TEST_KEY, 42)
		with self.assertRedisCallCounts(0):
			c.get_value(TEST_KEY)
		time.sleep(1)

		with self.assertRedisCallCounts(1, exact=True):
			c.get_value(TEST_KEY)

	def test_client_cache_maxsize(self):
		c = ClientCache(maxsize=2)
		c.set_value(TEST_KEY, 42)
		c.set_value(mrinimitable.generate_hash(), 42)
		c.set_value(mrinimitable.generate_hash(), 42)

		self.assertEqual(len(c.cache), 2)

	def test_shared_keyspace(self):
		val = mrinimitable.generate_hash()
		mrinimitable.client_cache.set_value(TEST_KEY, val)

		self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY), mrinimitable.cache.get_value(TEST_KEY))

	def test_shared_keys(self):
		val = mrinimitable.generate_hash()
		mrinimitable.client_cache.set_value(TEST_KEY, val, shared=True)
		with self.assertRedisCallCounts(0):
			self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY, shared=True), val)

	def test_generator(self):
		val = mrinimitable.generate_hash()
		with self.assertRedisCallCounts(3, exact=True):
			self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY, generator=lambda: val), val)

		with self.assertRedisCallCounts(0):
			self.assertEqual(mrinimitable.client_cache.get_value(TEST_KEY, generator=lambda: val), val)

	def test_get_doc(self):
		mrinimitable.client_cache.get_doc("User", "Guest")
		with self.assertRedisCallCounts(0):
			mrinimitable.client_cache.get_doc("User", "Guest")
