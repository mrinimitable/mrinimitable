import mrinimitable
from mrinimitable.email.utils import get_port


def execute():
	"""
	1. Set default incoming email port in email domain
	2. Set default incoming email port in all email account (for those account where domain is missing)
	"""
	mrinimitable.reload_doc("email", "doctype", "email_domain", force=True)
	mrinimitable.reload_doc("email", "doctype", "email_account", force=True)

	setup_incoming_email_port_in_email_domains()
	setup_incoming_email_port_in_email_accounts()


def setup_incoming_email_port_in_email_domains():
	email_domains = mrinimitable.get_all("Email Domain", ["incoming_port", "use_imap", "use_ssl", "name"])
	for domain in email_domains:
		if not domain.incoming_port:
			incoming_port = get_port(domain)
			mrinimitable.db.set_value(
				"Email Domain", domain.name, "incoming_port", incoming_port, update_modified=False
			)

			# update incoming email port in all
			mrinimitable.db.sql(
				"""update `tabEmail Account` set incoming_port=%s where domain = %s""",
				(domain.incoming_port, domain.name),
			)


def setup_incoming_email_port_in_email_accounts():
	email_accounts = mrinimitable.get_all(
		"Email Account", ["incoming_port", "use_imap", "use_ssl", "name", "enable_incoming"]
	)

	for account in email_accounts:
		if account.enable_incoming and not account.incoming_port:
			incoming_port = get_port(account)
			mrinimitable.db.set_value(
				"Email Account", account.name, "incoming_port", incoming_port, update_modified=False
			)
