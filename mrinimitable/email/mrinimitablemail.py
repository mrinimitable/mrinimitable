from datetime import datetime
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import mrinimitable
from mrinimitable import _
from mrinimitable.mrinimitableclient import MrinimitableClient, MrinimitableOAuth2Client
from mrinimitable.utils import convert_utc_to_system_timezone, get_datetime, get_system_timezone


class MrinimitableMail:
	"""Class to interact with the Mrinimitable Mail API."""

	def __init__(
		self,
		site: str,
		email: str,
		api_key: str | None = None,
		api_secret: str | None = None,
		access_token: str | None = None,
	) -> None:
		self.site = site
		self.email = email
		self.api_key = api_key
		self.api_secret = api_secret
		self.access_token = access_token
		self.client = self.get_client(self.site, self.email, self.api_key, self.api_secret, self.access_token)

	@staticmethod
	def get_client(
		site: str,
		email: str,
		api_key: str | None = None,
		api_secret: str | None = None,
		access_token: str | None = None,
	) -> MrinimitableClient | MrinimitableOAuth2Client:
		"""Returns a MrinimitableClient or MrinimitableOAuth2Client instance."""

		if hasattr(mrinimitable.local, "mrinimitable_mail_clients"):
			if client := mrinimitable.local.mrinimitable_mail_clients.get(email):
				return client
		else:
			mrinimitable.local.mrinimitable_mail_clients = {}

		client = (
			MrinimitableOAuth2Client(url=site, access_token=access_token)
			if access_token
			else MrinimitableClient(url=site, api_key=api_key, api_secret=api_secret)
		)
		mrinimitable.local.mrinimitable_mail_clients[email] = client

		return client

	def request(
		self,
		method: str,
		endpoint: str,
		params: dict | None = None,
		data: dict | None = None,
		json: dict | None = None,
		files: dict | None = None,
		headers: dict[str, str] | None = None,
		timeout: int | tuple[int, int] = (60, 120),
	) -> Any | None:
		"""Makes a request to the Mrinimitable Mail API."""

		url = urljoin(self.client.url, endpoint)

		headers = headers or {}
		headers.update(self.client.headers)

		if files:
			headers.pop("content-type", None)

		response = self.client.session.request(
			method=method,
			url=url,
			params=params,
			data=data,
			json=json,
			files=files,
			headers=headers,
			timeout=timeout,
		)
		response.raise_for_status()

		return self.client.post_process(response)

	def validate(self) -> None:
		"""Validates if the user is allowed to send or receive emails."""

		endpoint = "/api/method/mail.api.auth.validate"
		data = {"email": self.email}
		self.request("POST", endpoint=endpoint, data=data)

	def send_raw(
		self, sender: str, recipients: str | list, message: str | bytes, is_newsletter: bool = False
	) -> None:
		"""Sends an email using the Mrinimitable Mail API."""

		endpoint = "/api/method/mail.api.outbound.send_raw"
		data = {"from_": sender, "to": recipients, "is_newsletter": is_newsletter}
		self.request("POST", endpoint=endpoint, data=data, files={"raw_message": message})

	def pull_raw(
		self, mailbox: str = "inbox", limit: int = 50, last_received_at: str | None = None
	) -> dict[str, str | list[str]]:
		"""Pull emails for the account using the Mrinimitable Mail API."""

		endpoint = "/api/method/mail.api.inbound.pull_raw"
		if last_received_at:
			last_received_at = add_or_update_tzinfo(last_received_at)

		data = {"mailbox": mailbox, "limit": limit, "last_received_at": last_received_at}
		headers = {"X-Site": mrinimitable.utils.get_url()}
		response = self.request("GET", endpoint=endpoint, data=data, headers=headers)
		last_received_at = convert_utc_to_system_timezone(get_datetime(response["last_received_at"]))

		return {"latest_messages": response["mails"], "last_received_at": last_received_at}


def add_or_update_tzinfo(date_time: datetime | str, timezone: str | None = None) -> str:
	"""Adds or updates timezone to the datetime."""
	date_time = get_datetime(date_time)
	target_tz = ZoneInfo(timezone or get_system_timezone())

	if date_time.tzinfo is None:
		date_time = date_time.replace(tzinfo=target_tz)
	else:
		date_time = date_time.astimezone(target_tz)

	return str(date_time)
