# Copyright (c) 2021, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import os

import mrinimitable
from mrinimitable import safe_decode
from mrinimitable.core.doctype.communication.communication import Communication
from mrinimitable.email.doctype.email_queue.email_queue import QueueBuilder, SendMailContext
from mrinimitable.email.email_body import (
	get_email,
	get_header,
	inline_style_in_html,
	replace_filename_with_cid,
)
from mrinimitable.email.receive import Email, InboundMail
from mrinimitable.tests import IntegrationTestCase


class TestEmailBody(IntegrationTestCase):
	def setUp(self):
		email_html = """
<div>
	<h3>Hey John Doe!</h3>
	<p>This is embedded image you asked for</p>
	<img embed="assets/mrinimitable/images/mrinimitable-favicon.svg" />
</div>
"""
		email_text = """
Hey John Doe!
This is the text version of this email
"""

		img_path = os.path.abspath("assets/mrinimitable/images/mrinimitable-favicon.svg")
		with open(img_path, "rb") as f:
			img_content = f.read()
			img_base64 = base64.b64encode(img_content).decode()

		# email body keeps 76 characters on one line
		self.img_base64 = fixed_column_width(img_base64, 76)

		self.email_string = (
			get_email(
				recipients=["test@example.com"],
				sender="me@example.com",
				subject="Test Subject",
				content=email_html,
				text_content=email_text,
			)
			.as_string()
			.replace("\r\n", "\n")
		)

	def test_prepare_message_returns_already_encoded_string(self):
		uni_chr1 = chr(40960)
		uni_chr2 = chr(1972)

		QueueBuilder(
			recipients=["test@example.com"],
			sender="me@example.com",
			subject="Test Subject",
			message=f"<h1>{uni_chr1}abcd{uni_chr2}</h1>",
			text_content="whatever",
		).process()
		queue_doc = mrinimitable.get_last_doc("Email Queue")
		mail_ctx = SendMailContext(queue_doc=queue_doc)
		result = mail_ctx.build_message(recipient_email="test@test.com")
		self.assertTrue(b"<h1>=EA=80=80abcd=DE=B4</h1>" in result)

	def test_prepare_message_returns_cr_lf(self):
		QueueBuilder(
			recipients=["test@example.com"],
			sender="me@example.com",
			subject="Test Subject",
			message="<h1>\n this is a test of newlines\n" + "</h1>",
			text_content="whatever",
		).process()
		queue_doc = mrinimitable.get_last_doc("Email Queue")
		mail_ctx = SendMailContext(queue_doc=queue_doc)
		result = safe_decode(mail_ctx.build_message(recipient_email="test@test.com"))

		self.assertTrue(result.count("\n") == result.count("\r"))

	def test_image(self):
		img_signature = """
Content-Type: image/svg+xml
MIME-Version: 1.0
Content-Transfer-Encoding: base64
Content-Disposition: inline; filename="mrinimitable-favicon.svg"
"""
		self.assertTrue(img_signature in self.email_string)
		self.assertTrue(self.img_base64 in self.email_string)

	def test_text_content(self):
		text_content = """
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable


Hey John Doe!
This is the text version of this email
"""
		self.assertTrue(text_content in self.email_string)

	def test_email_content(self):
		html_head = """
Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.=
w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns=3D"http://www.w3.org/1999/xhtml">
"""

		html = """<h3>Hey John Doe!</h3>"""

		self.assertTrue(html_head in self.email_string)
		self.assertTrue(html in self.email_string)

	def test_replace_filename_with_cid(self):
		original_message = """
			<div>
				<img embed="assets/mrinimitable/images/mrinimitable-favicon.svg" alt="test" />
				<img embed="notexists.jpg" />
			</div>
		"""
		message, inline_images = replace_filename_with_cid(original_message)

		processed_message = """
			<div>
				<img src="cid:{}" alt="test" />
				<img  />
			</div>
		""".format(inline_images[0].get("content_id"))
		self.assertEqual(message, processed_message)

	def test_inline_styling(self):
		html = """
<h3>Hi John</h3>
<p>This is a test email</p>
"""
		transformed_html = """
<h3>Hi John</h3>
<p style="margin:1em 0 !important">This is a test email</p>
"""
		self.assertTrue(transformed_html in inline_style_in_html(html))

	def test_email_header(self):
		email_html = """
<h3>Hey John Doe!</h3>
<p>This is embedded image you asked for</p>
"""
		email_string = get_email(
			recipients=["test@example.com"],
			sender="me@example.com",
			subject="Test Subject\u2028, with line break, \nand Line feed \rand carriage return.",
			content=email_html,
			header=["Email Title", "green"],
		).as_string()
		# REDESIGN-TODO: Add style for indicators in email
		self.assertTrue("""<span class=3D"indicator indicator-green"></span>""" in email_string)
		self.assertTrue("<span>Email Title</span>" in email_string)
		self.assertIn(
			"Subject: Test Subject, with line break, and Line feed and carriage return.", email_string
		)

	def test_get_email_header(self):
		html = get_header(["This is test", "orange"])
		self.assertTrue('<span class="indicator indicator-orange"></span>' in html)
		self.assertTrue("<span>This is test</span>" in html)

		html = get_header(["This is another test"])
		self.assertTrue("<span>This is another test</span>" in html)

		html = get_header("This is string")
		self.assertTrue("<span>This is string</span>" in html)

	def test_8bit_utf_8_decoding(self):
		text_content_bytes = b"\xed\x95\x9c\xea\xb8\x80\xe1\xa5\xa1\xe2\x95\xa5\xe0\xba\xaa\xe0\xa4\x8f"
		text_content = text_content_bytes.decode("utf-8")

		content_bytes = (
			b"""MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Disposition: inline
Content-Transfer-Encoding: 8bit
From: test1_@okayblue.com
Reply-To: test2_@okayblue.com
"""
			+ text_content_bytes
		)

		mail = Email(content_bytes)
		self.assertEqual(mail.text_content, text_content)

	def test_poorly_encoded_messages(self):
		mail = Email.decode_email(
			"=?iso-2022-jp?B?VEFLQVlBTUEgS2FvcnUgWxskQnxiOzMbKEIgGyRCNzAbKEJd?=\n\t<user@example.com>"
		)
		self.assertIn("user@example.com", mail)

	def test_poorly_encoded_messages2(self):
		mail = Email.decode_email(" =?UTF-8?B?X\xe0\xe0Y?=  <xy@example.com>")
		self.assertIn("xy@example.com", mail)

	def test_quotes_in_email_sender(self):
		content_bytes = rb"""MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Disposition: inline
Content-Transfer-Encoding: 8bit
To: "\"fail@example.com\" via ABC"  <success@example.com>
From: "\"fail@example.com\" via DEF"  <success@example.com>
Reply-To: "\"fail@example.com\" via GHI"  <success@example.com>
CC: "\"fail@example.com\" via JKL"  <success@example.com>
"""

		mail = Email(content_bytes)
		self.assertEqual(mail.from_email, "success@example.com")

		self.assertEqual(mail.from_real_name, "failexamplecom via DEF")
		# https://github.com/mrinimitable/mrinimitable/pull/3371
		# self.assertEqual(mail.from_real_name, '"fail@example.com" via DEF')

		email_account = mrinimitable._dict({"email_id": "receive@example.com"})
		mail = InboundMail(content_bytes, email_account)
		communication: Communication = mail.process()  # type: ignore
		self.assertEqual(communication.sender_full_name, "failexamplecom via DEF")

	def test_quotes_in_email_recipients(self):
		content_bytes = rb"""MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Disposition: inline
Content-Transfer-Encoding: 8bit
From: "=?utf-8?Q?=F0=9F=98=83?="
	=?utf-8?Q?=3Ctest=40ex?= =?utf-8?Q?ample=2Eco?= =?utf-8?Q?m=3E?=
To: =?iso-8859-1?Q?X=E9Y=40example=2Ecom?= <xy@example.com>, "fail@example.com" <success@example.com>
"""

		# https://ldu2.github.io/rfc2047/
		email_account = mrinimitable._dict({"email_id": "receive@example.com"})
		mail = InboundMail(content_bytes, email_account)
		communication: Communication = mail.process()  # type: ignore
		self.assertEqual(communication.sender_mailid, "test@example.com")
		# self.assertEqual(communication.sender_full_name, "😃")
		# # TODO: Fix get_name_from_email_string to accept non-ASCII chars
		self.assertEqual(
			communication.recipients,
			'XéY@example.com <xy@example.com>, "fail@example.com" <success@example.com>',
		)
		mrinimitable.db.rollback()


def fixed_column_width(string, chunk_size):
	parts = [string[0 + i : chunk_size + i] for i in range(0, len(string), chunk_size)]
	return "\n".join(parts)
