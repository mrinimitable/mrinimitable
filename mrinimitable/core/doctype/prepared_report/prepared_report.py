# Copyright (c) 2018, Mrinimitable Technologies and contributors
# License: MIT. See LICENSE
import gzip
import json
import resource
from contextlib import suppress
from typing import Any

from rq import get_current_job

import mrinimitable
from mrinimitable.database.utils import dangerously_reconnect_on_connection_abort
from mrinimitable.desk.form.load import get_attachments
from mrinimitable.desk.query_report import generate_report_result
from mrinimitable.model.document import Document
from mrinimitable.monitor import add_data_to_monitor
from mrinimitable.utils import add_to_date, now
from mrinimitable.utils.background_jobs import enqueue

# If prepared report runs for longer than this time it's automatically considered as failed
FAILURE_THRESHOLD = 6 * 60 * 60
REPORT_TIMEOUT = 25 * 60


class PreparedReport(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.types import DF

		error_message: DF.Text | None
		filters: DF.SmallText | None
		job_id: DF.Data | None
		peak_memory_usage: DF.Int
		queued_at: DF.Datetime | None
		queued_by: DF.Data | None
		report_end_time: DF.Datetime | None
		report_name: DF.Data
		status: DF.Literal["Error", "Queued", "Completed", "Started"]
	# end: auto-generated types

	@property
	def queued_by(self):
		return self.owner

	@property
	def queued_at(self):
		return self.creation

	@staticmethod
	def clear_old_logs(days=30):
		prepared_reports_to_delete = mrinimitable.get_all(
			"Prepared Report",
			filters={"creation": ["<", mrinimitable.utils.add_days(mrinimitable.utils.now(), -days)]},
		)

		for batch in mrinimitable.utils.create_batch(prepared_reports_to_delete, 100):
			enqueue(method=delete_prepared_reports, reports=batch)

	def before_insert(self):
		self.status = "Queued"

	def on_trash(self):
		"""Remove pending job from queue, if already running then kill the job."""
		if self.status not in ("Started", "Queued"):
			return

		with suppress(Exception):
			job = mrinimitable.get_doc("RQ Job", self.job_id)
			job.stop_job() if self.status == "Started" else job.delete()

	def after_insert(self):
		timeout = mrinimitable.get_value("Report", self.report_name, "timeout")
		enqueue(
			generate_report,
			queue="long",
			prepared_report=self.name,
			timeout=timeout or REPORT_TIMEOUT,
			enqueue_after_commit=True,
			at_front_when_starved=True,
		)

	def get_prepared_data(self, with_file_name=False):
		if attachments := get_attachments(self.doctype, self.name):
			attachment = None
			for f in attachments or []:
				if f.file_url.endswith(".gz"):
					attachment = f
					break

			attached_file = mrinimitable.get_doc("File", attachment.name)

			if with_file_name:
				return (gzip.decompress(attached_file.get_content()), attachment.file_name)
			return gzip.decompress(attached_file.get_content())


def generate_report(prepared_report):
	update_job_id(prepared_report)

	instance: PreparedReport = mrinimitable.get_doc("Prepared Report", prepared_report)
	report = mrinimitable.get_doc("Report", instance.report_name)

	add_data_to_monitor(report=instance.report_name)

	try:
		report.custom_columns = []

		if report.report_type == "Custom Report":
			custom_report_doc = report
			reference_report = custom_report_doc.reference_report
			report = mrinimitable.get_doc("Report", reference_report)
			if custom_report_doc.json:
				data = json.loads(custom_report_doc.json)
				if data:
					report.custom_columns = data["columns"]

		result = generate_report_result(report=report, filters=instance.filters, user=instance.owner)
		create_json_gz_file(result, instance.doctype, instance.name, instance.report_name)

		instance.status = "Completed"
	except Exception:
		# we need to ensure that error gets stored
		_save_error(instance, error=mrinimitable.get_traceback(with_context=True))

	instance.report_end_time = mrinimitable.utils.now()
	instance.peak_memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
	add_data_to_monitor(peak_memory_usage=instance.peak_memory_usage)
	instance.save(ignore_permissions=True)

	mrinimitable.publish_realtime(
		"report_generated",
		{"report_name": instance.report_name, "name": instance.name},
		user=mrinimitable.session.user,
	)


@dangerously_reconnect_on_connection_abort
def _save_error(instance, error):
	instance.reload()
	instance.status = "Error"
	instance.error_message = error
	instance.save(ignore_permissions=True)


def update_job_id(prepared_report):
	job = get_current_job()

	mrinimitable.db.set_value(
		"Prepared Report",
		prepared_report,
		{
			"job_id": job and job.id,
			"status": "Started",
		},
	)

	mrinimitable.db.commit()


@mrinimitable.whitelist()
def make_prepared_report(report_name, filters=None):
	"""run reports in background"""
	prepared_report = mrinimitable.get_doc(
		{
			"doctype": "Prepared Report",
			"report_name": report_name,
			"filters": process_filters_for_prepared_report(filters),
		}
	).insert(ignore_permissions=True)

	return {"name": prepared_report.name}


def process_filters_for_prepared_report(filters: dict[str, Any] | str) -> str:
	if isinstance(filters, str):
		filters = json.loads(filters)

	# This looks like an insanity but, without this it'd be very hard to find Prepared Reports matching given condition
	# We're ensuring that spacing is consistent. e.g. JS seems to put no spaces after ":", Python on the other hand does.
	# We are also ensuring that order of keys is same so generated JSON string will be identical too.
	# PS: mrinimitable.as_json sorts keys
	return mrinimitable.as_json(filters, indent=None, separators=(",", ":"))


@mrinimitable.whitelist()
def get_reports_in_queued_state(report_name, filters):
	return mrinimitable.get_all(
		"Prepared Report",
		filters={
			"report_name": report_name,
			"filters": process_filters_for_prepared_report(filters),
			"status": ("in", ("Queued", "Started")),
			"owner": mrinimitable.session.user,
		},
	)


def get_completed_prepared_report(filters, user, report_name):
	return mrinimitable.db.get_value(
		"Prepared Report",
		filters={
			"status": "Completed",
			"filters": process_filters_for_prepared_report(filters),
			"owner": user,
			"report_name": report_name,
		},
	)


def expire_stalled_report():
	mrinimitable.db.set_value(
		"Prepared Report",
		{
			"status": "Started",
			"creation": ("<", add_to_date(now(), seconds=-FAILURE_THRESHOLD, as_datetime=True)),
		},
		{
			"status": "Failed",
			"error_message": mrinimitable._("Report timed out."),
		},
		update_modified=False,
	)


@mrinimitable.whitelist()
def delete_prepared_reports(reports):
	reports = mrinimitable.parse_json(reports)
	for report in reports:
		prepared_report = mrinimitable.get_doc("Prepared Report", report["name"])
		if prepared_report.has_permission():
			prepared_report.delete(ignore_permissions=True, delete_permanently=True)


def create_json_gz_file(data, dt, dn, report_name):
	# Storing data in CSV file causes information loss
	# Reports like P&L Statement were completely unsuable because of this
	json_filename = "{}_{}.json.gz".format(
		mrinimitable.scrub(report_name), mrinimitable.utils.data.format_datetime(mrinimitable.utils.now(), "Y-m-d-H-M")
	)
	encoded_content = mrinimitable.safe_encode(mrinimitable.as_json(data, indent=None, separators=(",", ":")))
	compressed_content = gzip.compress(encoded_content, compresslevel=5)

	# Call save() file function to upload and attach the file
	_file = mrinimitable.get_doc(
		{
			"doctype": "File",
			"file_name": json_filename,
			"attached_to_doctype": dt,
			"attached_to_name": dn,
			"content": compressed_content,
			"is_private": 1,
		}
	)
	_file.save(ignore_permissions=True)


@mrinimitable.whitelist()
def download_attachment(dn):
	pr = mrinimitable.get_doc("Prepared Report", dn)
	if not pr.has_permission("read"):
		mrinimitable.throw(mrinimitable._("Cannot Download Report due to insufficient permissions"))

	data, file_name = pr.get_prepared_data(with_file_name=True)
	mrinimitable.local.response.filename = file_name[:-3]
	mrinimitable.local.response.filecontent = data
	mrinimitable.local.response.type = "binary"


def get_permission_query_condition(user):
	if not user:
		user = mrinimitable.session.user
	if user == "Administrator":
		return None

	from mrinimitable.utils.user import UserPermissions

	user = UserPermissions(user)

	if "System Manager" in user.roles:
		return None

	reports = [mrinimitable.db.escape(report) for report in user.get_all_reports().keys()]

	return """`tabPrepared Report`.report_name in ({reports})""".format(reports=",".join(reports))


def has_permission(doc, user):
	if not user:
		user = mrinimitable.session.user
	if user == "Administrator":
		return True

	from mrinimitable.utils.user import UserPermissions

	user = UserPermissions(user)

	if "System Manager" in user.roles:
		return True

	return doc.report_name in user.get_all_reports().keys()


@mrinimitable.whitelist()
def enqueue_json_to_csv_conversion(prepared_report_name):
	"""Call this to enqueue the conversion in background."""
	enqueue(method=convert_json_to_csv, queue="long", prepared_report_name=prepared_report_name)


def convert_json_to_csv(prepared_report_name):
	"""Background job: Fetch JSON file, convert to CSV, attach CSV to Prepared Report."""

	import csv
	from io import StringIO

	doc = mrinimitable.get_doc("Prepared Report", prepared_report_name)
	json_content, file_name = doc.get_prepared_data(with_file_name=True)

	if not json_content:
		mrinimitable.log_error(f"No JSON content found for {prepared_report_name}", "CSV Conversion")
		return

	parsed = json.loads(json_content)

	columns = parsed.get("columns", [])
	result = parsed.get("result", [])

	if not columns or not result:
		mrinimitable.log_error("Columns or result is empty", "CSV Conversion")
		return

	fieldnames = [col.get("fieldname") for col in columns if col.get("fieldname")]

	output = StringIO()
	writer = csv.DictWriter(output, fieldnames=fieldnames)
	writer.writeheader()
	for row in result:
		writer.writerow({key: row.get(key, "") for key in fieldnames})

	csv_content = output.getvalue().encode("utf-8")

	_file = mrinimitable.get_doc(
		{
			"doctype": "File",
			"file_name": f"csv_{file_name[:-8]}.csv",
			"attached_to_doctype": "Prepared Report",
			"attached_to_name": prepared_report_name,
			"content": csv_content,
			"is_private": 1,
		}
	)
	_file.save(ignore_permissions=True)

	mrinimitable.get_doc(
		{
			"doctype": "Notification Log",
			"subject": "Your CSV file is ready for download",
			"email_content": f'Click <a href="{_file.file_url}" target="_blank">here</a> to download the file.',
			"for_user": mrinimitable.session.user,
			"type": "Alert",
			"document_type": "File",
			"document_name": _file.name,
			"link": _file.file_url,
		}
	).insert(ignore_permissions=True)
