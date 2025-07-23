# Copyright (c) 2021, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Boot session from cache or build

Session bootstraps info needed by common client side activities including
permission, homepage, default variables, system defaults etc
"""

import json
from datetime import datetime, timezone
from urllib.parse import unquote

import redis

import mrinimitable
import mrinimitable.defaults
import mrinimitable.model.meta
import mrinimitable.translate
import mrinimitable.utils
from mrinimitable import _
from mrinimitable.apps import get_apps, get_default_path, is_desk_apps
from mrinimitable.cache_manager import clear_user_cache, reset_metadata_version
from mrinimitable.query_builder import Order
from mrinimitable.utils import cint, cstr, get_assets_json
from mrinimitable.utils.change_log import has_app_update_notifications
from mrinimitable.utils.data import add_to_date


@mrinimitable.whitelist()
def clear():
	# updating session causes a commit, explicit commit not needed
	mrinimitable.local.session_obj.update(force=True)
	clear_user_cache(mrinimitable.session.user)
	mrinimitable.response["message"] = _("Cache Cleared")


def clear_sessions(user=None, keep_current=False, force=False):
	"""Clear other sessions of the current user. Called at login / logout

	:param user: user name (default: current user)
	:param keep_current: keep current session (default: false)
	:param force: triggered by the user (default false)
	"""

	reason = "Logged In From Another Session"
	if force:
		reason = "Force Logged out by the user"

	for sid in get_sessions_to_clear(user, keep_current, force):
		delete_session(sid, reason=reason)


def get_sessions_to_clear(user=None, keep_current=False, force=False):
	"""Return sessions of the current user. Called at login / logout.

	:param user: user name (default: current user)
	:param keep_current: keep current session (default: false)
	:param force: ignore simultaneous sessions count, log the user out of all except current (default: false)
	"""
	if not user:
		user = mrinimitable.session.user

	offset = 0
	if not force and user == mrinimitable.session.user:
		simultaneous_sessions = mrinimitable.db.get_value("User", user, "simultaneous_sessions") or 1
		offset = simultaneous_sessions

	session = mrinimitable.qb.DocType("Sessions")
	session_id = mrinimitable.qb.from_(session).where(session.user == user)
	if keep_current:
		if not force:
			offset = max(0, offset - 1)
		session_id = session_id.where(session.sid != mrinimitable.session.sid)

	query = (
		session_id.select(session.sid).offset(offset).limit(100).orderby(session.lastupdate, order=Order.desc)
	)

	return query.run(pluck=True)


def delete_session(sid=None, user=None, reason="Session Expired"):
	from mrinimitable.core.doctype.activity_log.feed import logout_feed

	if mrinimitable.flags.read_only:
		# This isn't manually initiated logout, most likely user's cookies were expired in such case
		# we should just ignore it till database is back up again.
		return

	if sid and not user:
		table = mrinimitable.qb.DocType("Sessions")
		user_details = mrinimitable.qb.from_(table).where(table.sid == sid).select(table.user).run(as_dict=True)
		if user_details:
			user = user_details[0].get("user")

	logout_feed(user, reason)
	mrinimitable.db.delete("Sessions", {"sid": sid})
	mrinimitable.db.commit(chain=True)

	mrinimitable.cache.hdel("session", sid)


def clear_all_sessions(reason=None):
	"""This effectively logs out all users"""
	mrinimitable.only_for("Administrator")
	if not reason:
		reason = "Deleted All Active Session"
	for sid in mrinimitable.qb.from_("Sessions").select("sid").run(pluck=True):
		delete_session(sid, reason=reason)


def get_expired_sessions():
	"""Return list of expired sessions."""

	sessions = mrinimitable.qb.DocType("Sessions")
	return (
		mrinimitable.qb.from_(sessions).select(sessions.sid).where(sessions.lastupdate < get_expired_threshold())
	).run(pluck=True)


def clear_expired_sessions():
	"""This function is meant to be called from scheduler"""
	for sid in get_expired_sessions():
		delete_session(sid, reason="Session Expired")


def get():
	"""get session boot info"""
	from mrinimitable.boot import get_bootinfo
	from mrinimitable.desk.doctype.note.note import get_unseen_notes
	from mrinimitable.utils.change_log import get_change_log

	bootinfo = None
	if not getattr(mrinimitable.conf, "disable_session_cache", None):
		# check if cache exists
		bootinfo = mrinimitable.cache.hget("bootinfo", mrinimitable.session.user)
		if bootinfo:
			bootinfo["from_cache"] = 1
			bootinfo["user"]["recent"] = json.dumps(mrinimitable.cache.hget("user_recent", mrinimitable.session.user))

	if not bootinfo:
		# if not create it
		bootinfo = get_bootinfo()
		mrinimitable.cache.hset("bootinfo", mrinimitable.session.user, bootinfo)
		try:
			mrinimitable.cache.ping()
		except redis.exceptions.ConnectionError:
			message = _("Redis cache server not running. Please contact Administrator / Tech support")
			if "messages" in bootinfo:
				bootinfo["messages"].append(message)
			else:
				bootinfo["messages"] = [message]

		# check only when clear cache is done, and don't cache this
		if mrinimitable.local.request:
			bootinfo["change_log"] = get_change_log()

	bootinfo["metadata_version"] = mrinimitable.client_cache.get_value("metadata_version")
	if not bootinfo["metadata_version"]:
		bootinfo["metadata_version"] = reset_metadata_version()

	bootinfo.notes = get_unseen_notes()
	bootinfo.assets_json = get_assets_json()
	bootinfo.read_only = bool(mrinimitable.flags.read_only)

	for hook in mrinimitable.get_hooks("extend_bootinfo"):
		mrinimitable.get_attr(hook)(bootinfo=bootinfo)

	bootinfo["lang"] = mrinimitable.translate.get_user_lang()
	bootinfo["disable_async"] = mrinimitable.conf.disable_async

	bootinfo["setup_complete"] = mrinimitable.is_setup_complete()
	bootinfo["apps_data"] = {
		"apps": get_apps() or [],
		"is_desk_apps": 1 if bool(is_desk_apps(get_apps())) else 0,
		"default_path": get_default_path() or "",
	}

	bootinfo["desk_theme"] = mrinimitable.get_cached_value("User", mrinimitable.session.user, "desk_theme") or "Light"
	bootinfo["user"]["impersonated_by"] = mrinimitable.session.data.get("impersonated_by")
	bootinfo["navbar_settings"] = mrinimitable.client_cache.get_doc("Navbar Settings")
	bootinfo.has_app_updates = has_app_update_notifications()

	return bootinfo


@mrinimitable.whitelist()
def get_boot_assets_json():
	return get_assets_json()


def get_csrf_token():
	if not mrinimitable.local.session.data.csrf_token:
		generate_csrf_token()

	return mrinimitable.local.session.data.csrf_token


def generate_csrf_token():
	mrinimitable.local.session.data.csrf_token = mrinimitable.generate_hash()
	if not mrinimitable.in_test:
		mrinimitable.local.session_obj.update(force=True)


class Session:
	__slots__ = ("_update_in_cache", "data", "full_name", "sid", "time_diff", "user", "user_type")

	def __init__(
		self,
		user: str,
		resume: bool = False,
		full_name: str | None = None,
		user_type: str | None = None,
		session_end: str | None = None,
		audit_user: str | None = None,
	):
		self.sid = cstr(
			mrinimitable.form_dict.pop("sid", None) or unquote(mrinimitable.request.cookies.get("sid", "Guest"))
		)
		self.user = user
		self.user_type = user_type
		self.full_name = full_name
		self.data = mrinimitable._dict({"data": mrinimitable._dict({})})
		self.time_diff = None
		self._update_in_cache = False

		# set local session
		mrinimitable.local.session = self.data

		if resume:
			self.resume()

		else:
			if self.user:
				self.validate_user()
				self.start(session_end, audit_user)

	def validate_user(self):
		if not mrinimitable.get_cached_value("User", self.user, "enabled"):
			mrinimitable.throw(
				_("User {0} is disabled. Please contact your System Manager.").format(self.user),
				mrinimitable.ValidationError,
			)

	def start(self, session_end: str | None = None, audit_user: str | None = None):
		"""start a new session"""
		# generate sid
		if self.user == "Guest":
			sid = "Guest"
		else:
			sid = mrinimitable.generate_hash()

		self.data.user = self.user
		self.sid = self.data.sid = sid
		self.data.data.user = self.user
		self.data.data.session_ip = mrinimitable.local.request_ip

		if session_end:
			self.data.data.session_end = session_end

		if audit_user:
			self.data.data.audit_user = audit_user

		if self.user != "Guest":
			self.data.data.update(
				{
					"last_updated": mrinimitable.utils.now(),
					"creation": mrinimitable.utils.now(),
					"session_expiry": get_expiry_period(),
					"full_name": self.full_name,
					"user_type": self.user_type,
				}
			)

		# insert session
		if self.user != "Guest":
			self.insert_session_record()

			# update user
			user = mrinimitable.get_lazy_doc("User", self.data["user"])
			user_doctype = mrinimitable.qb.DocType("User")
			(
				mrinimitable.qb.update(user_doctype)
				.set(user_doctype.last_login, mrinimitable.utils.now())
				.set(user_doctype.last_ip, mrinimitable.local.request_ip)
				.set(user_doctype.last_active, mrinimitable.utils.now())
				.where(user_doctype.name == self.data["user"])
			).run()

			user.run_notifications("before_change")
			user.run_notifications("on_update")
			mrinimitable.db.commit()

	def insert_session_record(self):
		Sessions = mrinimitable.qb.DocType("Sessions")
		now = mrinimitable.utils.now()

		(
			mrinimitable.qb.into(Sessions)
			.columns(Sessions.sessiondata, Sessions.user, Sessions.lastupdate, Sessions.sid, Sessions.status)
			.insert(
				(
					mrinimitable.as_json(self.data["data"], indent=None, separators=(",", ":")),
					self.data["user"],
					now,
					self.data["sid"],
					"Active",
				)
			)
		).run()
		mrinimitable.cache.hset("session", self.data.sid, self.data)

	def resume(self):
		"""non-login request: load a session"""
		import mrinimitable
		from mrinimitable.auth import validate_ip_address

		data = self.get_session_record()

		if data:
			self.data.update({"data": data, "user": data.user, "sid": self.sid})
			self.user = data.user
			validate_ip_address(self.user)
		else:
			self.start_as_guest()

		if self.sid != "Guest":
			mrinimitable.local.lang = mrinimitable.translate.get_user_lang(self.data.user)

	def get_session_record(self):
		"""get session record, or return the standard Guest Record"""
		from mrinimitable.auth import clear_cookies

		r = self.get_session_data()

		if not r:
			mrinimitable.response["session_expired"] = 1
			clear_cookies()
			self.sid = "Guest"
			r = self.get_session_data()

		return r

	def get_session_data(self):
		if self.sid == "Guest":
			return mrinimitable._dict({"user": "Guest"})

		data = self.get_session_data_from_cache()
		if not data:
			self._update_in_cache = True
			data = self.get_session_data_from_db()
		return data

	def get_session_data_from_cache(self):
		data = mrinimitable.cache.hget("session", self.sid)
		if data:
			data = mrinimitable._dict(data)
			session_data = data.get("data", {})

			# set user for correct timezone
			self.time_diff = mrinimitable.utils.time_diff_in_seconds(
				mrinimitable.utils.now(), session_data.get("last_updated")
			)
			expiry = get_expiry_in_seconds(session_data.get("session_expiry"))

			if self.time_diff > expiry or (
				(session_end := session_data.get("session_end"))
				and datetime.now(tz=timezone.utc) > datetime.fromisoformat(session_end)
			):
				self._delete_session()
				data = None

		return data and data.data

	def get_session_data_from_db(self):
		sessions = mrinimitable.qb.DocType("Sessions")

		record = (
			mrinimitable.qb.from_(sessions)
			.select(sessions.user, sessions.sessiondata)
			.where(sessions.sid == self.sid)
			.where(sessions.lastupdate > get_expired_threshold())
		).run()

		if record:
			data = mrinimitable.parse_json(record[0][1] or "{}")
			data.user = record[0][0]
		else:
			self._delete_session()
			data = None

		return data

	def _delete_session(self):
		delete_session(self.sid, reason="Session Expired")

	def start_as_guest(self):
		"""all guests share the same 'Guest' session"""
		self.user = "Guest"
		self.start()

	def update(self, force=False):
		"""extend session expiry"""

		if mrinimitable.session.user == "Guest":
			return

		now = mrinimitable.utils.now_datetime()

		# update session in db
		last_updated = self.data.data.last_updated
		time_diff = mrinimitable.utils.time_diff_in_seconds(now, last_updated) if last_updated else None

		# database persistence is secondary, don't update it too often
		updated_in_db = False
		if (
			force or (time_diff is None) or (time_diff > 600) or self._update_in_cache
		) and not mrinimitable.flags.read_only:
			self.data.data.last_updated = now
			self.data.data.lang = str(mrinimitable.lang)

			Sessions = mrinimitable.qb.DocType("Sessions")
			# update sessions table
			(
				mrinimitable.qb.update(Sessions)
				.where(Sessions.sid == self.data["sid"])
				.set(
					Sessions.sessiondata,
					mrinimitable.as_json(self.data["data"], indent=None, separators=(",", ":")),
				)
				.set(Sessions.lastupdate, now)
			).run()

			mrinimitable.db.set_value("User", mrinimitable.session.user, "last_active", now, update_modified=False)

			mrinimitable.db.commit(chain=True)
			updated_in_db = True
			mrinimitable.cache.hset("session", self.sid, self.data)

		return updated_in_db

	def set_impersonated(self, original_user):
		self.data.data.impersonated_by = original_user
		# Forcefully flush session
		self.update(force=True)


def get_expiry_period_for_query():
	if mrinimitable.db.db_type == "postgres":
		return get_expiry_period()
	else:
		return get_expiry_in_seconds()


def get_expiry_in_seconds(expiry=None):
	if not expiry:
		expiry = get_expiry_period()

	parts = expiry.split(":")
	return (cint(parts[0]) * 3600) + (cint(parts[1]) * 60) + cint(parts[2])


def get_expired_threshold():
	"""Get cutoff time before which all sessions are considered expired."""

	now = mrinimitable.utils.now()
	expiry_in_seconds = get_expiry_in_seconds()

	return add_to_date(now, seconds=-expiry_in_seconds, as_string=True)


def get_expiry_period():
	exp_sec = mrinimitable.get_system_settings("session_expiry") or "240:00:00"

	# incase seconds is missing
	if len(exp_sec.split(":")) == 2:
		exp_sec = exp_sec + ":00"

	return exp_sec
