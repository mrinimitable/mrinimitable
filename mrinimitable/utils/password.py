# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext
from pypika.terms import Values

import mrinimitable
from mrinimitable import _
from mrinimitable.query_builder import Table
from mrinimitable.utils import cstr, encode

Auth = Table("__Auth")

passlibctx = CryptContext(
	schemes=[
		"pbkdf2_sha256",
		"argon2",
	],
)


def get_decrypted_password(doctype, name, fieldname="password", raise_exception=True):
	result = (
		mrinimitable.qb.from_(Auth)
		.select(Auth.password)
		.where(
			(Auth.doctype == doctype)
			& (Auth.name == name)
			& (Auth.fieldname == fieldname)
			& (Auth.encrypted == 1)
		)
		.limit(1)
	).run()

	if result and result[0][0]:
		try:
			return decrypt(result[0][0], key=f"{doctype}.{name}.{fieldname}")
		except mrinimitable.ValidationError as e:
			if raise_exception:
				raise e

			return None

	if raise_exception:
		mrinimitable.throw(
			_("Password not found for {0} {1} {2}").format(doctype, name, fieldname),
		)


def set_encrypted_password(doctype, name, pwd, fieldname="password"):
	query = mrinimitable.qb.into(Auth).columns(
		Auth.doctype, Auth.name, Auth.fieldname, Auth.password, Auth.encrypted
	)

	# TODO: Simplify this via aliasing methods in `mrinimitable.qb`
	if mrinimitable.db.db_type == "mariadb":
		query = query.insert(doctype, name, fieldname, encrypt(pwd), 1).on_duplicate_key_update(
			Auth.password, Values(Auth.password)
		)
	elif mrinimitable.db.db_type == "sqlite":
		query = query.insert_or_replace(doctype, name, fieldname, encrypt(pwd), 1)
	elif mrinimitable.db.db_type == "postgres":
		query = (
			query.insert(doctype, name, fieldname, encrypt(pwd), 1)
			.on_conflict(Auth.doctype, Auth.name, Auth.fieldname)
			.do_update(Auth.password)
		)

	try:
		query.run()

	except mrinimitable.db.DataError as e:
		if mrinimitable.db.is_data_too_long(e):
			mrinimitable.throw(_("Most probably your password is too long."), exc=e)
		raise e


def remove_encrypted_password(doctype, name, fieldname="password"):
	mrinimitable.db.delete("__Auth", {"doctype": doctype, "name": name, "fieldname": fieldname})


def check_password(user, pwd, doctype="User", fieldname="password", delete_tracker_cache=True):
	"""Checks if user and password are correct, else raises mrinimitable.AuthenticationError"""

	result = (
		mrinimitable.qb.from_(Auth)
		.select(Auth.name, Auth.password)
		.where(
			(Auth.doctype == doctype)
			& (Auth.name == user)
			& (Auth.fieldname == fieldname)
			& (Auth.encrypted == 0)
		)
		.limit(1)
		.run(as_dict=True)
	)

	if not result or not passlibctx.verify(pwd, result[0].password):
		raise mrinimitable.AuthenticationError(_("Incorrect User or Password"))

	# lettercase agnostic
	user = result[0].name

	# TODO: This need to be deleted after checking side effects of it.
	# We have a `LoginAttemptTracker` that can take care of tracking related cache.
	if delete_tracker_cache:
		delete_login_failed_cache(user)

	if passlibctx.needs_update(result[0].password):
		update_password(user, pwd, doctype, fieldname)

	return user


def delete_login_failed_cache(user):
	mrinimitable.cache.hdel("login_failed_count", user)


def update_password(user, pwd, doctype="User", fieldname="password", logout_all_sessions=False):
	"""
	Update the password for the User

	:param user: username
	:param pwd: new password
	:param doctype: doctype name (for encryption)
	:param fieldname: fieldname (in given doctype) (for encryption)
	:param logout_all_session: delete all other session
	"""
	hashPwd = passlibctx.hash(pwd)

	query = mrinimitable.qb.into(Auth).columns(
		Auth.doctype, Auth.name, Auth.fieldname, Auth.password, Auth.encrypted
	)

	# TODO: Simplify this via aliasing methods in `mrinimitable.qb`
	if mrinimitable.db.db_type == "mariadb":
		query = (
			query.insert(doctype, user, fieldname, hashPwd, 0)
			.on_duplicate_key_update(Auth.password, hashPwd)
			.on_duplicate_key_update(Auth.encrypted, 0)
		)
	elif mrinimitable.db.db_type == "sqlite":
		query = query.insert_or_replace(doctype, user, fieldname, hashPwd, 0)

	elif mrinimitable.db.db_type == "postgres":
		query = (
			query.insert(doctype, user, fieldname, hashPwd, 0)
			.on_conflict(Auth.doctype, Auth.name, Auth.fieldname)
			.do_update(Auth.password, hashPwd)
			.do_update(Auth.encrypted, 0)
		)

	query.run()

	# clear all the sessions except current
	if logout_all_sessions:
		from mrinimitable.sessions import clear_sessions

		clear_sessions(user=user, keep_current=True, force=True)


def delete_all_passwords_for(doctype, name):
	try:
		mrinimitable.db.delete("__Auth", {"doctype": doctype, "name": name})
	except Exception as e:
		if not mrinimitable.db.is_missing_column(e):
			raise


def rename_password(doctype, old_name, new_name):
	# NOTE: fieldname is not considered, since the document is renamed
	mrinimitable.qb.update(Auth).set(Auth.name, new_name).where(
		(Auth.doctype == doctype) & (Auth.name == old_name)
	).run()


def rename_password_field(doctype, old_fieldname, new_fieldname):
	mrinimitable.qb.update(Auth).set(Auth.fieldname, new_fieldname).where(
		(Auth.doctype == doctype) & (Auth.fieldname == old_fieldname)
	).run()


def create_auth_table():
	# same as Framework.sql
	mrinimitable.db.create_auth_table()


def encrypt(txt, encryption_key=None):
	# Only use Fernet.generate_key().decode() to enter encyption_key value

	try:
		cipher_suite = Fernet(encode(encryption_key or get_encryption_key()))
	except Exception:
		# encryption_key is not in 32 url-safe base64-encoded format
		mrinimitable.throw(_("Encryption key is in invalid format!"))

	return cstr(cipher_suite.encrypt(encode(txt)))


def decrypt(txt, encryption_key=None, key: str | None = None):
	# Only use encryption_key value generated with Fernet.generate_key().decode()

	try:
		cipher_suite = Fernet(encode(encryption_key or get_encryption_key()))
		return cstr(cipher_suite.decrypt(encode(txt)))
	except InvalidToken:
		# encryption_key in site_config is changed and not valid
		mrinimitable.throw(
			(_("Failed to decrypt key {0}").format(key) + "<br><br>" if key else "")
			+ _("Encryption key is invalid! Please check site_config.json")
			+ "<br><br>"
			+ _(
				"If you have recently restored the site, you may need to copy the site_config.json containing the original encryption key."
			)
			+ "<br><br>"
			+ _(
				"Please visit https://mrinimitablecloud.com/docs/sites/migrate-an-existing-site#encryption-key for more information."
			),
		)


def get_encryption_key():
	if "encryption_key" not in mrinimitable.local.conf:
		from mrinimitable.installer import update_site_config

		encryption_key = Fernet.generate_key().decode()
		update_site_config("encryption_key", encryption_key)
		mrinimitable.local.conf.encryption_key = encryption_key

	return mrinimitable.local.conf.encryption_key


def get_password_reset_limit():
	return mrinimitable.get_system_settings("password_reset_limit") or 3
