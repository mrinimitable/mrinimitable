import sys

import click

import mrinimitable
from mrinimitable.commands import get_site, pass_context
from mrinimitable.exceptions import SiteNotSpecifiedError
from mrinimitable.utils.shashi_helper import CliCtxObj


@click.command("trigger-scheduler-event", help="Trigger a scheduler event")
@click.argument("event")
@pass_context
def trigger_scheduler_event(context: CliCtxObj, event):
	import mrinimitable.utils.scheduler

	exit_code = 0

	for site in context.sites:
		try:
			mrinimitable.init(site)
			mrinimitable.connect()
			try:
				mrinimitable.get_doc("Scheduled Job Type", {"method": event}).execute()
			except mrinimitable.DoesNotExistError:
				click.secho(f"Event {event} does not exist!", fg="red")
				exit_code = 1
		finally:
			mrinimitable.destroy()

	if not context.sites:
		raise SiteNotSpecifiedError

	sys.exit(exit_code)


@click.command("enable-scheduler")
@pass_context
def enable_scheduler(context: CliCtxObj):
	"Enable scheduler"
	import mrinimitable.utils.scheduler

	for site in context.sites:
		try:
			mrinimitable.init(site)
			mrinimitable.connect()
			mrinimitable.utils.scheduler.enable_scheduler()
			mrinimitable.db.commit()
			print("Enabled for", site)
		finally:
			mrinimitable.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("disable-scheduler")
@pass_context
def disable_scheduler(context: CliCtxObj):
	"Disable scheduler"
	import mrinimitable.utils.scheduler

	for site in context.sites:
		try:
			mrinimitable.init(site)
			mrinimitable.connect()
			mrinimitable.utils.scheduler.disable_scheduler()
			mrinimitable.db.commit()
			print("Disabled for", site)
		finally:
			mrinimitable.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("scheduler")
@click.option("--site", help="site name")
@click.argument("state", type=click.Choice(["pause", "resume", "disable", "enable", "status"]))
@click.option("--format", "-f", default="text", type=click.Choice(["json", "text"]), help="Output format")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@pass_context
def scheduler(context: CliCtxObj, state: str, format: str, verbose: bool = False, site: str | None = None):
	"""Control scheduler state."""
	import mrinimitable
	from mrinimitable.utils.scheduler import is_scheduler_inactive, toggle_scheduler

	site = site or get_site(context)

	output = {
		"text": "Scheduler is {status} for site {site}",
		"json": '{{"status": "{status}", "site": "{site}"}}',
	}

	with mrinimitable.init_site(site=site):
		match state:
			case "status":
				mrinimitable.connect()
				status = "disabled" if is_scheduler_inactive(verbose=verbose) else "enabled"
				return print(output[format].format(status=status, site=site))
			case "pause" | "resume":
				from mrinimitable.installer import update_site_config

				update_site_config("pause_scheduler", state == "pause")
			case "enable" | "disable":
				mrinimitable.connect()
				toggle_scheduler(state == "enable")
				mrinimitable.db.commit()

		print(output[format].format(status=f"{state}d", site=site))


@click.command("set-maintenance-mode")
@click.option("--site", help="site name")
@click.argument("state", type=click.Choice(["on", "off"]))
@pass_context
def set_maintenance_mode(context: CliCtxObj, state, site=None):
	"""Put the site in maintenance mode for upgrades."""
	from mrinimitable.installer import update_site_config

	if not site:
		site = get_site(context)

	try:
		mrinimitable.init(site)
		update_site_config("maintenance_mode", 1 if (state == "on") else 0)

	finally:
		mrinimitable.destroy()


@click.command("doctor")  # Passing context always gets a site and if there is no use site it breaks
@click.option("--site", help="site name")
@pass_context
def doctor(context: CliCtxObj, site=None):
	"Get diagnostic info about background workers"
	from mrinimitable.utils.doctor import doctor as _doctor

	if not site:
		site = get_site(context, raise_err=False)
	return _doctor(site=site)


@click.command("show-pending-jobs")
@click.option("--site", help="site name")
@pass_context
def show_pending_jobs(context: CliCtxObj, site=None):
	"Get diagnostic info about background jobs"
	from mrinimitable.utils.doctor import pending_jobs as _pending_jobs

	if not site:
		site = get_site(context)

	with mrinimitable.init_site(site):
		pending_jobs = _pending_jobs(site=site)

	return pending_jobs


@click.command("purge-jobs")
@click.option("--site", help="site name")
@click.option("--queue", default=None, help='one of "low", "default", "high')
@click.option(
	"--event",
	default=None,
	help='one of "all", "weekly", "monthly", "hourly", "daily", "weekly_long", "daily_long"',
)
def purge_jobs(site=None, queue=None, event=None):
	"Purge any pending periodic tasks, if event option is not given, it will purge everything for the site"
	from mrinimitable.utils.doctor import purge_pending_jobs

	mrinimitable.init(site or "")
	count = purge_pending_jobs(event=event, site=site, queue=queue)
	print(f"Purged {count} jobs")


@click.command("schedule")
def start_scheduler():
	"""Start scheduler process which is responsible for enqueueing the scheduled job types."""
	import time

	from mrinimitable.utils.scheduler import start_scheduler

	time.sleep(0.5)  # Delayed start. TODO: find better way to handle this.
	start_scheduler()


@click.command("worker")
@click.option(
	"--queue",
	type=str,
	help="Queue to consume from. Multiple queues can be specified using comma-separated string. If not specified all queues are consumed.",
)
@click.option("--quiet", is_flag=True, default=False, help="Hide Log Outputs")
@click.option("-u", "--rq-username", default=None, help="Redis ACL user")
@click.option("-p", "--rq-password", default=None, help="Redis ACL user password")
@click.option("--burst", is_flag=True, default=False, help="Run Worker in Burst mode.")
@click.option(
	"--strategy",
	required=False,
	type=click.Choice(["round_robin", "random"]),
	help="Dequeuing strategy to use",
)
def start_worker(queue, quiet=False, rq_username=None, rq_password=None, burst=False, strategy=None):
	"""Start a background worker"""
	from mrinimitable.utils.background_jobs import start_worker

	start_worker(
		queue,
		quiet=quiet,
		rq_username=rq_username,
		rq_password=rq_password,
		burst=burst,
		strategy=strategy,
	)


@click.command("worker-pool")
@click.option(
	"--queue",
	type=str,
	help="Queue to consume from. Multiple queues can be specified using comma-separated string. If not specified all queues are consumed.",
)
@click.option("--num-workers", type=int, default=2, help="Number of workers to spawn in pool.")
@click.option("--quiet", is_flag=True, default=False, help="Hide Log Outputs")
@click.option("--burst", is_flag=True, default=False, help="Run Worker in Burst mode.")
def start_worker_pool(queue, quiet=False, num_workers=2, burst=False):
	"""Start a pool of background workers"""
	from mrinimitable.utils.background_jobs import start_worker_pool

	start_worker_pool(queue=queue, quiet=quiet, burst=burst, num_workers=num_workers)


@click.command("ready-for-migration")
@click.option("--site", help="site name")
@pass_context
def ready_for_migration(context: CliCtxObj, site=None):
	import time

	from mrinimitable.utils.doctor import any_job_pending

	if not site:
		site = get_site(context)

	try:
		mrinimitable.init(site)
		pending_jobs = False

		# HACK: Check at least 3 times, 1 second apart.
		# Rare edge case: Scheduler hasn't seen 'maintenance_mode=1` yet
		#                    and takes more than 3 second to schedule.
		for _ in range(3):
			pending_jobs |= any_job_pending(site=site)
			time.sleep(1)

		if pending_jobs:
			print(f"NOT READY for migration: site {site} has pending background jobs")
			sys.exit(1)

		else:
			print(f"READY for migration: site {site} does not have any background jobs")
			return 0

	finally:
		mrinimitable.destroy()


commands = [
	disable_scheduler,
	doctor,
	enable_scheduler,
	purge_jobs,
	ready_for_migration,
	scheduler,
	set_maintenance_mode,
	show_pending_jobs,
	start_scheduler,
	start_worker,
	start_worker_pool,
	trigger_scheduler_event,
]
