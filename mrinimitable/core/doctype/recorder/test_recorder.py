# Copyright (c) 2023, Mrinimitable Technologies and Contributors
# See license.txt

import re

import mrinimitable
import mrinimitable.recorder
from mrinimitable.core.doctype.recorder.recorder import _optimize_query, serialize_request
from mrinimitable.query_builder.utils import db_type_is
from mrinimitable.recorder import get as get_recorder_data
from mrinimitable.tests import IntegrationTestCase
from mrinimitable.tests.test_query_builder import run_only_if
from mrinimitable.utils import set_request


class TestRecorder(IntegrationTestCase):
	def setUp(self):
		self.start_recoder()

	def tearDown(self) -> None:
		mrinimitable.recorder.stop()

	def start_recoder(self):
		mrinimitable.recorder.stop()
		mrinimitable.recorder.delete()
		set_request(path="/api/method/ping")
		mrinimitable.recorder.start()
		mrinimitable.recorder.record()

	def stop_recorder(self):
		mrinimitable.recorder.dump()

	def test_recorder_list(self):
		mrinimitable.get_all("User")  # trigger one query
		self.stop_recorder()
		requests = mrinimitable.get_all("Recorder")
		self.assertGreaterEqual(len(requests), 1)
		request = mrinimitable.get_doc("Recorder", requests[0].name)
		self.assertGreaterEqual(len(request.sql_queries), 1)
		queries = [sql_query.query for sql_query in request.sql_queries]
		match_flag = 0
		for query in queries:
			if bool(re.match("^[select.*from `tabUser`]", query, flags=re.IGNORECASE)):
				match_flag = 1
				break
		self.assertEqual(match_flag, 1)

	def test_recorder_list_filters(self):
		user = mrinimitable.qb.DocType("User")
		mrinimitable.qb.from_(user).select("name").run()
		self.stop_recorder()

		set_request(path="/api/method/abc")
		mrinimitable.recorder.start()
		mrinimitable.recorder.record()
		mrinimitable.get_all("User")
		self.stop_recorder()

		requests = mrinimitable.get_list(
			"Recorder", filters={"path": ("like", "/api/method/ping"), "number_of_queries": 1}
		)
		self.assertGreaterEqual(len(requests), 1)
		requests = mrinimitable.get_list("Recorder", filters={"path": ("like", "/api/method/test")})
		self.assertEqual(len(requests), 0)

		requests = mrinimitable.get_list("Recorder", filters={"method": "GET"})
		self.assertGreaterEqual(len(requests), 1)
		requests = mrinimitable.get_list("Recorder", filters={"method": "POST"})
		self.assertEqual(len(requests), 0)

		requests = mrinimitable.get_list("Recorder", order_by="path desc")
		self.assertEqual(requests[0].path, "/api/method/ping")

	def test_recorder_serialization(self):
		mrinimitable.get_all("User")  # trigger one query
		self.stop_recorder()
		requests = mrinimitable.get_all("Recorder")
		request_doc = get_recorder_data(requests[0].name)
		self.assertIsInstance(serialize_request(request_doc), dict)


class TestQueryOptimization(IntegrationTestCase):
	@run_only_if(db_type_is.MARIADB)
	def test_query_optimizer(self):
		suggested_index = _optimize_query(
			"""select name from
			`tabUser` u
			join `tabHas Role` r
			on r.parent = u.name
			where email='xyz'
			and creation > '2023'
			and bio like '%xyz%'
			"""
		)
		self.assertEqual(suggested_index.table, "tabUser")
		self.assertEqual(suggested_index.column, "email")
