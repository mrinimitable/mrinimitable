# Copyright (c) 2022, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import smtplib
from contextlib import suppress

import mrinimitable
from mrinimitable import _
from mrinimitable.email.oauth import Oauth
from mrinimitable.utils import cint, cstr, get_traceback


class InvalidEmailCredentials(mrinimitable.ValidationError):
	pass


class SMTPServer:
	def __init__(
		self,
		server,
		login=None,
		email_account=None,
		password=None,
		port=None,
		use_tls=None,
		use_ssl=None,
		use_oauth=0,
		access_token=None,
	):
		self.login = login
		self.email_account = email_account
		self.password = password
		self._server = server
		self._port = port
		self.use_tls = use_tls
		self.use_ssl = use_ssl
		self.use_oauth = use_oauth
		self.access_token = access_token
		self._session = None

		if not self.server:
			mrinimitable.msgprint(
				_("Email Account not setup. Please create a new Email Account from Settings > Email Account"),
				raise_exception=mrinimitable.OutgoingEmailError,
			)

	@property
	def port(self):
		port = self._port or (self.use_ssl and 465) or (self.use_tls and 587)
		return cint(port)

	@property
	def server(self):
		return cstr(self._server or "")

	def secure_session(self, conn):
		"""Secure the connection incase of TLS."""
		if self.use_tls:
			conn.ehlo()
			conn.starttls()
			conn.ehlo()

	@property
	def session(self):
		"""Get SMTP session.

		We make best effort to revive connection if it's disconnected by checking the connection
		health before returning it to user."""
		if self.is_session_active():
			return self._session

		SMTP = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP

		try:
			_session = SMTP(self.server, self.port, timeout=2 * 60)
			if not _session:
				mrinimitable.msgprint(
					_("Could not connect to outgoing email server"), raise_exception=mrinimitable.OutgoingEmailError
				)

			self.secure_session(_session)

			if self.use_oauth:
				Oauth(_session, self.email_account, self.login, self.access_token).connect()

			elif self.password:
				res = _session.login(str(self.login or ""), str(self.password or ""))

				# check if logged correctly
				if res[0] != 235:
					mrinimitable.msgprint(res[1], raise_exception=mrinimitable.OutgoingEmailError)

			self._session = _session
			self._enqueue_connection_closure()
			return self._session

		except smtplib.SMTPAuthenticationError:
			self.throw_invalid_credentials_exception()

		except OSError as e:
			# Invalid mail server -- due to refusing connection
			mrinimitable.throw(
				_("Invalid Outgoing Mail Server or Port: {0}").format(str(e)),
				title=_("Incorrect Configuration"),
			)

	def _enqueue_connection_closure(self):
		if mrinimitable.request and hasattr(mrinimitable.request, "after_response"):
			mrinimitable.request.after_response.add(self.quit)
		elif mrinimitable.job:
			mrinimitable.job.after_job.add(self.quit)
		elif not mrinimitable.in_test:
			# Console?
			import atexit

			atexit.register(self.quit)

	def is_session_active(self):
		if self._session:
			try:
				return self._session.noop()[0] == 250
			except Exception:
				return False

	def quit(self):
		with suppress(TimeoutError):
			if self.is_session_active():
				self._session.quit()

	@classmethod
	def throw_invalid_credentials_exception(cls):
		original_exception = get_traceback() or "\n"
		mrinimitable.throw(
			_("Please check your email login credentials.") + " " + original_exception.splitlines()[-1],
			title=_("Invalid Credentials"),
			exc=InvalidEmailCredentials,
		)
