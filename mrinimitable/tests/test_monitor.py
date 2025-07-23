# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable
import mrinimitable.monitor
from mrinimitable.monitor import MONITOR_REDIS_KEY, get_trace_id
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.utils import set_request
from mrinimitable.utils.response import build_response


class TestMonitor(IntegrationTestCase):
	def setUp(self):
		mrinimitable.conf.monitor = 1
		mrinimitable.cache.delete_value(MONITOR_REDIS_KEY)

	def tearDown(self):
		mrinimitable.conf.monitor = 0
		mrinimitable.cache.delete_value(MONITOR_REDIS_KEY)

	def test_enable_monitor(self):
		set_request(method="GET", path="/api/method/mrinimitable.ping")
		response = build_response("json")

		mrinimitable.monitor.start()
		mrinimitable.monitor.stop(response)

		logs = mrinimitable.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

		log = mrinimitable.parse_json(logs[0].decode())
		self.assertTrue(log.duration)
		self.assertTrue(log.site)
		self.assertTrue(log.timestamp)
		self.assertTrue(log.uuid)
		self.assertTrue(log.request)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

	def test_no_response(self):
		set_request(method="GET", path="/api/method/mrinimitable.ping")

		mrinimitable.monitor.start()
		mrinimitable.monitor.stop(response=None)

		logs = mrinimitable.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

		log = mrinimitable.parse_json(logs[0].decode())
		self.assertEqual(log.request["status_code"], 500)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

	def test_job(self):
		mrinimitable.utils.background_jobs.execute_job(
			mrinimitable.local.site, "mrinimitable.ping", None, None, {}, is_async=False
		)

		logs = mrinimitable.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)
		log = mrinimitable.parse_json(logs[0].decode())
		self.assertEqual(log.transaction_type, "job")
		self.assertTrue(log.job)
		self.assertEqual(log.job["method"], "mrinimitable.ping")
		self.assertEqual(log.job["scheduled"], False)
		self.assertEqual(log.job["wait"], 0)

	def test_flush(self):
		set_request(method="GET", path="/api/method/mrinimitable.ping")
		response = build_response("json")
		mrinimitable.monitor.start()
		mrinimitable.monitor.stop(response)

		open(mrinimitable.monitor.log_file(), "w").close()
		mrinimitable.monitor.flush()

		with open(mrinimitable.monitor.log_file()) as f:
			logs = f.readlines()

		self.assertEqual(len(logs), 1)
		log = mrinimitable.parse_json(logs[0])
		self.assertEqual(log.transaction_type, "request")

	def test_trace_ids(self):
		set_request(method="GET", path="/api/method/mrinimitable.ping")
		response = build_response("json")
		mrinimitable.monitor.start()
		mrinimitable.db.sql("select 1")
		self.assertIn(get_trace_id(), str(mrinimitable.db.last_query))
		mrinimitable.monitor.stop(response)
