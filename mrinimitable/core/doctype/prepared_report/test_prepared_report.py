# Copyright (c) 2018, Mrinimitable Technologies and Contributors
# License: MIT. See LICENSE
import json
import time
from contextlib import contextmanager

import mrinimitable
from mrinimitable.desk.query_report import generate_report_result, get_report_doc
from mrinimitable.query_builder.utils import db_type_is
from mrinimitable.tests import IntegrationTestCase, timeout
from mrinimitable.tests.test_query_builder import run_only_if


class TestPreparedReport(IntegrationTestCase):
	@classmethod
	def tearDownClass(cls):
		for r in mrinimitable.get_all("Prepared Report", pluck="name"):
			mrinimitable.delete_doc("Prepared Report", r, force=True, delete_permanently=True)

		mrinimitable.db.commit()

	@timeout(seconds=20)
	def wait_for_status(self, report, status):
		mrinimitable.db.commit()  # Flush changes first
		while True:
			mrinimitable.db.rollback()  # read new data
			report.reload()
			if report.status == status:
				break
			time.sleep(0.5)

	def create_prepared_report(self, report=None, commit=True):
		doc = mrinimitable.get_doc(
			{
				"doctype": "Prepared Report",
				"report_name": report or "Database Storage Usage By Tables",
			}
		).insert()

		if commit:
			mrinimitable.db.commit()

		return doc

	def test_queueing(self):
		doc = self.create_prepared_report()
		self.assertEqual("Queued", doc.status)
		self.assertTrue(doc.queued_at)

		self.wait_for_status(doc, "Completed")

		doc = mrinimitable.get_last_doc("Prepared Report")
		self.assertTrue(doc.job_id)
		self.assertTrue(doc.report_end_time)

	def test_prepared_data(self):
		doc = self.create_prepared_report()
		self.wait_for_status(doc, "Completed")

		prepared_data = json.loads(doc.get_prepared_data().decode("utf-8"))
		generated_data = generate_report_result(get_report_doc("Database Storage Usage By Tables"))
		self.assertEqual(len(prepared_data["columns"]), len(generated_data["columns"]))
		self.assertEqual(len(prepared_data["result"]), len(generated_data["result"]))
		self.assertEqual(len(prepared_data), len(generated_data))

	@run_only_if(db_type_is.MARIADB)
	def test_start_status_and_kill_jobs(self):
		with test_report(report_type="Query Report", query="select sleep(10)") as report:
			doc = self.create_prepared_report(report.name)
			self.wait_for_status(doc, "Started")
			job_id = doc.job_id

			doc.delete()
			time.sleep(1)
			job = mrinimitable.get_doc("RQ Job", job_id)
			self.assertEqual(job.status, "stopped")


@contextmanager
def test_report(**args):
	try:
		report = mrinimitable.new_doc("Report")
		report.update(args)
		if not report.report_name:
			report.report_name = mrinimitable.generate_hash()
		if not report.ref_doctype:
			report.ref_doctype = "ToDo"
		report.insert()
		mrinimitable.db.commit()
		yield report
	finally:
		report.delete()
