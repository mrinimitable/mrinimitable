# Copyright (c) 2022, Mrinimitable Technologies and Contributors
# See license.txt

import mrinimitable
from mrinimitable.core.doctype.rq_worker.rq_worker import RQWorker
from mrinimitable.tests import IntegrationTestCase


class TestRQWorker(IntegrationTestCase):
	def test_get_worker_list(self):
		workers = RQWorker.get_list()
		self.assertGreaterEqual(len(workers), 1)
		self.assertTrue(any("short" in w.queue_type for w in workers))

	def test_worker_serialization(self):
		workers = RQWorker.get_list()
		mrinimitable.get_doc("RQ Worker", workers[0].name)
