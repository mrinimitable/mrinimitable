# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import hashlib
import itertools
import json
import time
import warnings
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from functools import wraps
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, Optional, TypeAlias, Union, overload

from typing_extensions import Self, override
from werkzeug.exceptions import NotFound

import mrinimitable
from mrinimitable import _, is_whitelisted, msgprint
from mrinimitable.core.doctype.file.utils import relink_mismatched_files
from mrinimitable.core.doctype.server_script.server_script_utils import run_server_script_for_doc_event
from mrinimitable.database.utils import commit_after_response
from mrinimitable.desk.form.document_follow import follow_document
from mrinimitable.integrations.doctype.webhook import run_webhooks
from mrinimitable.model import optional_fields, table_fields
from mrinimitable.model.base_document import BaseDocument, D, get_controller
from mrinimitable.model.docstatus import DocStatus
from mrinimitable.model.naming import set_new_name, validate_name
from mrinimitable.model.utils import is_virtual_doctype, simple_singledispatch
from mrinimitable.model.workflow import set_workflow_state_on_action, validate_workflow
from mrinimitable.types import DF
from mrinimitable.types.filter import FilterSignature
from mrinimitable.utils import compare, cstr, date_diff, file_lock, flt, get_table_name, now
from mrinimitable.utils.data import get_absolute_url, get_datetime, get_timedelta, getdate
from mrinimitable.utils.global_search import update_global_search

if TYPE_CHECKING:
	from typing_extensions import Self

	from mrinimitable.core.doctype.docfield.docfield import DocField


DOCUMENT_LOCK_EXPIRY = 3 * 60 * 60  # All locks expire in 3 hours automatically
DOCUMENT_LOCK_SOFT_EXPIRY = 30 * 60  # Let users force-unlock after 30 minutes


_SingleDocument: TypeAlias = "Document"
_NewDocument: TypeAlias = "Document"


@overload
def get_doc(document: "Document", /) -> "Document":
	pass


@overload
def get_doc(doctype: str, /) -> _SingleDocument:
	"""Retrieve Single DocType from DB, doctype must be positional argument."""
	pass


@overload
def get_doc(doctype: str, name: str, /, *, for_update: bool | None = None) -> "Document":
	"""Retrieve DocType from DB, doctype and name must be positional argument."""
	pass


@overload
def get_doc(**kwargs: dict) -> "_NewDocument":
	"""Initialize document from kwargs.
	Not recommended. Use `mrinimitable.new_doc` instead."""
	pass


@overload
def get_doc(documentdict: dict) -> "_NewDocument":
	"""Create document from dict.
	Not recommended. Use `mrinimitable.new_doc` instead."""
	pass


@simple_singledispatch
def get_doc(*args, **kwargs) -> "Document":
	"""Return a `mrinimitable.model.Document` object.

	:param arg1: Document dict or DocType name.
	:param arg2: [optional] document name.
	:param for_update: [optional] select document for update.

	There are multiple ways to call `get_doc`

	        # will fetch the latest user object (with child table) from the database
	        user = get_doc("User", "test@example.com")

	        # create a new object
	        user = get_doc({
	                "doctype":"User"
	                "email_id": "test@example.com",
	                "roles: [
	                        {"role": "System Manager"}
	                ]
	        })

	        # create new object with keyword arguments
	        user = get_doc(doctype='User', email_id='test@example.com')

	        # select a document for update
	        user = get_doc("User", "test@example.com", for_update=True)
	"""
	if not args and kwargs:
		return get_doc_from_dict(kwargs)
	else:
		raise ValueError("First non keyword argument must be a string or dict")


@get_doc.register(BaseDocument)
def _basedoc(doc: BaseDocument, *args, **kwargs) -> "Document":
	return doc


@get_doc.register(str)
def get_doc_str(doctype: str, name: str | None = None, **kwargs) -> "Document":
	# if no name: it's a single
	controller = get_controller(doctype)
	if controller:
		return controller(doctype, name, **kwargs)

	raise ImportError(doctype)


@get_doc.register(MappingProxyType)  # global test record
def get_doc_from_mapping_proxy(data: MappingProxyType, **kwargs) -> "Document":
	return get_doc_from_dict(dict(data), **kwargs)


@get_doc.register(dict)
def get_doc_from_dict(data: dict[str, Any], **kwargs) -> "Document":
	if "doctype" not in data:
		raise ValueError('"doctype" is a required key')
	controller = get_controller(data["doctype"])
	if controller:
		return controller(**data)
	raise ImportError(data["doctype"])


def get_lazy_doc(doctype: str, name: str, *, for_update=None) -> "Document":
	if doctype == "DocType":
		warnings.warn("DocType doesn't support lazy loading", stacklevel=1)
		return get_doc(doctype, name)

	controller = get_lazy_controller(doctype)
	if controller:
		return controller(doctype, name, for_update=for_update)
	raise ImportError(doctype)


class Document(BaseDocument):
	"""All controllers inherit from `Document`."""

	doctype: DF.Data
	name: DF.Data | None
	flags: mrinimitable._dict[str, Any]
	owner: DF.Link
	creation: DF.Datetime
	modified: DF.Datetime
	modified_by: DF.Link
	idx: DF.Int

	def __init__(self, *args, **kwargs):
		"""Constructor.

		:param arg1: DocType name as string, document **dict**, or DocRef object
		:param arg2: Document name, if `arg1` is DocType name.

		If DocType name and document name are passed, the object will load
		all values (including child documents) from the database.
		"""
		self.doctype = None
		self.name = None
		self.flags = mrinimitable._dict()
		if args:
			first_arg = args[0]
			if isinstance(first_arg, str):
				self.doctype = first_arg
				self.name = first_arg if len(args) == 1 else args[1]

				# for_update is set in flags to avoid changing load_from_db signature
				# since it is used in virtual doctypes and inherited in child classes
				self.flags.for_update = kwargs.get("for_update", False)
				self.load_from_db()
				return

			if isinstance(first_arg, dict):
				kwargs = first_arg

		if kwargs:
			super().__init__(kwargs)
			self.init_child_tables()
			self.init_valid_columns()
			return

		raise ValueError("Illegal arguments")

	@property
	def is_locked(self):
		signature = self.get_signature()
		if not file_lock.lock_exists(signature):
			return False

		if file_lock.lock_age(signature) > DOCUMENT_LOCK_EXPIRY:
			return False

		return True

	def load_from_db(self) -> "Self":
		"""Load document and children from database and create properties
		from fields"""

		is_doctype = self.doctype == "DocType"

		self.flags.ignore_children = True
		if not is_doctype and self.meta.issingle:
			single_doc = mrinimitable.db.get_singles_dict(self.doctype, for_update=self.flags.for_update)
			if not single_doc:
				single_doc = mrinimitable.new_doc(self.doctype, as_dict=True)
				single_doc["name"] = self.doctype
				del single_doc["__islocal"]

			super().__init__(single_doc)
			self.init_valid_columns()
			self._fix_numeric_types()

		else:
			if not is_doctype and isinstance(self.name, str | int):
				for_update = ""
				if self.flags.for_update and mrinimitable.db.db_type != "sqlite":
					for_update = "FOR UPDATE"
				# Fast path - use raw SQL to avoid QB/ORM overheads.
				d = mrinimitable.db.sql(
					"SELECT * FROM {table_name} WHERE `name` = %s {for_update}".format(
						table_name=get_table_name(self.doctype, wrap_in_backticks=True),
						for_update=for_update,
					),
					(self.name),
					as_dict=True,
				)
				d = d[0] if d else d
			else:
				d = mrinimitable.db.get_value(
					doctype=self.doctype,
					filters=self.name,
					fieldname="*",
					for_update=self.flags.for_update,
					as_dict=True,
				)

			if not d:
				mrinimitable.throw(
					_("{0} {1} not found").format(_(self.doctype), self.name),
					mrinimitable.DoesNotExistError(doctype=self.doctype),
				)

			super().__init__(d)
		self.flags.pop("ignore_children", None)

		self.load_children_from_db()

		# sometimes __setup__ can depend on child values, hence calling again at the end
		if hasattr(self, "__setup__"):
			self.__setup__()

		return self

	def load_children_from_db(self):
		is_doctype = self.doctype == "DocType"

		for fieldname, child_doctype in self._table_fieldnames.items():
			# Make sure not to query the DB for a child table, if it is a virtual one.
			if not is_doctype and is_virtual_doctype(child_doctype):
				self.set(fieldname, [])
				continue

			if is_doctype:
				# This special handling is required because of bootstrapping code that doesn't
				# handle failures correctly.
				children = mrinimitable.db.get_values(
					child_doctype,
					{"parent": self.name, "parenttype": self.doctype, "parentfield": fieldname},
					"*",
					as_dict=True,
					order_by="idx asc",
					for_update=self.flags.for_update,
				)
			else:
				children = self._load_child_table_from_db(fieldname, child_doctype)

			if children is None:
				children = []

			self.set(fieldname, children)

		return self

	def _load_child_table_from_db(self, fieldname, child_doctype):
		for_update = ""
		if self.flags.for_update and mrinimitable.db.db_type != "sqlite":
			for_update = "FOR UPDATE"
		# Fast pass for all other doctypes - using raw SQL
		return mrinimitable.db.sql(
			"""SELECT * FROM {table_name}
			WHERE `parent`= %(parent)s
				AND `parenttype`= %(parenttype)s
				AND `parentfield`= %(parentfield)s
			ORDER BY `idx` ASC {for_update}""".format(
				table_name=get_table_name(child_doctype, wrap_in_backticks=True),
				for_update=for_update,
			),
			{"parent": str(self.name), "parenttype": self.doctype, "parentfield": fieldname},
			as_dict=True,
		)

	def reload(self) -> "Self":
		"""Reload document from database"""
		return self.load_from_db()

	def get_latest(self):
		if not getattr(self, "_doc_before_save", None):
			self.load_doc_before_save()

		return self._doc_before_save

	def check_permission(self, permtype="read", permlevel=None):
		"""Raise `mrinimitable.PermissionError` if not permitted"""
		if not self.has_permission(permtype):
			self._handle_permission_failure(permtype)

	def has_permission(self, permtype="read", *, debug=False, user=None) -> bool:
		"""
		Call `mrinimitable.permissions.has_permission` if `ignore_permissions` flag isn't truthy

		:param permtype: `read`, `write`, `submit`, `cancel`, `delete`, etc.
		"""

		if self.flags.ignore_permissions:
			return True

		import mrinimitable.permissions

		return mrinimitable.permissions.has_permission(self.doctype, permtype, self, debug=debug, user=user)

	def _handle_permission_failure(self, perm_type):
		from mrinimitable.permissions import check_doctype_permission

		check_doctype_permission(self.doctype, perm_type)
		self.raise_no_permission_to(perm_type)

	def raise_no_permission_to(self, perm_type):
		"""Raise `mrinimitable.PermissionError`."""
		mrinimitable.flags.error_message = _(
			"You need the '{0}' permission on {1} {2} to perform this action."
		).format(
			_(perm_type),
			mrinimitable.bold(_(self.doctype)),
			self.name or "",
		)
		raise mrinimitable.PermissionError

	def insert(
		self,
		ignore_permissions=None,
		ignore_links=None,
		ignore_if_duplicate=False,
		ignore_mandatory=None,
		set_name=None,
		set_child_names=True,
	) -> "Self":
		"""Insert the document in the database (as a new document).
		This will check for user permissions and execute `before_insert`,
		`validate`, `on_update`, `after_insert` methods if they are written.

		:param ignore_permissions: Do not check permissions if True.
		:param ignore_links: Do not check validity of links if True.
		:param ignore_if_duplicate: Do not raise error if a duplicate entry exists.
		:param ignore_mandatory: Do not check missing mandatory fields if True.
		:param set_name: Name to set for the document, if valid.
		:param set_child_names: Whether to set names for the child documents.
		"""
		if self.flags.in_print:
			return self

		self.flags.notifications_executed = []

		if ignore_permissions is not None:
			self.flags.ignore_permissions = ignore_permissions

		if ignore_links is not None:
			self.flags.ignore_links = ignore_links

		if ignore_mandatory is not None:
			self.flags.ignore_mandatory = ignore_mandatory

		self.set("__islocal", True)

		self._set_defaults()
		self.set_user_and_timestamp()
		self.set_docstatus()
		self.check_if_latest()
		self._validate_links()
		self.check_permission("create")
		self.run_method("before_insert")
		self.set_new_name(set_name=set_name, set_child_names=set_child_names)
		self.set_parent_in_children()
		self.validate_higher_perm_levels()

		self.flags.in_insert = True
		self.run_before_save_methods()
		self._validate()
		self.set_docstatus()
		self.flags.in_insert = False

		# run validate, on update etc.

		# parent
		if getattr(self.meta, "issingle", 0):
			self.update_single(self.get_valid_dict())
		else:
			self.db_insert(ignore_if_duplicate=ignore_if_duplicate)

		# children
		if not getattr(self.meta, "is_virtual", False):
			for d in self.get_all_children():
				d.db_insert()

		self.run_method("after_insert")
		self.flags.in_insert = True

		if self.get("amended_from"):
			self.validate_amended_from()
			self.copy_attachments_from_amended_from()

		relink_mismatched_files(self)
		self.run_post_save_methods()
		self.flags.in_insert = False

		# delete __islocal
		if hasattr(self, "__islocal"):
			delattr(self, "__islocal")

		# clear unsaved flag
		if hasattr(self, "__unsaved"):
			delattr(self, "__unsaved")

		if not (mrinimitable.flags.in_migrate or mrinimitable.local.flags.in_install or mrinimitable.flags.in_setup_wizard):
			if mrinimitable.get_cached_value("User", mrinimitable.session.user, "follow_created_documents"):
				follow_document(self.doctype, self.name, mrinimitable.session.user)
		return self

	def check_if_locked(self):
		if not self.creation or not self.is_locked:
			return

		# Allow unlocking if created more than 60 minutes ago
		primary_action = None
		if file_lock.lock_age(self.get_signature()) > DOCUMENT_LOCK_SOFT_EXPIRY:
			primary_action = {
				"label": "Force Unlock",
				"server_action": "mrinimitable.model.document.unlock_document",
				"hide_on_success": True,
				"args": {
					"doctype": self.doctype,
					"name": self.name,
				},
			}

		mrinimitable.throw(
			_(
				"This document is currently locked and queued for execution. Please try again after some time."
			),
			title=_("Document Queued"),
			primary_action=primary_action,
			exc=mrinimitable.DocumentLockedError,
		)

	def save(self, *args, **kwargs) -> "Self":
		"""Wrapper for _save"""
		return self._save(*args, **kwargs)

	def _save(self, ignore_permissions=None, ignore_version=None) -> "Self":
		"""Save the current document in the database in the **DocType**'s table or
		`tabSingles` (for single types).

		This will check for user permissions and execute
		`validate` before updating, `on_update` after updating triggers.

		:param ignore_permissions: Do not check permissions if True.
		:param ignore_version: Do not save version if True."""
		if self.flags.in_print:
			return self

		self.flags.notifications_executed = []

		if ignore_permissions is not None:
			self.flags.ignore_permissions = ignore_permissions

		self.flags.ignore_version = mrinimitable.in_test if ignore_version is None else ignore_version

		if self.get("__islocal") or not self.get("name"):
			return self.insert()

		self.check_if_locked()
		self._set_defaults()
		self.check_permission("write", "save")

		self.set_user_and_timestamp()
		self.set_docstatus()
		self.check_if_latest()
		self.set_parent_in_children()
		self.set_name_in_children()

		self.validate_higher_perm_levels()
		self._validate_links()
		self.run_before_save_methods()

		if self._action != "cancel":
			self._validate()

		if self._action == "update_after_submit":
			self.validate_update_after_submit()

		self.set_docstatus()

		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_update()

		self.update_children()
		self.run_post_save_methods()

		# clear unsaved flag
		if hasattr(self, "__unsaved"):
			delattr(self, "__unsaved")

		return self

	def validate_amended_from(self):
		if mrinimitable.db.get_value(self.doctype, self.get("amended_from"), "docstatus") != 2:
			message = _(
				"{0} cannot be amended because it is not cancelled. Please cancel the document before creating an amendment."
			).format(mrinimitable.utils.get_link_to_form(self.doctype, self.get("amended_from")))
			mrinimitable.throw(message, title=_("Amendment Not Allowed"))

	def copy_attachments_from_amended_from(self):
		"""Copy attachments from `amended_from`"""
		from mrinimitable.desk.form.load import get_attachments

		# loop through attachments
		for attach_item in get_attachments(self.doctype, self.amended_from):
			# save attachments to new doc
			_file = mrinimitable.get_doc(
				{
					"doctype": "File",
					"file_url": attach_item.file_url,
					"file_name": attach_item.file_name,
					"attached_to_name": self.name,
					"attached_to_doctype": self.doctype,
					"folder": "Home/Attachments",
					"is_private": attach_item.is_private,
				}
			)
			_file.save()

	def update_children(self):
		"""update child tables"""
		if getattr(self.meta, "is_virtual", False):
			# Virtual doctypes manage their own children
			return

		for df in self.meta.get_table_fields():
			self.update_child_table(df.fieldname, df)

	def update_child_table(self, fieldname: str, df: Optional["DocField"] = None):
		"""sync child table for given fieldname"""
		df: DocField = df or self.meta.get_field(fieldname)
		all_rows = self.get(df.fieldname)

		# delete rows that do not match the ones in the document
		# if the doctype isn't in ignore_children_type flag and isn't virtual
		if not (
			df.options in (self.flags.ignore_children_type or ())
			or mrinimitable.get_meta(df.options).is_virtual == 1
		):
			existing_row_names = [row.name for row in all_rows if row.name and not row.is_new()]

			tbl = mrinimitable.qb.DocType(df.options)
			qry = (
				mrinimitable.qb.from_(tbl)
				.where(tbl.parent == str(self.name))
				.where(tbl.parenttype == self.doctype)
				.where(tbl.parentfield == fieldname)
				.delete()
			)

			if existing_row_names:
				qry = qry.where(tbl.name.notin(existing_row_names))

			qry.run()

		# update / insert
		for d in all_rows:
			d: Document
			d.db_update()

	def get_doc_before_save(self) -> "Self":
		return getattr(self, "_doc_before_save", None)

	def has_value_changed(self, fieldname):
		"""Return True if value has changed before and after saving."""
		from datetime import date, datetime, timedelta

		previous = self.get_doc_before_save()

		if not previous:
			return True

		previous_value = previous.get(fieldname)
		current_value = self.get(fieldname)

		if isinstance(previous_value, datetime):
			current_value = get_datetime(current_value)
		elif isinstance(previous_value, date):
			current_value = getdate(current_value)
		elif isinstance(previous_value, timedelta):
			current_value = get_timedelta(current_value)

		return previous_value != current_value

	def get_value_before_save(self, fieldname):
		"""Returns value of a field before saving

		Note: This function only works in save context like doc.save, doc.submit.
		"""
		previous = self.get_doc_before_save()
		if not previous:
			return
		return previous.get(fieldname)

	def set_new_name(self, force=False, set_name=None, set_child_names=True):
		"""Calls `mrinimitable.naming.set_new_name` for parent and child docs."""

		if self.flags.name_set and not force:
			return

		autoname = self.meta.autoname or ""

		# If autoname has set as Prompt (name)
		if self.get("__newname") and autoname.lower() == "prompt":
			self.name = validate_name(self.doctype, self.get("__newname"))
			self.flags.name_set = True
			return

		if set_name:
			self.name = validate_name(self.doctype, set_name)
		else:
			set_new_name(self)

		if set_child_names:
			# set name for children
			for d in self.get_all_children():
				set_new_name(d)

		self.flags.name_set = True

	def get_title(self):
		"""Get the document title based on title_field or `title` or `name`"""
		return self.get(self.meta.get_title_field()) or ""

	def set_title_field(self):
		"""Set title field based on template"""

		def get_values():
			values = self.as_dict()
			# format values
			for key, value in values.items():
				if value is None:
					values[key] = ""
			return values

		if self.meta.get("title_field") == "title":
			df = self.meta.get_field(self.meta.title_field)

			if df.options:
				self.set(df.fieldname, df.options.format(**get_values()))
			elif self.is_new() and not self.get(df.fieldname) and df.default:
				# set default title for new transactions (if default)
				self.set(df.fieldname, df.default.format(**get_values()))

	def update_single(self, d):
		"""Updates values for Single type Document in `tabSingles`."""
		mrinimitable.db.delete("Singles", {"doctype": self.doctype})
		for field, value in d.items():
			if field != "doctype":
				mrinimitable.db.sql(
					"""insert into `tabSingles` (doctype, field, value)
					values (%s, %s, %s)""",
					(self.doctype, field, value),
				)

		if self.doctype in mrinimitable.db.value_cache:
			mrinimitable.db.value_cache.pop(self.doctype, None)

	def set_user_and_timestamp(self):
		self._original_modified = self.modified
		self.modified = now()
		self.modified_by = mrinimitable.session.user

		# We'd probably want the creation and owner to be set via API
		# or Data import at some point, that'd have to be handled here
		if self.is_new() and not (
			mrinimitable.flags.in_install or mrinimitable.flags.in_patch or mrinimitable.flags.in_migrate
		):
			self.creation = self.modified
			self.owner = self.modified_by

		for d in self.get_all_children():
			d.modified = self.modified
			d.modified_by = self.modified_by
			if not d.owner:
				d.owner = self.owner
			if not d.creation:
				d.creation = self.creation

		mrinimitable.flags.currently_saving.append((self.doctype, self.name))

	def set_docstatus(self):
		# docstatus property automatically sets a docstatus if not set
		docstatus = self.docstatus

		for d in self.get_all_children():
			d.set("docstatus", docstatus)

	def _validate(self):
		self._validate_mandatory()
		self._validate_data_fields()
		self._validate_selects()
		self._validate_non_negative()
		self._validate_length()
		self._fix_rating_value()
		self._validate_code_fields()
		self._sync_autoname_field()
		self._extract_images_from_text_editor()
		self._sanitize_content()
		self._save_passwords()
		self.validate_workflow()

		for d in self.get_all_children():
			d._validate_data_fields()
			d._validate_selects()
			d._validate_non_negative()
			d._validate_length()
			d._fix_rating_value()
			d._validate_code_fields()
			d._sync_autoname_field()
			d._extract_images_from_text_editor()
			d._sanitize_content()
			d._save_passwords()
		if self.is_new():
			# don't set fields like _assign, _comments for new doc
			for fieldname in optional_fields:
				self.set(fieldname, None)
		else:
			self.validate_set_only_once()

	def _validate_non_negative(self):
		def get_msg(df):
			if self.get("parentfield"):
				return "{} {} #{}: {} {}".format(
					mrinimitable.bold(_(self.doctype)),
					_("Row"),
					self.idx,
					_("Value cannot be negative for"),
					mrinimitable.bold(_(df.label, context=df.parent)),
				)
			else:
				return _("Value cannot be negative for {0}: {1}").format(
					_(df.parent), mrinimitable.bold(_(df.label, context=df.parent))
				)

		for df in self.meta.get(
			"fields", {"non_negative": ("=", 1), "fieldtype": ("in", ["Int", "Float", "Currency"])}
		):
			if flt(self.get(df.fieldname)) < 0:
				msg = get_msg(df)
				mrinimitable.throw(msg, mrinimitable.NonNegativeError, title=_("Negative Value"))

	def _fix_rating_value(self):
		for field in self.meta.get("fields", {"fieldtype": "Rating"}):
			value = self.get(field.fieldname)
			if not isinstance(value, float):
				value = flt(value)

			# Make sure rating is between 0 and 1
			self.set(field.fieldname, max(0, min(value, 1)))

	def validate_workflow(self):
		"""Validate if the workflow transition is valid"""
		if mrinimitable.flags.in_install == "mrinimitable":
			return
		workflow = self.meta.get_workflow()
		if workflow:
			validate_workflow(self)
			if self._action != "save":
				set_workflow_state_on_action(self, workflow, self._action)

	def validate_set_only_once(self):
		"""Validate that fields are not changed if not in insert"""
		set_only_once_fields = self.meta.get_set_only_once_fields()

		if set_only_once_fields and self._doc_before_save:
			# document exists before saving
			for field in set_only_once_fields:
				fail = False
				value = self.get(field.fieldname)
				original_value = self._doc_before_save.get(field.fieldname)

				if field.fieldtype in table_fields:
					fail = not self.is_child_table_same(field.fieldname)
				elif field.fieldtype in ("Date", "Datetime", "Time"):
					fail = str(value) != str(original_value)
				else:
					fail = value != original_value

				if fail:
					mrinimitable.throw(
						_("Value cannot be changed for {0}").format(
							mrinimitable.bold(_(self.meta.get_label(field.fieldname)))
						),
						exc=mrinimitable.CannotChangeConstantError,
					)

		return False

	def is_child_table_same(self, fieldname):
		"""Validate child table is same as original table before saving"""
		value = self.get(fieldname)
		original_value = self._doc_before_save.get(fieldname)
		same = True

		if len(original_value) != len(value):
			same = False
		else:
			# check all child entries
			for i, d in enumerate(original_value):
				new_child = value[i].as_dict(convert_dates_to_str=True)
				original_child = d.as_dict(convert_dates_to_str=True)

				# all fields must be same other than modified and modified_by
				for key in ("modified", "modified_by", "creation"):
					del new_child[key]
					del original_child[key]

				if original_child != new_child:
					same = False
					break

		return same

	def apply_fieldlevel_read_permissions(self):
		"""Remove values the user is not allowed to read."""
		if mrinimitable.session.user == "Administrator":
			return

		all_fields = self.meta.fields.copy()
		for table_field in self.meta.get_table_fields():
			all_fields += mrinimitable.get_meta(table_field.options).fields or []

		if all(df.permlevel == 0 for df in all_fields):
			return

		has_access_to = self.get_permlevel_access("read")

		for df in self.meta.fields:
			if df.permlevel and hasattr(self, df.fieldname) and df.permlevel not in has_access_to:
				try:
					delattr(self, df.fieldname)
				except AttributeError:
					# hasattr might return True for class attribute which can't be delattr-ed.
					continue

		for table_field in self.meta.get_table_fields():
			for df in mrinimitable.get_meta(table_field.options).fields or []:
				if df.permlevel and df.permlevel not in has_access_to:
					for child in self.get(table_field.fieldname) or []:
						if hasattr(child, df.fieldname):
							delattr(child, df.fieldname)

	def validate_higher_perm_levels(self):
		"""If the user does not have permissions at permlevel > 0, then reset the values to original / default"""
		if self.flags.ignore_permissions or mrinimitable.flags.in_install:
			return

		if mrinimitable.session.user == "Administrator":
			return

		has_access_to = self.get_permlevel_access()
		high_permlevel_fields = self.meta.get_high_permlevel_fields()

		if high_permlevel_fields:
			self.reset_values_if_no_permlevel_access(has_access_to, high_permlevel_fields)

		# If new record then don't reset the values for child table
		if self.is_new():
			return

		# check for child tables
		for df in self.meta.get_table_fields():
			high_permlevel_fields = mrinimitable.get_meta(df.options).get_high_permlevel_fields()
			if high_permlevel_fields:
				for d in self.get(df.fieldname):
					d.reset_values_if_no_permlevel_access(has_access_to, high_permlevel_fields)

	def get_permlevel_access(self, permission_type="write"):
		allowed_permlevels = []
		roles = mrinimitable.get_roles()

		for perm in self.get_permissions():
			if perm.role in roles and perm.get(permission_type) and perm.permlevel not in allowed_permlevels:
				allowed_permlevels.append(perm.permlevel)

		return allowed_permlevels

	def has_permlevel_access_to(self, fieldname, df=None, permission_type="read"):
		if not df:
			df = self.meta.get_field(fieldname)

		return df.permlevel in self.get_permlevel_access(permission_type)

	def get_permissions(self):
		if self.meta.istable:
			# use parent permissions
			permissions = mrinimitable.get_meta(self.parenttype).permissions
		else:
			permissions = self.meta.permissions

		return permissions

	def _set_defaults(self):
		if mrinimitable.flags.in_import:
			return

		if self.is_new():
			new_doc = mrinimitable.new_doc(self.doctype, as_dict=True)
			self.update_if_missing(new_doc)

		# children
		for df in self.meta.get_table_fields():
			new_doc = mrinimitable.new_doc(df.options, parent_doc=self, parentfield=df.fieldname, as_dict=True)
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					if d.is_new():
						d.update_if_missing(new_doc)

	def check_if_latest(self):
		"""Checks if `modified` timestamp provided by document being updated is same as the
		`modified` timestamp in the database. If there is a different, the document has been
		updated in the database after the current copy was read. Will throw an error if
		timestamps don't match.

		Will also validate document transitions (Save > Submit > Cancel) calling
		`self.check_docstatus_transition`."""

		self.load_doc_before_save(raise_exception=True)

		if not hasattr(self, "_action"):
			self._action = "save"

		previous = self._doc_before_save
		# previous is None for new document insert
		if not previous and self._action != "discard":
			self.check_docstatus_transition(0)
			return

		if cstr(previous.modified) != cstr(self._original_modified):
			mrinimitable.msgprint(
				_(f"Error: {self.name} ({self.doctype}) has been modified after you have opened it")
				+ (f" ({previous.modified}, {self.modified}). ")
				+ _("Please refresh to get the latest document."),
				raise_exception=mrinimitable.TimestampMismatchError,
			)

		if not self.meta.issingle and self._action != "discard":
			self.check_docstatus_transition(previous.docstatus)

	def check_docstatus_transition(self, to_docstatus):
		"""Ensures valid `docstatus` transition.
		Valid transitions are (number in brackets is `docstatus`):

		- Save (0) > Save (0)
		- Save (0) > Submit (1)
		- Submit (1) > Submit (1)
		- Submit (1) > Cancel (2)

		"""
		if to_docstatus == DocStatus.DRAFT:
			if self.docstatus.is_draft():
				self._action = "save"
			elif self.docstatus.is_submitted():
				self._action = "submit"
				self.check_permission("submit")
			elif self.docstatus.is_cancelled():
				raise mrinimitable.DocstatusTransitionError(
					_("Cannot change docstatus from 0 (Draft) to 2 (Cancelled)")
				)
			else:
				raise mrinimitable.ValidationError(_("Invalid docstatus"), self.docstatus)

		elif to_docstatus == DocStatus.SUBMITTED:
			if self.docstatus.is_submitted():
				self._action = "update_after_submit"
				self.check_permission("submit")
			elif self.docstatus.is_cancelled():
				self._action = "cancel"
				self.check_permission("cancel")
			elif self.docstatus.is_draft():
				raise mrinimitable.DocstatusTransitionError(
					_("Cannot change docstatus from 1 (Submitted) to 0 (Draft)")
				)
			else:
				raise mrinimitable.ValidationError(_("Invalid docstatus"), self.docstatus)

		elif to_docstatus == DocStatus.CANCELLED:
			raise mrinimitable.ValidationError(_("Cannot edit cancelled document"))

	def set_parent_in_children(self):
		"""Updates `parent` and `parenttype` property in all children."""
		for d in self.get_all_children():
			d.parent = self.name
			d.parenttype = self.doctype

	def set_name_in_children(self):
		# Set name for any new children
		for d in self.get_all_children():
			if not d.name:
				set_new_name(d)

	def validate_update_after_submit(self):
		if self.flags.ignore_validate_update_after_submit:
			return

		self._validate_update_after_submit()
		for d in self.get_all_children():
			if d.is_new() and self.meta.get_field(d.parentfield).allow_on_submit:
				# in case of a new row, don't validate allow on submit, if table is allow on submit
				continue

			d._validate_update_after_submit()

		# TODO check only allowed values are updated

	def _validate_mandatory(self):
		if self.flags.ignore_mandatory:
			return

		missing = self._get_missing_mandatory_fields()
		for d in self.get_all_children():
			missing.extend(d._get_missing_mandatory_fields())

		if not missing:
			return

		for idx, msg in missing:  # noqa: B007
			msgprint(msg)

		if mrinimitable.flags.print_messages:
			print(self.as_json().encode("utf-8"))

		raise mrinimitable.MandatoryError(
			"[{doctype}, {name}]: {fields}".format(
				fields=", ".join(each[0] for each in missing), doctype=self.doctype, name=self.name
			)
		)

	def _validate_links(self):
		if self.flags.ignore_links or self._action == "cancel":
			return

		invalid_links, cancelled_links = self.get_invalid_links()

		for d in self.get_all_children():
			result = d.get_invalid_links(is_submittable=self.meta.is_submittable)
			invalid_links.extend(result[0])
			cancelled_links.extend(result[1])

		if invalid_links:
			msg = ", ".join(each[2] for each in invalid_links)
			mrinimitable.throw(_("Could not find {0}").format(msg), mrinimitable.LinkValidationError)

		if cancelled_links:
			msg = ", ".join(each[2] for each in cancelled_links)
			mrinimitable.throw(_("Cannot link cancelled document: {0}").format(msg), mrinimitable.CancelledLinkError)

	def get_all_children(self, parenttype=None) -> list["Document"]:
		"""Return all children documents from **Table** type fields in a list."""

		children = []

		for fieldname, child_doctype in self._table_fieldnames.items():
			if parenttype and child_doctype != parenttype:
				continue

			if value := self.get(fieldname):
				children.extend(value)

		return children

	def run_method(self, method, *args, **kwargs):
		"""run standard triggers, plus those in hooks"""

		def fn(self, *args, **kwargs):
			method_object = getattr(self, method, None)

			# Cannot have a field with same name as method
			# If method found in __dict__, expect it to be callable
			if method in self.__dict__ or callable(method_object):
				return method_object(*args, **kwargs)

		fn.__name__ = str(method)
		out = Document.hook(fn)(self, *args, **kwargs)

		self.run_notifications(method)
		run_webhooks(self, method)
		run_server_script_for_doc_event(self, method)

		return out

	def run_trigger(self, method, *args, **kwargs):
		return self.run_method(method, *args, **kwargs)

	def run_notifications(self, method):
		"""Run notifications for this method"""
		if (
			method == "onload"
			or (mrinimitable.flags.in_import and mrinimitable.flags.mute_emails)
			or mrinimitable.flags.in_patch
			or mrinimitable.flags.in_install
		):
			return

		if self.flags.notifications_executed is None:
			self.flags.notifications_executed = []

		from mrinimitable.email.doctype.notification.notification import evaluate_alert

		def _get_notifications():
			"""Return enabled notifications for the current doctype."""

			return mrinimitable.get_all(
				"Notification",
				fields=["name", "event", "method"],
				filters={"enabled": 1, "document_type": self.doctype},
			)

		notifications = mrinimitable.client_cache.get_value(
			f"notifications::{self.doctype}", generator=_get_notifications
		)

		if not notifications:
			return

		def _evaluate_alert(alert):
			if alert.name in self.flags.notifications_executed:
				return

			evaluate_alert(self, alert.name, alert.event)
			self.flags.notifications_executed.append(alert.name)

		event_map = {
			"on_update": "Save",
			"after_insert": "New",
			"on_submit": "Submit",
			"on_cancel": "Cancel",
		}

		if not self.flags.in_insert and not self.flags.in_delete:
			# value change is not applicable in insert
			event_map["on_change"] = "Value Change"

		for alert in notifications:
			event = event_map.get(method, None)
			if event and alert.event == event:
				_evaluate_alert(alert)
			elif alert.event == "Method" and method == alert.method:
				_evaluate_alert(alert)

	def _submit(self):
		"""Submit the document. Sets `docstatus` = 1, then saves."""
		self.docstatus = DocStatus.SUBMITTED
		return self.save()

	def _cancel(self):
		"""Cancel the document. Sets `docstatus` = 2, then saves."""
		self.docstatus = DocStatus.CANCELLED
		return self.save()

	def _rename(
		self, name: str | int, merge: bool = False, force: bool = False, validate_rename: bool = True
	):
		"""Rename the document. Triggers mrinimitable.rename_doc, then reloads."""
		from mrinimitable.model.rename_doc import rename_doc

		self.name = rename_doc(doc=self, new=name, merge=merge, force=force, validate=validate_rename)
		self.reload()

	@mrinimitable.whitelist()
	def submit(self):
		"""Submit the document. Sets `docstatus` = 1, then saves."""
		return self._submit()

	@mrinimitable.whitelist()
	def cancel(self):
		"""Cancel the document. Sets `docstatus` = 2, then saves."""
		return self._cancel()

	@mrinimitable.whitelist()
	def discard(self):
		"""Discard the draft document. Sets `docstatus` = 2 with db_set."""
		self._action = "discard"

		self.check_if_locked()
		self.set_user_and_timestamp()
		self.check_if_latest()

		if not self.docstatus.is_draft():
			raise mrinimitable.ValidationError(_("Only draft documents can be discarded"), self.docstatus)

		self.check_permission("write")

		self.run_method("before_discard")
		self.db_set("docstatus", DocStatus.CANCELLED)
		delattr(self, "_action")
		self.run_method("on_discard")

	@mrinimitable.whitelist()
	def rename(self, name: str | int, merge=False, force=False, validate_rename=True):
		"""Rename the document to `name`. This transforms the current object."""
		return self._rename(name=name, merge=merge, force=force, validate_rename=validate_rename)

	def delete(self, ignore_permissions=False, force=False, *, delete_permanently=False):
		"""Delete document."""
		return mrinimitable.delete_doc(
			self.doctype,
			self.name,
			ignore_permissions=ignore_permissions,
			flags=self.flags,
			force=force,
			delete_permanently=delete_permanently,
		)

	def run_before_save_methods(self):
		"""Run standard methods before	`INSERT` or `UPDATE`. Standard Methods are:

		- `validate`, `before_save` for **Save**.
		- `validate`, `before_submit` for **Submit**.
		- `before_cancel` for **Cancel**
		- `before_update_after_submit` for **Update after Submit**

		Will also update title_field if set"""

		self.reset_seen()

		# before_validate method should be executed before ignoring validations
		if self._action in ("save", "submit"):
			self.run_method("before_validate")

		if self.flags.ignore_validate:
			return

		if self._action == "save":
			self.run_method("validate")
			self.run_method("before_save")
		elif self._action == "submit":
			self.run_method("validate")
			self.run_method("before_submit")
		elif self._action == "cancel":
			self.run_method("before_cancel")
		elif self._action == "update_after_submit":
			self.run_method("before_update_after_submit")

		self.set_title_field()

	def load_doc_before_save(self, *, raise_exception: bool = False):
		"""load existing document from db before saving"""

		self._doc_before_save = None

		if self.is_new():
			return

		try:
			self._doc_before_save = mrinimitable.get_doc(self.doctype, self.name, for_update=True)
		except mrinimitable.DoesNotExistError:
			if raise_exception:
				raise

			return mrinimitable.clear_last_message()

		for fieldname in self._table_fieldnames:
			for row in self.get(fieldname):
				row._doc_before_save = next(
					(d for d in (self._doc_before_save.get(fieldname) or []) if d.name == row.name), None
				)

	def run_post_save_methods(self):
		"""Run standard methods after `INSERT` or `UPDATE`. Standard Methods are:

		- `on_update` for **Save**.
		- `on_update`, `on_submit` for **Submit**.
		- `on_cancel` for **Cancel**
		- `update_after_submit` for **Update after Submit**"""

		if self._action == "save":
			self.run_method("on_update")
		elif self._action == "submit":
			self.run_method("on_update")
			self.run_method("on_submit")
		elif self._action == "cancel":
			self.run_method("on_cancel")
			self.check_no_back_links_exist()
		elif self._action == "update_after_submit":
			self.run_method("on_update_after_submit")

		if not (mrinimitable.flags.in_import and self.is_new()):
			self.clear_cache()

		if self.flags.get("notify_update", True):
			self.notify_update()

		update_global_search(self)

		self.save_version()

		self.run_method("on_change")

		if (self.doctype, self.name) in mrinimitable.flags.currently_saving:
			mrinimitable.flags.currently_saving.remove((self.doctype, self.name))

	def clear_cache(self):
		mrinimitable.clear_document_cache(self.doctype, self.name)

	def reset_seen(self):
		"""Clear _seen property and set current user as seen"""
		if (
			getattr(self.meta, "track_seen", False)
			and not getattr(self.meta, "issingle", False)
			and not self.is_new()
		):
			mrinimitable.db.set_value(
				self.doctype, self.name, "_seen", json.dumps([mrinimitable.session.user]), update_modified=False
			)

	def notify_update(self):
		"""Publish realtime that the current document is modified"""
		if (
			mrinimitable.flags.in_import
			or mrinimitable.flags.in_patch
			or mrinimitable.flags.in_migrate
			or mrinimitable.flags.in_install
		):
			return

		mrinimitable.publish_realtime(
			"doc_update",
			{"modified": self.modified, "doctype": self.doctype, "name": self.name},
			doctype=self.doctype,
			docname=self.name,
			after_commit=True,
		)

		if not self.meta.get("read_only") and not self.meta.get("issingle") and not self.meta.get("istable"):
			data = {"doctype": self.doctype, "name": self.name, "user": mrinimitable.session.user}
			mrinimitable.publish_realtime("list_update", data, after_commit=True)

	def db_set(self, fieldname, value=None, update_modified=True, notify=False, commit=False):
		"""Set a value in the document object, update the timestamp and update the database.

		WARNING: This method does not trigger controller validations and should
		be used very carefully.

		:param fieldname: fieldname of the property to be updated, or a {"field":"value"} dictionary
		:param value: value of the property to be updated
		:param update_modified: default True. updates the `modified` and `modified_by` properties
		:param notify: default False. run doc.notify_update() to send updates via socketio
		:param commit: default False. run mrinimitable.db.commit()
		"""
		if isinstance(fieldname, dict):
			self.update(fieldname)
		else:
			self.set(fieldname, value)

		if update_modified and (self.doctype, self.name) not in mrinimitable.flags.currently_saving:
			# don't update modified timestamp if called from post save methods
			# like on_update or on_submit
			self.set("modified", now())
			self.set("modified_by", mrinimitable.session.user)

		# load but do not reload doc_before_save because before_change or on_change might expect it
		if not self.get_doc_before_save() and not self.meta.istable:
			self.load_doc_before_save()

		# to trigger notification on value change
		self.run_method("before_change")

		if self.name is None:
			return

		if self.meta.issingle:
			mrinimitable.db.set_single_value(
				self.doctype,
				fieldname,
				value,
				modified=self.modified,
				modified_by=self.modified_by,
				update_modified=update_modified,
			)
		else:
			mrinimitable.db.set_value(
				self.doctype,
				self.name,
				fieldname,
				value,
				self.modified,
				self.modified_by,
				update_modified=update_modified,
			)

		self.run_method("on_change")

		if notify:
			self.notify_update()

		if commit:
			mrinimitable.db.commit()

	def db_get(self, fieldname):
		"""get database value for this fieldname"""
		return mrinimitable.db.get_value(self.doctype, self.name, fieldname)

	def check_no_back_links_exist(self):
		"""Check if document links to any active document before Cancel."""
		from mrinimitable.model.delete_doc import check_if_doc_is_dynamically_linked, check_if_doc_is_linked

		if not self.flags.ignore_links:
			check_if_doc_is_linked(self, method="Cancel")
			check_if_doc_is_dynamically_linked(self, method="Cancel")

	def save_version(self):
		"""Save version info"""

		# don't track version under following conditions
		if (
			not getattr(self.meta, "track_changes", False)
			or self.doctype == "Version"
			or self.flags.ignore_version
			or mrinimitable.flags.in_install
			or (not self._doc_before_save and mrinimitable.flags.in_patch)
		):
			return

		doc_to_compare = self._doc_before_save
		if not doc_to_compare and (amended_from := self.get("amended_from")):
			doc_to_compare = mrinimitable.get_doc(self.doctype, amended_from)

		version = mrinimitable.new_doc("Version")

		if not doc_to_compare and not self.flags.updater_reference:
			return

		if version.update_version_info(doc_to_compare, self):
			version.insert(ignore_permissions=True)

	@staticmethod
	def hook(f):
		"""Decorator: Make method `hookable` (i.e. extensible by another app).

		Note: If each hooked method returns a value (dict), then all returns are
		collated in one dict and returned. Ideally, don't return values in hookable
		methods, set properties in the document."""

		def add_to_return_value(self, new_return_value):
			if new_return_value is None:
				self._return_value = self.get("_return_value")
				return

			if isinstance(new_return_value, dict):
				if not self.get("_return_value"):
					self._return_value = {}
				self._return_value.update(new_return_value)
			else:
				self._return_value = new_return_value

		def compose(fn, *hooks):
			def runner(self, method, *args, **kwargs):
				add_to_return_value(self, fn(self, *args, **kwargs))
				for f in hooks:
					try:
						mrinimitable.db._disable_transaction_control += 1
						add_to_return_value(self, f(self, method, *args, **kwargs))
					finally:
						mrinimitable.db._disable_transaction_control -= 1

				return self.__dict__.pop("_return_value", None)

			return runner

		def composer(self, *args, **kwargs):
			hooks = []
			method = f.__name__
			doc_events = mrinimitable.get_doc_hooks()
			for handler in doc_events.get(self.doctype, {}).get(method, []) + doc_events.get("*", {}).get(
				method, []
			):
				hooks.append(mrinimitable.get_attr(handler))

			composed = compose(f, *hooks)
			return composed(self, method, *args, **kwargs)

		return composer

	def is_whitelisted(self, method_name):
		method = getattr(self, method_name, None)
		if not method:
			raise NotFound(f"Method {method_name} not found")

		is_whitelisted(getattr(method, "__func__", method))

	def validate_value(self, fieldname, condition, val2, doc=None, raise_exception=None):
		"""Check that value of fieldname should be 'condition' val2
		else throw Exception."""
		if not doc:
			doc = self

		val1 = doc.get_value(fieldname)

		df = doc.meta.get_field(fieldname)
		val2 = doc.cast(val2, df)

		if not compare(val1, condition, val2):
			label = doc.meta.get_label(fieldname)
			if doc.get("parentfield"):
				msg = _("Incorrect value in row {0}:").format(doc.idx)
			else:
				msg = _("Incorrect value:")

			if condition == "in":
				msg += _("{0} must be one of {1}").format(label, val2)
			elif condition == "not in":
				msg += _("{0} must be none of {1}").format(label, val2)
			elif condition == "^":
				msg += _("{0} must be beginning with '{1}'").format(label, val2)
			elif condition == "=":
				msg += _("{0} must be equal to '{1}'").format(label, val2)
			else:
				msg += _("{0} must be {1} {2}").format(label, condition, val2)

			# raise passed exception or True
			msgprint(msg, raise_exception=raise_exception or True)

	def validate_table_has_rows(self, parentfield, raise_exception=None):
		"""Raise exception if Table field is empty."""
		if not (isinstance(self.get(parentfield), list) and len(self.get(parentfield)) > 0):
			label = _(self.meta.get_label(parentfield))
			mrinimitable.throw(
				_("Table {0} cannot be empty").format(label), raise_exception or mrinimitable.EmptyTableError
			)

	def round_floats_in(self, doc, fieldnames=None):
		"""Round floats for all `Currency`, `Float`, `Percent` fields for the given doc.

		:param doc: Document whose numeric properties are to be rounded.
		:param fieldnames: [Optional] List of fields to be rounded."""
		if not fieldnames:
			fieldnames = (
				df.fieldname
				for df in doc.meta.get("fields", {"fieldtype": ["in", ["Currency", "Float", "Percent"]]})
			)

		# PERF: flt internally has to resolve this if we don't specify it.
		rounding_method = mrinimitable.get_system_settings("rounding_method")
		for fieldname in fieldnames:
			doc.set(
				fieldname,
				flt(
					doc.get(fieldname),
					self.precision(fieldname, doc.get("parentfield")),
					rounding_method=rounding_method,
				),
			)

	def get_url(self):
		"""Return Desk URL for this document."""
		return get_absolute_url(self.doctype, self.name)

	@mrinimitable.whitelist()
	def add_comment(
		self,
		comment_type="Comment",
		text=None,
		comment_email=None,
		comment_by=None,
	):
		"""Add a comment to this document.

		:param comment_type: e.g. `Comment`. See Communication for more info."""

		return mrinimitable.get_doc(
			{
				"doctype": "Comment",
				"comment_type": comment_type,
				"comment_email": comment_email or mrinimitable.session.user,
				"comment_by": comment_by,
				"reference_doctype": self.doctype,
				"reference_name": self.name,
				"content": text or comment_type,
			}
		).insert(ignore_permissions=True)

	def add_seen(self, user=None):
		"""add the given/current user to list of users who have seen this document (_seen)"""
		if not user:
			user = mrinimitable.session.user

		if self.meta.track_seen and not mrinimitable.flags.read_only and not self.meta.issingle:
			_seen = self.get("_seen") or []
			_seen = mrinimitable.parse_json(_seen)

			if user not in _seen:
				_seen.append(user)
				commit_after_response(
					lambda: mrinimitable.db.set_value(
						self.doctype, self.name, "_seen", json.dumps(_seen), update_modified=False
					)
				)

	def add_viewed(self, user=None, force=False, unique_views=False):
		"""Add a view log for the current document"""

		if not (getattr(self.meta, "track_views", False) or force):
			return

		user = user or mrinimitable.session.user

		if unique_views and mrinimitable.db.exists(
			"View Log", {"reference_doctype": self.doctype, "reference_name": self.name, "viewed_by": user}
		):
			return

		view_log = mrinimitable.get_doc(
			{
				"doctype": "View Log",
				"viewed_by": user,
				"reference_doctype": self.doctype,
				"reference_name": self.name,
			}
		)
		if mrinimitable.flags.read_only:
			view_log.deferred_insert()
		else:
			commit_after_response(lambda: view_log.insert(ignore_permissions=True))

		return view_log

	def log_error(self, title=None, message=None):
		"""Helper function to create an Error Log"""
		return mrinimitable.log_error(
			message=message, title=title, reference_doctype=self.doctype, reference_name=self.name
		)

	def get_signature(self):
		"""Return signature (hash) for private URL."""
		return hashlib.sha224(f"{self.doctype}:{self.name}".encode(), usedforsecurity=False).hexdigest()

	def get_document_share_key(self, expires_on=None, no_expiry=False):
		if no_expiry:
			expires_on = None

		existing_key = mrinimitable.db.exists(
			"Document Share Key",
			{
				"reference_doctype": self.doctype,
				"reference_docname": self.name,
				"expires_on": expires_on,
			},
		)
		if existing_key:
			doc = mrinimitable.get_doc("Document Share Key", existing_key)
		else:
			doc = mrinimitable.new_doc("Document Share Key")
			doc.reference_doctype = self.doctype
			doc.reference_docname = self.name
			doc.expires_on = expires_on
			doc.flags.no_expiry = no_expiry
			doc.insert(ignore_permissions=True)

		return doc.key

	def get_liked_by(self):
		liked_by = getattr(self, "_liked_by", None)
		if liked_by:
			return json.loads(liked_by)
		else:
			return []

	@property
	def __onload(self):
		onload = self.get("__onload")
		if onload is None:
			onload = mrinimitable._dict()
			self.set("__onload", onload)

		return onload

	def set_onload(self, key, value):
		self.__onload[key] = value

	def get_onload(self, key=None):
		return self.__onload[key] if key else self.__onload

	def queue_action(self, action, **kwargs):
		"""Run an action in background. If the action has an inner function,
		like _submit for submit, it will call that instead"""
		# call _submit instead of submit, so you can override submit to call
		# run_delayed based on some action
		# See: Stock Reconciliation
		from mrinimitable.utils.background_jobs import enqueue

		if hasattr(self, f"_{action}"):
			action = f"_{action}"

		self.check_if_locked()
		self.lock()

		enqueue_after_commit = kwargs.pop("enqueue_after_commit", None)
		if enqueue_after_commit is None:
			enqueue_after_commit = True

		return enqueue(
			"mrinimitable.model.document.execute_action",
			__doctype=self.doctype,
			__name=self.name,
			__action=action,
			enqueue_after_commit=enqueue_after_commit,
			**kwargs,
		)

	def lock(self, timeout=None):
		"""Creates a lock file for the given document. If timeout is set,
		it will retry every 1 second for acquiring the lock again

		:param timeout: Timeout in seconds, default 0"""
		signature = self.get_signature()
		if file_lock.lock_exists(signature):
			lock_exists = True
			if file_lock.lock_age(signature) > DOCUMENT_LOCK_EXPIRY:
				file_lock.delete_lock(signature)
				lock_exists = False
			if timeout:
				for _ in range(timeout):
					time.sleep(1)
					if not file_lock.lock_exists(signature):
						lock_exists = False
						break
			if lock_exists:
				raise mrinimitable.DocumentLockedError
		file_lock.create_lock(signature)
		mrinimitable.local.locked_documents.append(self)

	def unlock(self):
		"""Delete the lock file for this document"""
		file_lock.delete_lock(self.get_signature())
		if self in mrinimitable.local.locked_documents:
			mrinimitable.local.locked_documents.remove(self)

	def validate_from_to_dates(self, from_date_field: str, to_date_field: str) -> None:
		"""Validate that the value of `from_date_field` is not later than the value of `to_date_field`."""
		from_date = self.get(from_date_field)
		to_date = self.get(to_date_field)
		if not (from_date and to_date):
			return

		if date_diff(to_date, from_date) < 0:
			table_row = ""
			if self.meta.istable:
				table_row = _("{0} row #{1}: ").format(
					_(mrinimitable.unscrub(self.parentfield)),
					self.idx,
				)

			mrinimitable.throw(
				table_row
				+ _("{0} must be after {1}").format(
					mrinimitable.bold(_(self.meta.get_label(to_date_field))),
					mrinimitable.bold(_(self.meta.get_label(from_date_field))),
				),
				mrinimitable.exceptions.InvalidDates,
			)

	def get_assigned_users(self):
		assigned_users = mrinimitable.get_all(
			"ToDo",
			fields=["allocated_to"],
			filters={
				"reference_type": self.doctype,
				"reference_name": self.name,
				"status": ("!=", "Cancelled"),
			},
			pluck="allocated_to",
		)

		return set(assigned_users)

	def add_tag(self, tag):
		"""Add a Tag to this document"""
		from mrinimitable.desk.doctype.tag.tag import DocTags

		DocTags(self.doctype).add(self.name, tag)

	def remove_tag(self, tag):
		"""Remove a Tag to this document"""
		from mrinimitable.desk.doctype.tag.tag import DocTags

		DocTags(self.doctype).remove(self.name, tag)

	def get_tags(self):
		"""Return a list of Tags attached to this document"""
		from mrinimitable.desk.doctype.tag.tag import DocTags

		return DocTags(self.doctype).get_tags(self.name).split(",")[1:]

	def deferred_insert(self) -> None:
		"""Push the document to redis temporarily and insert later.

		WARN: This doesn't guarantee insertion as redis can be restarted
		before data is flushed to database.
		"""

		from mrinimitable.deferred_insert import deferred_insert

		self.set_user_and_timestamp()

		doc = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)
		deferred_insert(doctype=self.doctype, records=doc)

	def __str__(self):
		return f"{self.doctype} ({self.name or 'unsaved'})"

	def __repr__(self):
		doctype = f"doctype={self.doctype}"
		name = self.name or "unsaved"
		docstatus = f" docstatus={self.docstatus}" if self.docstatus else ""
		parent = f" parent={self.parent}" if getattr(self, "parent", None) else ""

		return f"<{self.__class__.__name__}: {doctype} {name}{docstatus}{parent}>"


def execute_action(__doctype, __name, __action, **kwargs):
	"""Execute an action on a document (called by background worker)"""
	doc = mrinimitable.get_doc(__doctype, __name)
	doc.unlock()
	try:
		getattr(doc, __action)(**kwargs)
	except Exception:
		mrinimitable.db.rollback()

		# add a comment (?)
		if mrinimitable.message_log:
			msg = mrinimitable.message_log[-1].get("message")
		else:
			msg = "<pre><code>" + mrinimitable.get_traceback() + "</pre></code>"

		doc.add_comment("Comment", _("Action Failed") + "<br><br>" + msg)
	doc.notify_update()


def bulk_insert(
	doctype: str,
	documents: Iterable["Document"],
	ignore_duplicates: bool = False,
	chunk_size=1000,
	commit_chunks=False,
):
	"""Insert simple Documents objects to database in bulk.

	Warning/Info:
	        - All documents are inserted without triggering ANY hooks.
	        - This function assumes you've done the due dilligence and inserts in similar fashion as db_insert
	        - Documents can be any iterable / generator containing Document objects
	"""

	doctype_meta = mrinimitable.get_meta(doctype)

	valid_column_map = {
		doctype: doctype_meta.get_valid_columns(),
	}

	child_table_fields = doctype_meta.get_table_fields()
	for child_table in child_table_fields:
		valid_column_map[child_table.options] = mrinimitable.get_meta(child_table.options).get_valid_columns()

	documents = iter(documents)
	while document_batch := list(itertools.islice(documents, chunk_size)):
		values_map = {
			doctype: _document_values_generator(document_batch, valid_column_map[doctype]),
		}

		for child_table in child_table_fields:
			values_map[child_table.options] = _document_values_generator(
				[
					ch_doc
					for ch_doc in (
						child_docs for doc in document_batch for child_docs in doc.get(child_table.fieldname)
					)
				],
				valid_column_map[child_table.options],
			)

		for dt, docs in values_map.items():
			mrinimitable.db.bulk_insert(dt, valid_column_map[dt], docs, ignore_duplicates=ignore_duplicates)

		if commit_chunks:
			mrinimitable.db.commit()


def _document_values_generator(
	documents: Iterable["Document"],
	columns: list[str],
) -> Generator[tuple[Any], None, None]:
	for doc in documents:
		doc.creation = doc.modified = now()
		doc.owner = doc.modified_by = mrinimitable.session.user
		doc_values = doc.get_valid_dict(
			convert_dates_to_str=True,
			ignore_nulls=True,
			ignore_virtual=True,
		)
		yield tuple(doc_values.get(col) for col in columns)


@mrinimitable.whitelist()
def unlock_document(doctype: str, name: str):
	mrinimitable.get_lazy_doc(doctype, name).unlock()
	mrinimitable.msgprint(mrinimitable._("Document Unlocked"), alert=True)


def get_lazy_controller(doctype):
	lazy_controllers = mrinimitable.lazy_controllers.setdefault(mrinimitable.local.site, {})
	if doctype not in lazy_controllers:
		meta = mrinimitable.get_meta(doctype)
		original_controller = get_controller(doctype)
		if meta.is_virtual:  # not supported
			lazy_controllers[doctype] = original_controller
			warnings.warn("Virtual doctypes don't support lazy loading", stacklevel=2)
			return original_controller

		# Dynamically construct a class that subclasses LazyDocument and original controller.
		lazy_controller = type(f"Lazy{original_controller.__name__}", (LazyDocument, original_controller), {})
		for fieldname, child_doctype in meta._table_doctypes.items():
			setattr(lazy_controller, fieldname, LazyChildTable(fieldname, child_doctype))

		lazy_controllers[doctype] = lazy_controller
	return lazy_controllers[doctype]


class LazyDocument:
	"""Mixin for Document class that implments lazy loading for child tables."""

	@override
	def load_children_from_db(self: Document):
		"""Override Document which eagerly loads child tables"""
		# This is a map of loaded children, it should get erased whenever load_children_from_db is
		# called to allow reloading lazily again.
		for fieldname in self._table_fieldnames:
			self.__dict__.pop(fieldname, None)

	@override
	def get(self: Document, key, filters=None, limit=None, default=None):
		# Ensure that table descriptor is triggered at least once
		if isinstance(key, str) and key in self._table_fieldnames:
			getattr(self, key, None)
		return super().get(key, filters, limit, default)

	@override
	def append(self, key: str, value: D | dict | None = None, position: int = -1) -> D:
		# Ensure that table descriptor is triggered at least once
		# key is assumed to be a table fieldname (as expected by BaseDocument.append)
		getattr(self, key, None)
		return super().append(key, value, position)

	@override
	def db_update_all(self):
		self.db_update()
		for fieldname in self._table_fieldnames:
			if fieldname not in self.__dict__:
				# Not fetched, can't possibly change so no need to update
				continue
			for doc in self.get(fieldname):
				doc.db_update()

	@override
	def init_child_tables(self):
		# Avoid initializing anything, descriptor handles it.
		return


class LazyChildTable:
	__slots__ = ("doctype", "fieldname")

	def __init__(self, fieldname: str, doctype: str) -> None:
		self.fieldname = fieldname
		self.doctype = doctype

	def __get__(self, doc: Document, objtype=None):
		# Note: avoid any high level access here, can cause recursion
		fieldname = self.fieldname
		__dict = doc.__dict__
		assert fieldname not in __dict, "Descriptor should not override existing values"
		children = doc._load_child_table_from_db(fieldname, self.doctype) or []
		__dict[fieldname] = []
		# Update __dict__ and convert to Document objects
		doc.extend(fieldname, children)
		return __dict[fieldname]

	# Note: Don't implement __set__ method! https://docs.python.org/3/howto/descriptor.html#descriptor-protocol


def copy_doc(doc: "Document", ignore_no_copy: bool = True) -> "Document":
	"""No_copy fields also get copied."""
	import copy
	from types import MappingProxyType

	from mrinimitable.model.base_document import BaseDocument

	def remove_no_copy_fields(d):
		for df in d.meta.get("fields", {"no_copy": 1}):
			if hasattr(d, df.fieldname):
				d.set(df.fieldname, None)

	fields_to_clear = ["name", "owner", "creation", "modified", "modified_by"]

	if not mrinimitable.in_test:
		fields_to_clear.append("docstatus")

	if isinstance(doc, BaseDocument):
		d = doc.as_dict()
	elif isinstance(doc, MappingProxyType):  # global test record
		d = dict(doc)
	else:
		d = doc

	newdoc = get_doc(copy.deepcopy(d))
	newdoc.set("__islocal", 1)
	for fieldname in [*fields_to_clear, "amended_from", "amendment_date"]:
		newdoc.set(fieldname, None)

	if not ignore_no_copy:
		remove_no_copy_fields(newdoc)

	for d in newdoc.get_all_children():
		d.set("__islocal", 1)

		for fieldname in fields_to_clear:
			d.set(fieldname, None)

		if not ignore_no_copy:
			remove_no_copy_fields(d)

	return newdoc


def new_doc(
	doctype: str,
	*,
	parent_doc: Optional["Document"] = None,
	parentfield: str | None = None,
	as_dict: bool = False,
	**kwargs,
) -> "Document":
	"""Return a new document of the given DocType with defaults set.

	:param doctype: DocType of the new document.
	:param parent_doc: [optional] add to parent document.
	:param parentfield: [optional] add against this `parentfield`.
	:param as_dict: [optional] return as dictionary instead of Document.
	:param kwargs: [optional] You can specify fields as field=value pairs in function call.
	"""

	from mrinimitable.model.create_new import get_new_doc

	new_doc = get_new_doc(doctype, parent_doc, parentfield, as_dict=as_dict)

	return new_doc.update(kwargs)


def get_cached_doc(*args: Any, **kwargs: Any) -> "Document":
	"""Identical to `mrinimitable.get_doc`, but return from cache if available."""
	if (key := can_cache_doc(args)) and (doc := mrinimitable.cache.get_value(key)):
		return doc

	# Not found in cache, fetch from DB
	doc = get_doc(*args, **kwargs)

	# Store in cache
	if not key:
		key = get_document_cache_key(doc.doctype, doc.name)

	_set_document_in_cache(key, doc)

	return doc


def _set_document_in_cache(key: str, doc: "Document") -> None:
	mrinimitable.cache.set_value(key, doc, expires_in_sec=3600)


def can_cache_doc(args) -> str | None:
	"""
	Determine if document should be cached based on get_doc params.
	Return cache key if doc can be cached, None otherwise.
	"""

	if not args:
		return

	doctype = args[0]
	name = doctype if len(args) == 1 or args[1] is None else args[1]

	# Only cache if both doctype and name are strings
	if isinstance(doctype, str) and isinstance(name, str):
		return get_document_cache_key(doctype, name)


def get_document_cache_key(doctype: str, name: str):
	return f"document_cache::{doctype}::{name}"


def clear_document_cache(doctype: str, name: str | None = None) -> None:
	mrinimitable.db.value_cache.pop(doctype, None)

	def clear_in_redis():
		if name is not None:
			mrinimitable.cache.delete_value(get_document_cache_key(doctype, name))
		else:
			mrinimitable.cache.delete_keys(get_document_cache_key(doctype, ""))

	clear_in_redis()
	if hasattr(mrinimitable.db, "after_commit"):
		mrinimitable.db.after_commit.add(clear_in_redis)
		mrinimitable.db.after_rollback.add(clear_in_redis)

	if doctype == "System Settings" and hasattr(mrinimitable.local, "system_settings"):
		delattr(mrinimitable.local, "system_settings")

	if doctype == "Website Settings" and hasattr(mrinimitable.local, "website_settings"):
		delattr(mrinimitable.local, "website_settings")


def get_cached_value(
	doctype: str, name: str | dict, fieldname: str | Iterable[str] = "name", as_dict: bool = False
) -> Any:
	try:
		doc = get_cached_doc(doctype, name)
	except mrinimitable.DoesNotExistError:
		mrinimitable.clear_last_message()
		return

	if isinstance(fieldname, str):
		if as_dict:
			mrinimitable.throw("Cannot make dict for single fieldname")
		return doc.get(fieldname)

	values = [doc.get(f) for f in fieldname]
	if as_dict:
		return mrinimitable._dict(zip(fieldname, values, strict=False))
	return values


def get_single_value(setting: str, fieldname: str, /, *, as_dict: bool = False):
	"""Return the cached value associated with the given fieldname from single DocType.

	Usage:
		telemetry_enabled = mrinimitable.get_single_value("System Settings", "telemetry_enabled")
	"""
	return get_cached_value(setting, setting, fieldname=fieldname, as_dict=as_dict)


def get_last_doc(
	doctype,
	filters: FilterSignature | None = None,
	order_by="creation desc",
	*,
	for_update=False,
):
	"""Get last created document of this type."""
	d = mrinimitable.get_all(doctype, filters=filters, limit_page_length=1, order_by=order_by, pluck="name")
	if d:
		return get_doc(doctype, d[0], for_update=for_update)
	else:
		raise mrinimitable.DoesNotExistError(doctype=doctype)


def get_single(doctype):
	"""Return a `mrinimitable.model.document.Document` object of the given Single doctype."""
	return get_doc(doctype, doctype)
