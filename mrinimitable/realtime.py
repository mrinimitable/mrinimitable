# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from contextlib import suppress

import redis

import mrinimitable
from mrinimitable.utils.data import cstr


def publish_progress(percent, title=None, doctype=None, docname=None, description=None, task_id=None):
	publish_realtime(
		"progress",
		{"percent": percent, "title": title, "description": description},
		user=None if doctype and docname else mrinimitable.session.user,
		doctype=doctype,
		docname=docname,
		task_id=task_id,
	)


def publish_realtime(
	event: str | None = None,
	message: dict | None = None,
	room: str | None = None,
	user: str | None = None,
	doctype: str | None = None,
	docname: str | None = None,
	task_id: str | None = None,
	after_commit: bool = False,
):
	"""Publish real-time updates

	:param event: Event name, like `task_progress` etc. that will be handled by the client (default is `task_progress` if within task or `global`)
	:param message: JSON message object. For async must contain `task_id`
	:param room: Room in which to publish update (default entire site)
	:param user: Transmit to user
	:param doctype: Transmit to doctype, docname
	:param docname: Transmit to doctype, docname
	:param after_commit: (default False) will emit after current transaction is committed"""
	if message is None:
		message = {}

	if not task_id and hasattr(mrinimitable.local, "task_id"):
		task_id = mrinimitable.local.task_id

	if event is None:
		event = "task_progress" if task_id else "global"
	elif event == "msgprint" and not user:
		user = mrinimitable.session.user
	elif event == "list_update":
		doctype = doctype or message.get("doctype")
		room = get_doctype_room(doctype)
	elif event == "docinfo_update":
		room = get_doc_room(doctype, docname)

	if not room:
		if task_id:
			after_commit = False
			if "task_id" not in message:
				message["task_id"] = task_id
			room = get_task_progress_room(task_id)
		elif user:
			# transmit to specific user: System, Website or Guest
			room = get_user_room(user)
		elif doctype and docname:
			room = get_doc_room(doctype, docname)
		else:
			# This will be broadcasted to all Desk users
			room = get_site_room()

	if after_commit:
		if not hasattr(mrinimitable.local, "_realtime_log"):
			mrinimitable.local._realtime_log = []
			mrinimitable.db.after_commit.add(flush_realtime_log)
			mrinimitable.db.after_rollback.add(clear_realtime_log)

		params = [event, message, room]
		if params not in mrinimitable.local._realtime_log:
			mrinimitable.local._realtime_log.append(params)
	else:
		emit_via_redis(event, message, room)


def flush_realtime_log():
	if not hasattr(mrinimitable.local, "_realtime_log"):
		return
	for args in mrinimitable.local._realtime_log:
		mrinimitable.realtime.emit_via_redis(*args)

	clear_realtime_log()


def clear_realtime_log():
	if hasattr(mrinimitable.local, "_realtime_log"):
		del mrinimitable.local._realtime_log


def emit_via_redis(event, message, room):
	"""Publish real-time updates via redis

	:param event: Event name, like `task_progress` etc.
	:param message: JSON message object. For async must contain `task_id`
	:param room: name of the room"""
	from mrinimitable.utils.background_jobs import get_redis_connection_without_auth

	with suppress(redis.exceptions.ConnectionError):
		r = get_redis_connection_without_auth()
		r.publish(
			"events",
			mrinimitable.as_json(
				{"event": event, "message": message, "room": room, "namespace": mrinimitable.local.site}
			),
		)


@mrinimitable.whitelist(allow_guest=True)
def has_permission(doctype: str, name: str) -> bool:
	mrinimitable.has_permission(doctype, doc=name, throw=True)
	return True


@mrinimitable.whitelist(allow_guest=True)
def get_user_info():
	user_type = mrinimitable.session.data.user_type
	# For requests with Bearer tokens, user_type is not set in the session data
	if not user_type:
		user_type = mrinimitable.get_cached_value("User", mrinimitable.session.user, "user_type")
	return {
		"user": mrinimitable.session.user,
		"user_type": user_type,
		"installed_apps": mrinimitable.get_installed_apps(),
	}


def get_doctype_room(doctype):
	return f"doctype:{doctype}"


def get_doc_room(doctype, docname):
	return f"doc:{doctype}/{cstr(docname)}"


def get_user_room(user):
	return f"user:{user}"


def get_site_room():
	return "all"


def get_task_progress_room(task_id):
	return f"task_progress:{task_id}"


def get_website_room():
	return "website"
