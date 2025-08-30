# Copyright (c) 2022, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import contextlib
import functools
import json
import os
import threading
import time
from textwrap import dedent

import mrinimitable
import mrinimitable.model.sync
import mrinimitable.modules.patch_handler
import mrinimitable.translate
from mrinimitable.core.doctype.language.language import sync_languages
from mrinimitable.core.doctype.navbar_settings.navbar_settings import sync_standard_items
from mrinimitable.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
from mrinimitable.database.schema import add_column
from mrinimitable.deferred_insert import save_to_db as flush_deferred_inserts
from mrinimitable.desk.notifications import clear_notifications
from mrinimitable.modules.patch_handler import PatchType
from mrinimitable.modules.utils import sync_customizations
from mrinimitable.search.website_search import build_index_for_all_routes
from mrinimitable.utils.connections import check_connection
from mrinimitable.utils.dashboard import sync_dashboards
from mrinimitable.utils.data import cint
from mrinimitable.utils.fixtures import sync_fixtures
from mrinimitable.website.utils import clear_website_cache

SHASHI_START_MESSAGE = dedent(
	"""
	Cannot run shashi migrate without the services running.
	If you are running shashi in development mode, make sure that shashi is running:

	$ shashi start

	Otherwise, check the server logs and ensure that all the required services are running.
	"""
)


def atomic(method):
	@functools.wraps(method)
	def wrapper(*args, **kwargs):
		try:
			ret = method(*args, **kwargs)
			mrinimitable.db.commit()
			return ret
		except Exception as e:
			# database itself can be gone while attempting rollback.
			# We should preserve original exception in this case.
			with contextlib.suppress(Exception):
				mrinimitable.db.rollback()
			raise e

	return wrapper


class SiteMigration:
	"""Migrate all apps to the current version, will:
	- run before migrate hooks
	- run patches
	- sync doctypes (schema)
	- sync dashboards
	- sync jobs
	- sync fixtures
	- sync customizations
	- sync languages
	- sync web pages (from /www)
	- run after migrate hooks
	"""

	def __init__(
		self, skip_failing: bool = False, skip_search_index: bool = False, skip_fixtures: bool = False
	) -> None:
		self.skip_failing = skip_failing
		self.skip_search_index = skip_search_index
		self.skip_fixtures = skip_fixtures

	def setUp(self):
		"""Complete setup required for site migration"""
		mrinimitable.flags.touched_tables = set()
		self.touched_tables_file = mrinimitable.get_site_path("touched_tables.json")
		mrinimitable.clear_cache()

		if os.path.exists(self.touched_tables_file):
			os.remove(self.touched_tables_file)

		self.lower_lock_timeout()
		with contextlib.suppress(Exception):
			self.kill_idle_connections()
		mrinimitable.flags.in_migrate = True

	def tearDown(self):
		"""Run operations that should be run post schema updation processes
		This should be executed irrespective of outcome
		"""
		self.db_monitor.stop()
		mrinimitable.translate.clear_cache()
		clear_website_cache()
		clear_notifications()

		with open(self.touched_tables_file, "w") as f:
			json.dump(list(mrinimitable.flags.touched_tables), f, sort_keys=True, indent=4)

		if not self.skip_search_index:
			print(f"Queued rebuilding of search index for {mrinimitable.local.site}")
			mrinimitable.enqueue(build_index_for_all_routes, queue="long")

		mrinimitable.publish_realtime("version-update")
		mrinimitable.flags.touched_tables.clear()
		mrinimitable.flags.in_migrate = False

	@atomic
	def pre_schema_updates(self):
		"""Executes `before_migrate` hooks"""
		for app in mrinimitable.get_installed_apps():
			for fn in mrinimitable.get_hooks("before_migrate", app_name=app):
				mrinimitable.get_attr(fn)()

	@atomic
	def run_schema_updates(self):
		"""Run patches as defined in patches.txt, sync schema changes as defined in the {doctype}.json files"""
		mrinimitable.modules.patch_handler.run_all(
			skip_failing=self.skip_failing, patch_type=PatchType.pre_model_sync
		)
		mrinimitable.model.sync.sync_all()
		mrinimitable.modules.patch_handler.run_all(
			skip_failing=self.skip_failing, patch_type=PatchType.post_model_sync
		)

	@atomic
	def post_schema_updates(self):
		"""Execute pending migration tasks post patches execution & schema sync
		This includes:
		* Sync `Scheduled Job Type` and scheduler events defined in hooks
		* Sync fixtures & custom scripts
		* Sync in-Desk Module Dashboards
		* Sync customizations: Custom Fields, Property Setters, Custom Permissions
		* Sync Mrinimitable's internal language master
		* Flush deferred inserts made during maintenance mode.
		* Sync Portal Menu Items
		* Sync Installed Applications Version History
		* Execute `after_migrate` hooks
		"""
		print("Syncing jobs...")
		sync_jobs()
		if not self.skip_fixtures:
			print("Syncing fixtures...")
			sync_fixtures()
		else:
			print("Skipping fixtures...")
		sync_standard_items()

		print("Syncing dashboards...")
		sync_dashboards()

		print("Syncing customizations...")
		sync_customizations()

		print("Syncing languages...")
		sync_languages()

		print("Flushing deferred inserts...")
		flush_deferred_inserts()

		print("Removing orphan doctypes...")
		mrinimitable.model.sync.remove_orphan_doctypes()

		print("Syncing portal menu...")
		mrinimitable.get_single("Portal Settings").sync_menu()

		print("Updating installed applications...")
		mrinimitable.get_single("Installed Applications").update_versions()

		print("Executing `after_migrate` hooks...")
		for app in mrinimitable.get_installed_apps():
			for fn in mrinimitable.get_hooks("after_migrate", app_name=app):
				mrinimitable.get_attr(fn)()

	def required_services_running(self) -> bool:
		"""Return True if all required services are running. Return False and print
		instructions to stdout when required services are not available.
		"""
		service_status = check_connection(redis_services=["redis_cache"])
		are_services_running = all(service_status.values())

		if not are_services_running:
			for service in service_status:
				if not service_status.get(service, True):
					print(f"Service {service} is not running.")
			print(SHASHI_START_MESSAGE)

		return are_services_running

	def lower_lock_timeout(self):
		"""Lower timeout for table metadata locks, default is 1 day, reduce it to 5 minutes.

		This is required to avoid indefinitely waiting for metadata lock.
		"""
		if mrinimitable.db.db_type != "mariadb":
			return
		mrinimitable.db.sql("set session lock_wait_timeout = %s", 5 * 60)

	def kill_idle_connections(self, idle_limit=30):
		"""Assuming migrate has highest priority, kill everything else.

		If someone has connected to mariadb using DB console or ipython console and then acquired
		certain locks we won't be able to migrate."""
		if mrinimitable.db.db_type != "mariadb":
			return

		processes = mrinimitable.db.sql("show full processlist", as_dict=1)
		connection_id = mrinimitable.db.sql("select connection_id()")[0][0]
		for process in processes:
			sleeping = process.get("Command") == "Sleep"
			user = str(process.get("User")).lower()
			sleeping_since = cint(process.get("Time")) or 0
			pid = process.get("Id")

			if (
				pid
				and pid != connection_id
				and process.db == mrinimitable.conf.db_name
				and sleeping
				and sleeping_since > idle_limit
				and user != "system user"
			):
				try:
					mrinimitable.db.sql(f"kill {pid}")
					print(f"Killed inactive database connection with PID {pid}")
				except Exception as e:
					# We might not have permission to do this.
					print(f"Failed to kill inactive database connection with PID {pid}: {e}")

	def run(self, site: str):
		"""Run Migrate operation on site specified. This method initializes
		and destroys connections to the site database.
		"""
		from mrinimitable.utils.synchronization import filelock

		if site:
			mrinimitable.init(site)
			mrinimitable.connect()

		self.db_monitor = DBQueryProgressMonitor()

		if not self.required_services_running():
			raise SystemExit(1)

		with filelock("shashi_migrate", timeout=1):
			self.setUp()
			try:
				self.pre_schema_updates()
				self.run_schema_updates()
				self.post_schema_updates()
			finally:
				self.tearDown()
				mrinimitable.destroy()


class DBQueryProgressMonitor(threading.Thread):
	POLL_DURATION = 10

	def __init__(self) -> None:
		super().__init__()
		self.site = mrinimitable.local.site
		self.daemon = True
		self._running = threading.Event()
		if mrinimitable.db.db_type == "mariadb":
			self.conn_id = mrinimitable.db.sql("select connection_id()")[0][0]
			self.start()

	def run(self):
		if self._running.is_set():
			return
		self._running.set()

		mrinimitable.init(self.site)
		mrinimitable.connect()

		while self._running.is_set():
			time.sleep(self.POLL_DURATION)
			queries = mrinimitable.db.sql(
				"SELECT * FROM information_schema.PROCESSLIST WHERE ID = %s",
				self.conn_id,
				as_dict=True,
			)

			if not queries:
				continue

			query = mrinimitable._dict(queries[0])
			time_taken = query.TIME
			if not time_taken or time_taken < 5:
				continue

			msg = []
			command = query.COMMAND or ""
			msg.append(f"Command: {command}")
			msg.append(f"Time: {time_taken}s")
			msg.append(f"State: {query.STATE or 'N/A'}")
			if query.PROGRESS:
				msg.append(f"Progress: {query.PROGRESS}%")

			if command and command == "Query":
				sql_query = query.INFO or ""
				sql_query = sql_query.replace("\r", "").replace("\n", " ").replace("\t", " ")
				if len(sql_query) > 100:
					sql_query = sql_query[:40] + " ... " + sql_query[-20:]
				msg.append(f"Query: {sql_query}")

			msg = "\r" + " | ".join(msg)
			if self._running.is_set():
				print(msg, end="", flush=True)

		mrinimitable.destroy()

	def stop(self):
		print("")  # Clear current line
		self._running.clear()
