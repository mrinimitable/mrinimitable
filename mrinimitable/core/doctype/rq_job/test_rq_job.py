# Copyright (c) 2022, Mrinimitable Technologies and Contributors

# See license.txt

import time

from rq import exceptions as rq_exc
from rq.job import Job

import mrinimitable
from mrinimitable.core.doctype.rq_job.rq_job import RQJob, remove_failed_jobs, stop_job
from mrinimitable.installer import update_site_config
from mrinimitable.tests import IntegrationTestCase, timeout
from mrinimitable.utils import cstr, execute_in_shell
from mrinimitable.utils.background_jobs import get_job_status, is_job_enqueued


@timeout(seconds=60)
def wait_for_completion(job: Job):
	while True:
		if not (job.is_queued or job.is_started):
			break
		time.sleep(0.2)


class TestRQJob(IntegrationTestCase):
	BG_JOB = "mrinimitable.core.doctype.rq_job.test_rq_job.test_func"

	def setUp(self) -> None:
		# Cleanup all pending jobs
		for job in mrinimitable.get_all("RQ Job", {"status": "queued"}):
			mrinimitable.get_doc("RQ Job", job.name).cancel()
		return super().setUp()

	def check_status(self, job: Job, status, wait=True):
		if wait:
			wait_for_completion(job)
		self.assertEqual(mrinimitable.get_doc("RQ Job", job.id).status, status)

	def test_serialization(self):
		job = mrinimitable.enqueue(method=self.BG_JOB, queue="short")
		rq_job = mrinimitable.get_doc("RQ Job", job.id)

		self.assertEqual(job, rq_job.job)
		self.assertDocumentEqual(
			{
				"name": job.id,
				"queue": "short",
				"job_name": self.BG_JOB,
				"exc_info": None,
			},
			rq_job,
		)
		self.check_status(job, "finished")

	def test_configurable_ttl(self):
		mrinimitable.conf.rq_job_failure_ttl = 600
		job = mrinimitable.enqueue(method=self.BG_JOB, queue="short")

		self.assertEqual(job.failure_ttl, 600)

	def test_func_obj_serialization(self):
		job = mrinimitable.enqueue(method=test_func, queue="short")
		rq_job = mrinimitable.get_doc("RQ Job", job.id)
		self.assertEqual(rq_job.job_name, "mrinimitable.core.doctype.rq_job.test_rq_job.test_func")

	@timeout
	def test_get_list_filtering(self):
		# Check failed job clearning and filtering
		remove_failed_jobs()
		jobs = mrinimitable.get_all("RQ Job", {"status": "failed"})
		self.assertEqual(jobs, [])

		# Pass a job
		job = mrinimitable.enqueue(method=self.BG_JOB, queue="short")
		self.check_status(job, "finished")

		# Fail a job
		job = mrinimitable.enqueue(method=self.BG_JOB, queue="short", fail=True)
		self.check_status(job, "failed")
		jobs = mrinimitable.get_all("RQ Job", {"status": "failed"})
		self.assertEqual(len(jobs), 1)
		self.assertTrue(jobs[0].exc_info)

		# Assert that non-failed job still exists
		non_failed_jobs = mrinimitable.get_all("RQ Job", {"status": ("!=", "failed")})
		self.assertGreaterEqual(len(non_failed_jobs), 1)

		# Create a slow job and check if it's stuck in "Started"
		job = mrinimitable.enqueue(method=self.BG_JOB, queue="short", sleep=10)
		time.sleep(3)
		self.check_status(job, "started", wait=False)
		stop_job(job_id=job.id)
		self.check_status(job, "stopped")

	def test_delete_doc(self):
		job = mrinimitable.enqueue(method=self.BG_JOB, queue="short")
		mrinimitable.get_doc("RQ Job", job.id).delete()

		with self.assertRaises(rq_exc.NoSuchJobError):
			job.refresh()

	@timeout
	def test_multi_queue_burst_consumption(self):
		for _ in range(3):
			for q in ["default", "short"]:
				mrinimitable.enqueue(self.BG_JOB, sleep=1, queue=q)

		_, stderr = execute_in_shell("shashi worker --queue short,default --burst", check_exit_code=True)
		self.assertIn("quitting", cstr(stderr))

	@timeout
	def test_multi_queue_burst_consumption_worker_pool(self):
		for _ in range(3):
			for q in ["default", "short"]:
				mrinimitable.enqueue(self.BG_JOB, sleep=1, queue=q)

		_, stderr = execute_in_shell(
			"shashi worker-pool --queue short,default --burst --num-workers=4", check_exit_code=True
		)
		self.assertIn("quitting", cstr(stderr))

	def test_job_id_manual_dedup(self):
		job_id = "test_dedup"
		job = mrinimitable.enqueue(self.BG_JOB, sleep=5, job_id=job_id)
		self.assertTrue(is_job_enqueued(job_id))
		self.check_status(job, "finished")
		self.assertFalse(is_job_enqueued(job_id))

	def test_auto_job_dedup(self):
		job_id = "test_dedup"
		job1 = mrinimitable.enqueue(self.BG_JOB, sleep=2, job_id=job_id, deduplicate=True)
		job2 = mrinimitable.enqueue(self.BG_JOB, sleep=5, job_id=job_id, deduplicate=True)
		self.assertIsNone(job2)
		self.check_status(job1, "finished")  # wait

		# Failed jobs last longer, subsequent job should still pass with same ID.
		job3 = mrinimitable.enqueue(self.BG_JOB, fail=True, job_id=job_id, deduplicate=True)
		self.check_status(job3, "failed")
		job4 = mrinimitable.enqueue(self.BG_JOB, sleep=1, job_id=job_id, deduplicate=True)
		self.check_status(job4, "finished")

	@timeout
	def test_enqueue_after_commit(self):
		job_id = mrinimitable.generate_hash()

		mrinimitable.enqueue(self.BG_JOB, enqueue_after_commit=True, job_id=job_id)
		self.assertIsNone(get_job_status(job_id))

		mrinimitable.db.commit()
		self.assertIsNotNone(get_job_status(job_id))

		job_id = mrinimitable.generate_hash()
		mrinimitable.enqueue(self.BG_JOB, enqueue_after_commit=True, job_id=job_id)
		self.assertIsNone(get_job_status(job_id))

		mrinimitable.db.rollback()
		self.assertIsNone(get_job_status(job_id))

		mrinimitable.db.commit()
		self.assertIsNone(get_job_status(job_id))

	def test_memory_usage(self):
		if mrinimitable.db.db_type != "mariadb":
			return
		job = mrinimitable.enqueue("mrinimitable.utils.data._get_rss_memory_usage")
		self.check_status(job, "finished")

		rss = job.latest_result().return_value
		msg = """Memory usage of simple background job increased. Potential root cause can be a newly added python module import. Check and move them to approriate file/function to avoid loading the module by default."""

		# If this starts failing analyze memory usage using memray or some equivalent tool to find
		# offending imports/function calls.
		# Refer this PR: https://github.com/mrinimitable/mrinimitable/pull/21467
		LAST_MEASURED_USAGE = 46
		if mrinimitable.conf.use_mysqlclient:
			# TEMP: Add extra allowance for running two connectors, this should be rolled back before v16
			LAST_MEASURED_USAGE += 2
		self.assertLessEqual(rss, LAST_MEASURED_USAGE * 1.05, msg)

	def test_clear_failed_jobs(self):
		limit = 10
		update_site_config("rq_failed_jobs_limit", limit)

		jobs = [mrinimitable.enqueue(method=self.BG_JOB, queue="short", fail=True) for _ in range(limit * 2)]
		self.check_status(jobs[-1], "failed")
		self.assertLessEqual(RQJob.get_count(filters=[["RQ Job", "status", "=", "failed"]]), limit * 1.1)


def test_func(fail=False, sleep=0):
	if fail:
		42 / 0
	if sleep:
		time.sleep(sleep)

	return True
