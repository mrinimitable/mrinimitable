# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Events:
	always
	daily
	monthly
	weekly
"""

import datetime
import os
import random
import time
from typing import NoReturn

from croniter import CroniterBadCronError
from filelock import FileLock, Timeout

import mrinimitable
from mrinimitable.utils import cint, get_shashi_path, get_datetime, get_sites, now_datetime
from mrinimitable.utils.background_jobs import set_niceness
from mrinimitable.utils.caching import redis_cache

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_SCHEDULER_TICK = 4 * 60


def cprint(*args, **kwargs):
	"""Prints only if called from STDOUT"""
	try:
		os.get_terminal_size()
		print(*args, **kwargs)
	except Exception:
		pass


def start_scheduler() -> NoReturn:
	"""Run enqueue_events_for_all_sites based on scheduler tick.
	Specify scheduler_tick_interval in seconds in common_site_config.json"""

	tick = get_scheduler_tick()
	set_niceness()

	lock_path = _get_scheduler_lock_file()

	try:
		lock = FileLock(lock_path)
		lock.acquire(blocking=False)
	except Timeout:
		mrinimitable.logger("scheduler").debug("Scheduler already running")
		return

	while True:
		time.sleep(sleep_duration(tick))
		enqueue_events_for_all_sites()


def _get_scheduler_lock_file() -> True:
	return os.path.abspath(os.path.join(get_shashi_path(), "config", "scheduler_process"))


def is_schduler_process_running() -> bool:
	"""Checks if any other process is holding the lock.

	Note: FLOCK is held by process until it exits, this function just checks if process is
	running or not. We can't determine if process is stuck somehwere.
	"""
	try:
		lock = FileLock(_get_scheduler_lock_file())
		lock.acquire(blocking=False)
		lock.release()
		return False
	except Timeout:
		return True


def sleep_duration(tick):
	if tick != DEFAULT_SCHEDULER_TICK:
		# Assuming user knows what they want.
		return tick

	# Sleep until next multiple of tick.
	# This makes scheduler aligned with real clock,
	# so event scheduled at 12:00 happen at 12:00 and not 12:00:35.
	minutes = tick // 60
	now = datetime.datetime.now(datetime.timezone.utc)
	left_minutes = minutes - now.minute % minutes
	next_execution = now.replace(second=0) + datetime.timedelta(minutes=left_minutes)

	return (next_execution - now).total_seconds()


def enqueue_events_for_all_sites() -> None:
	"""Loop through sites and enqueue events that are not already queued"""

	with mrinimitable.init_site():
		sites = get_sites()

	# Sites are sorted in alphabetical order, shuffle to randomize priorities
	random.shuffle(sites)

	for site in sites:
		try:
			enqueue_events_for_site(site=site)
		except Exception:
			mrinimitable.logger("scheduler").debug(f"Failed to enqueue events for site: {site}", exc_info=True)


def enqueue_events_for_site(site: str) -> None:
	def log_exc():
		mrinimitable.logger("scheduler").error(f"Exception in Enqueue Events for Site {site}", exc_info=True)

	try:
		mrinimitable.init(site)
		mrinimitable.connect()
		if is_scheduler_inactive():
			return

		enqueue_events()

		mrinimitable.logger("scheduler").debug(f"Queued events for site {site}")
	except Exception as e:
		if mrinimitable.db.is_access_denied(e):
			mrinimitable.logger("scheduler").debug(f"Access denied for site {site}")
		log_exc()

	finally:
		mrinimitable.destroy()


def enqueue_events() -> list[str] | None:
	if schedule_jobs_based_on_activity():
		enqueued_jobs = []
		all_jobs = mrinimitable.get_all("Scheduled Job Type", filters={"stopped": 0}, fields="*")
		random.shuffle(all_jobs)
		for job_type in all_jobs:
			job_type = mrinimitable.get_doc(doctype="Scheduled Job Type", **job_type)
			try:
				if job_type.enqueue():
					enqueued_jobs.append(job_type.method)
			except CroniterBadCronError:
				mrinimitable.logger("scheduler").error(
					f"Invalid Job on {mrinimitable.local.site} - {job_type.name}", exc_info=True
				)

		return enqueued_jobs


def is_scheduler_inactive(verbose=True) -> bool:
	if mrinimitable.local.conf.maintenance_mode:
		if verbose:
			cprint(f"{mrinimitable.local.site}: Maintenance mode is ON")
		return True

	if mrinimitable.local.conf.pause_scheduler:
		if verbose:
			cprint(f"{mrinimitable.local.site}: mrinimitable.conf.pause_scheduler is SET")
		return True

	if is_scheduler_disabled(verbose=verbose):
		return True

	return False


def is_scheduler_disabled(verbose=True) -> bool:
	if mrinimitable.conf.disable_scheduler:
		if verbose:
			cprint(f"{mrinimitable.local.site}: mrinimitable.conf.disable_scheduler is SET")
		return True

	scheduler_disabled = not mrinimitable.get_system_settings("enable_scheduler")
	if scheduler_disabled:
		if verbose:
			cprint(f"{mrinimitable.local.site}: SystemSettings.enable_scheduler is UNSET")
	return scheduler_disabled


def toggle_scheduler(enable):
	mrinimitable.db.set_single_value("System Settings", "enable_scheduler", int(enable))


def enable_scheduler():
	toggle_scheduler(True)


def disable_scheduler():
	toggle_scheduler(False)


@redis_cache(ttl=60 * 60)
def schedule_jobs_based_on_activity(check_time=None):
	"""Return True for active sites as defined by `Activity Log`.
	Also return True for inactive sites once every 24 hours based on `Scheduled Job Log`."""
	if is_dormant(check_time=check_time):
		# ensure last job is one day old
		last_job_timestamp = _get_last_creation_timestamp("Scheduled Job Log")
		if not last_job_timestamp:
			return True
		else:
			if ((check_time or now_datetime()) - last_job_timestamp).total_seconds() >= 86400:
				# one day is passed since jobs are run, so lets do this
				return True
			else:
				# schedulers run in the last 24 hours, do nothing
				return False
	else:
		# site active, lets run the jobs
		return True


@redis_cache(ttl=60 * 60)
def is_dormant(check_time=None):
	from mrinimitable.utils.mrinimitablecloud import on_mrinimitablecloud

	if mrinimitable.conf.developer_mode or not on_mrinimitablecloud():
		return False
	threshold = cint(mrinimitable.get_system_settings("dormant_days")) * 86400
	if not threshold:
		return False

	last_activity = mrinimitable.db.get_value(
		"User", filters={}, fieldname="last_active", order_by="last_active desc"
	)

	if not last_activity:
		return True
	if ((check_time or now_datetime()) - last_activity).total_seconds() >= threshold:
		return True
	return False


def _get_last_creation_timestamp(doctype):
	timestamp = mrinimitable.db.get_value(doctype, filters={}, fieldname="creation", order_by="creation desc")
	if timestamp:
		return get_datetime(timestamp)


@mrinimitable.whitelist()
def activate_scheduler():
	from mrinimitable.installer import update_site_config

	mrinimitable.only_for("Administrator")

	if mrinimitable.local.conf.maintenance_mode:
		mrinimitable.throw(mrinimitable._("Scheduler can not be re-enabled when maintenance mode is active."))

	if is_scheduler_disabled():
		enable_scheduler()
	if mrinimitable.conf.pause_scheduler:
		update_site_config("pause_scheduler", 0)


@mrinimitable.whitelist()
def get_scheduler_status():
	if is_scheduler_inactive():
		return {"status": "inactive"}
	return {"status": "active"}


def get_scheduler_tick() -> int:
	conf = mrinimitable.get_conf()
	return cint(conf.scheduler_tick_interval) or DEFAULT_SCHEDULER_TICK
