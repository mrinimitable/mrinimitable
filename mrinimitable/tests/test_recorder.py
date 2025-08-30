# Copyright (c) 2019, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import time

import sqlparse

import mrinimitable
import mrinimitable.recorder
from mrinimitable.recorder import normalize_query
from mrinimitable.tests import IntegrationTestCase, timeout
from mrinimitable.utils import set_request
from mrinimitable.utils.doctor import any_job_pending
from mrinimitable.website.serve import get_response_content


class TestRecorder(IntegrationTestCase):
	def setUp(self):
		self.wait_for_background_jobs()
		mrinimitable.recorder.stop()
		mrinimitable.recorder.delete()
		set_request()
		mrinimitable.recorder.start()
		mrinimitable.recorder.record()

	@timeout
	def wait_for_background_jobs(self):
		while any_job_pending(mrinimitable.local.site):
			time.sleep(1)

	def stop_recording(self):
		mrinimitable.recorder.dump()
		mrinimitable.recorder.stop()

	def test_start(self):
		self.stop_recording()
		requests = mrinimitable.recorder.get()
		self.assertEqual(len(requests), 1)

	def test_do_not_record(self):
		mrinimitable.recorder.do_not_record(mrinimitable.get_all)("DocType")
		self.stop_recording()
		requests = mrinimitable.recorder.get()
		self.assertEqual(len(requests), 0)

	def test_get(self):
		self.stop_recording()

		requests = mrinimitable.recorder.get()
		self.assertEqual(len(requests), 1)

		request = mrinimitable.recorder.get(requests[0]["uuid"])
		self.assertTrue(request)

	def test_delete(self):
		self.stop_recording()

		requests = mrinimitable.recorder.get()
		self.assertEqual(len(requests), 1)

		mrinimitable.recorder.delete()

		requests = mrinimitable.recorder.get()
		self.assertEqual(len(requests), 0)

	def test_record_without_sql_queries(self):
		self.stop_recording()

		requests = mrinimitable.recorder.get()
		request = mrinimitable.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"]), 0)

	def test_record_with_sql_queries(self):
		mrinimitable.get_all("DocType")
		self.stop_recording()

		requests = mrinimitable.recorder.get()
		request = mrinimitable.recorder.get(requests[0]["uuid"])

		self.assertNotEqual(len(request["calls"]), 0)

	def test_explain(self):
		mrinimitable.db.sql("SELECT * FROM tabDocType")
		mrinimitable.db.sql("COMMIT")
		mrinimitable.db.sql("select 1", run=0)
		self.stop_recording()

		requests = mrinimitable.recorder.get()
		request = mrinimitable.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"][0]["explain_result"]), 1)
		self.assertEqual(len(request["calls"][1]["explain_result"]), 0)

	def test_multiple_queries(self):
		queries = [
			{"mariadb": "SELECT * FROM tabDocType", "postgres": 'SELECT * FROM "tabDocType"'},
			{"mariadb": "SELECT COUNT(*) FROM tabDocType", "postgres": 'SELECT COUNT(*) FROM "tabDocType"'},
			{"mariadb": "COMMIT", "postgres": "COMMIT"},
		]

		sql_dialect = mrinimitable.db.db_type or "mariadb"
		for query in queries:
			mrinimitable.db.sql(query[sql_dialect])

		self.stop_recording()

		requests = mrinimitable.recorder.get()
		request = mrinimitable.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"]), len(queries))

		for query, call in zip(queries, request["calls"], strict=False):
			self.assertEqual(
				call["query"],
				sqlparse.format(
					query[sql_dialect].strip(), keyword_case="upper", reindent=True, strip_comments=True
				),
			)

	def test_duplicate_queries(self):
		queries = [
			("SELECT * FROM tabDocType", 2),
			("SELECT COUNT(*) FROM tabDocType", 1),
			("select * from tabDocType", 2),
			("COMMIT", 3),
			("COMMIT", 3),
			("COMMIT", 3),
		]
		for query in queries:
			mrinimitable.db.sql(query[0])

		self.stop_recording()

		requests = mrinimitable.recorder.get()
		request = mrinimitable.recorder.get(requests[0]["uuid"])

		for query, call in zip(queries, request["calls"], strict=False):
			self.assertEqual(call["exact_copies"], query[1])

	def test_error_page_rendering(self):
		content = get_response_content("error")
		self.assertIn("Error", content)


class TestRecorderDeco(IntegrationTestCase):
	def test_recorder_flag(self):
		mrinimitable.recorder.delete()

		@mrinimitable.recorder.record_queries
		def test():
			mrinimitable.get_all("User")

		test()
		self.assertTrue(mrinimitable.recorder.get())


class TestQueryNormalization(IntegrationTestCase):
	def test_query_normalization(self):
		test_cases = {
			"select * from user where name = 'x'": "select * from user where name = ?",
			"select * from user where a > 5": "select * from user where a > ?",
			"select * from `user` where a > 5": "select * from `user` where a > ?",
			"select `name` from `user`": "select `name` from `user`",
			"select `name` from `user` limit 10": "select `name` from `user` limit ?",
			"select `name` from `user` where name in ('a', 'b', 'c')": "select `name` from `user` where name in (?)",
		}

		for query, normalized in test_cases.items():
			self.assertEqual(normalize_query(query), normalized)
