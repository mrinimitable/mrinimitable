# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
from typing import TYPE_CHECKING

import mrinimitable
import mrinimitable.model
import mrinimitable.utils
from mrinimitable import _
from mrinimitable.desk.reportview import validate_args
from mrinimitable.model.db_query import check_parent_permission
from mrinimitable.model.utils import is_virtual_doctype
from mrinimitable.utils import get_safe_filters
from mrinimitable.utils.caching import http_cache

if TYPE_CHECKING:
	from mrinimitable.model.document import Document

"""
Handle RESTful requests that are mapped to the `/api/resource` route.

Requests via MrinimitableClient are also handled here.
"""


@mrinimitable.whitelist()
def get_list(
	doctype,
	fields=None,
	filters=None,
	group_by=None,
	order_by=None,
	limit_start=None,
	limit_page_length=20,
	parent=None,
	debug: bool = False,
	as_dict: bool = True,
	or_filters=None,
):
	"""Return a list of records by filters, fields, ordering and limit.

	:param doctype: DocType of the data to be queried
	:param fields: fields to be returned. Default is `name`
	:param filters: filter list by this dict
	:param order_by: Order by this fieldname
	:param limit_start: Start at this index
	:param limit_page_length: Number of records to be returned (default 20)"""
	if mrinimitable.is_table(doctype):
		check_parent_permission(parent, doctype)

	args = mrinimitable._dict(
		doctype=doctype,
		parent_doctype=parent,
		fields=fields,
		filters=filters,
		or_filters=or_filters,
		group_by=group_by,
		order_by=order_by,
		limit_start=limit_start,
		limit_page_length=limit_page_length,
		debug=debug,
		as_list=not as_dict,
	)

	validate_args(args)
	return mrinimitable.get_list(**args)


@mrinimitable.whitelist()
def get_count(doctype, filters=None, debug=False, cache=False):
	return mrinimitable.db.count(doctype, get_safe_filters(filters), debug, cache)


@mrinimitable.whitelist()
def get(doctype, name=None, filters=None, parent=None):
	"""Return a document by name or filters.

	:param doctype: DocType of the document to be returned
	:param name: return document of this `name`
	:param filters: If name is not set, filter by these values and return the first match"""
	if mrinimitable.is_table(doctype):
		check_parent_permission(parent, doctype)

	if name:
		doc = mrinimitable.get_doc(doctype, name)
	elif filters or filters == {}:
		doc = mrinimitable.get_doc(doctype, mrinimitable.parse_json(filters))
	else:
		doc = mrinimitable.get_doc(doctype)  # single

	doc.check_permission()
	doc.apply_fieldlevel_read_permissions()

	return doc.as_dict()


@mrinimitable.whitelist()
def get_value(doctype, fieldname, filters=None, as_dict=True, debug=False, parent=None):
	"""Return a value from a document.

	:param doctype: DocType to be queried
	:param fieldname: Field to be returned (default `name`)
	:param filters: dict or string for identifying the record"""
	if mrinimitable.is_table(doctype):
		check_parent_permission(parent, doctype)

	if not mrinimitable.has_permission(doctype, parent_doctype=parent):
		mrinimitable.throw(_("No permission for {0}").format(_(doctype)), mrinimitable.PermissionError)

	filters = get_safe_filters(filters)
	if isinstance(filters, str):
		filters = {"name": filters}

	try:
		fields = mrinimitable.parse_json(fieldname)
	except (TypeError, ValueError):
		# name passed, not json
		fields = [fieldname]

	# check whether the used filters were really parseable and usable
	# and did not just result in an empty string or dict
	if not filters:
		filters = None

	if mrinimitable.get_meta(doctype).issingle:
		value = mrinimitable.db.get_values_from_single(fields, filters, doctype, as_dict=as_dict, debug=debug)
	else:
		value = get_list(
			doctype,
			filters=filters,
			fields=fields,
			debug=debug,
			limit_page_length=1,
			parent=parent,
			as_dict=as_dict,
		)

	if as_dict:
		return value[0] if value else {}

	if not value:
		return

	return value[0] if len(fields) > 1 else value[0][0]


@mrinimitable.whitelist()
def get_single_value(doctype, field):
	if not mrinimitable.has_permission(doctype):
		mrinimitable.throw(_("No permission for {0}").format(_(doctype)), mrinimitable.PermissionError)

	return mrinimitable.db.get_single_value(doctype, field)


@mrinimitable.whitelist(methods=["POST", "PUT"])
def set_value(doctype, name, fieldname, value=None):
	"""Set a value using get_doc, group of values

	:param doctype: DocType of the document
	:param name: name of the document
	:param fieldname: fieldname string or JSON / dict with key value pair
	:param value: value if fieldname is JSON / dict"""

	if fieldname in (mrinimitable.model.default_fields + mrinimitable.model.child_table_fields):
		mrinimitable.throw(_("Cannot edit standard fields"))

	if not value:
		values = fieldname
		if isinstance(fieldname, str):
			try:
				values = json.loads(fieldname)
			except ValueError:
				values = {fieldname: ""}
	else:
		values = {fieldname: value}

	# check for child table doctype
	if not mrinimitable.get_meta(doctype).istable:
		doc = mrinimitable.get_doc(doctype, name)
		doc.update(values)
	else:
		doc = mrinimitable.db.get_value(doctype, name, ["parenttype", "parent"], as_dict=True)
		doc = mrinimitable.get_doc(doc.parenttype, doc.parent)
		child = doc.getone({"doctype": doctype, "name": name})
		child.update(values)

	doc.save()

	return doc.as_dict()


@mrinimitable.whitelist(methods=["POST", "PUT"])
def insert(doc=None):
	"""Insert a document

	:param doc: JSON or dict object to be inserted"""
	if isinstance(doc, str):
		doc = json.loads(doc)

	return insert_doc(doc).as_dict()


@mrinimitable.whitelist(methods=["POST", "PUT"])
def insert_many(docs=None):
	"""Insert multiple documents

	:param docs: JSON or list of dict objects to be inserted in one request"""
	if isinstance(docs, str):
		docs = json.loads(docs)

	if len(docs) > 200:
		mrinimitable.throw(_("Only 200 inserts allowed in one request"))

	return [insert_doc(doc).name for doc in docs]


@mrinimitable.whitelist(methods=["POST", "PUT"])
def save(doc):
	"""Update (save) an existing document

	:param doc: JSON or dict object with the properties of the document to be updated"""
	if isinstance(doc, str):
		doc = json.loads(doc)

	doc = mrinimitable.get_doc(doc)
	doc.save()

	return doc.as_dict()


@mrinimitable.whitelist(methods=["POST", "PUT"])
def rename_doc(doctype, old_name, new_name, merge=False):
	"""Rename document

	:param doctype: DocType of the document to be renamed
	:param old_name: Current `name` of the document to be renamed
	:param new_name: New `name` to be set"""
	new_name = mrinimitable.rename_doc(doctype, old_name, new_name, merge=merge)
	return new_name


@mrinimitable.whitelist(methods=["POST", "PUT"])
def submit(doc):
	"""Submit a document

	:param doc: JSON or dict object to be submitted remotely"""
	if isinstance(doc, str):
		doc = json.loads(doc)

	doc = mrinimitable.get_doc(doc)
	doc.submit()

	return doc.as_dict()


@mrinimitable.whitelist(methods=["POST", "PUT"])
def cancel(doctype, name):
	"""Cancel a document

	:param doctype: DocType of the document to be cancelled
	:param name: name of the document to be cancelled"""
	wrapper = mrinimitable.get_doc(doctype, name)
	wrapper.cancel()

	return wrapper.as_dict()


@mrinimitable.whitelist(methods=["DELETE", "POST"])
def delete(doctype, name):
	"""Delete a remote document

	:param doctype: DocType of the document to be deleted
	:param name: name of the document to be deleted"""
	delete_doc(doctype, name)


@mrinimitable.whitelist(methods=["POST", "PUT"])
def bulk_update(docs):
	"""Bulk update documents

	:param docs: JSON list of documents to be updated remotely. Each document must have `docname` property"""
	docs = json.loads(docs)
	failed_docs = []
	for doc in docs:
		doc.pop("flags", None)
		try:
			existing_doc = mrinimitable.get_doc(doc["doctype"], doc["docname"])
			existing_doc.update(doc)
			existing_doc.save()
		except Exception:
			failed_docs.append({"doc": doc, "exc": mrinimitable.utils.get_traceback()})

	return {"failed_docs": failed_docs}


@mrinimitable.whitelist()
def has_permission(doctype: str, docname: str, perm_type: str = "read"):
	"""Return a JSON with data whether the document has the requested permission.

	:param doctype: DocType of the document to be checked
	:param docname: `name` of the document to be checked
	:param perm_type: one of `read`, `write`, `create`, `submit`, `cancel`, `report`. Default is `read`"""
	# perm_type can be one of read, write, create, submit, cancel, report
	return {"has_permission": mrinimitable.has_permission(doctype, perm_type.lower(), docname)}


@mrinimitable.whitelist()
def get_doc_permissions(doctype: str, docname: str):
	"""Return an evaluated document permissions dict like `{"read":1, "write":1}`.

	:param doctype: DocType of the document to be evaluated
	:param docname: `name` of the document to be evaluated
	"""
	doc = mrinimitable.get_lazy_doc(doctype, docname)
	return {"permissions": mrinimitable.permissions.get_doc_permissions(doc)}


@mrinimitable.whitelist()
def get_password(doctype: str, name: str, fieldname: str):
	"""Return a password type property. Only applicable for System Managers

	:param doctype: DocType of the document that holds the password
	:param name: `name` of the document that holds the password
	:param fieldname: `fieldname` of the password property
	"""
	mrinimitable.only_for("System Manager")
	return mrinimitable.get_lazy_doc(doctype, name).get_password(fieldname)


from mrinimitable.deprecation_dumpster import get_js as _get_js

get_js = mrinimitable.whitelist()(_get_js)


@mrinimitable.whitelist(allow_guest=True)
def get_time_zone():
	"""Return the default time zone."""
	return {"time_zone": mrinimitable.defaults.get_defaults().get("time_zone")}


@mrinimitable.whitelist(methods=["POST", "PUT"])
def attach_file(
	filename=None,
	filedata=None,
	doctype=None,
	docname=None,
	folder=None,
	decode_base64=False,
	is_private=None,
	docfield=None,
):
	"""Attach a file to Document

	:param filename: filename e.g. test-file.txt
	:param filedata: base64 encode filedata which must be urlencoded
	:param doctype: Reference DocType to attach file to
	:param docname: Reference DocName to attach file to
	:param folder: Folder to add File into
	:param decode_base64: decode filedata from base64 encode, default is False
	:param is_private: Attach file as private file (1 or 0)
	:param docfield: file to attach to (optional)"""

	doc = mrinimitable.get_lazy_doc(doctype, docname)
	doc.check_permission()

	file = mrinimitable.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
			"attached_to_field": docfield,
			"folder": folder,
			"is_private": is_private,
			"content": filedata,
			"decode": decode_base64,
		}
	).save()

	if docfield and doctype:
		doc.set(docfield, file.file_url)
		doc.save()

	return file


@mrinimitable.whitelist()
@http_cache(max_age=10 * 60)
def is_document_amended(doctype: str, docname: str):
	if mrinimitable.permissions.has_permission(doctype):
		try:
			return mrinimitable.db.exists(doctype, {"amended_from": docname})
		except mrinimitable.db.InternalError:
			pass

	return False


@mrinimitable.whitelist()
def validate_link(doctype: str, docname: str, fields=None):
	if not isinstance(doctype, str):
		mrinimitable.throw(_("DocType must be a string"))

	if not isinstance(docname, str):
		mrinimitable.throw(_("Document Name must be a string"))

	if doctype != "DocType":
		parent_doctype = None
		if mrinimitable.get_meta(doctype).istable:  # needed for links to child rows
			parent_doctype = mrinimitable.db.get_value(doctype, docname, "parenttype")
		if not (
			mrinimitable.has_permission(doctype, "select", parent_doctype=parent_doctype)
			or mrinimitable.has_permission(doctype, "read", parent_doctype=parent_doctype)
		):
			mrinimitable.throw(
				_("You do not have Read or Select Permissions for {}").format(mrinimitable.bold(doctype)),
				mrinimitable.PermissionError,
			)

	values = mrinimitable._dict()

	if is_virtual_doctype(doctype):
		try:
			mrinimitable.get_doc(doctype, docname)
			values.name = docname
		except mrinimitable.DoesNotExistError:
			mrinimitable.clear_last_message()
			mrinimitable.msgprint(
				_("Document {0} {1} does not exist").format(mrinimitable.bold(doctype), mrinimitable.bold(docname)),
			)
		return values

	values.name = mrinimitable.db.get_value(doctype, docname, cache=True)

	fields = mrinimitable.parse_json(fields)
	if not values.name:
		return values

	if not fields:
		mrinimitable.local.response_headers.set("Cache-Control", "private,max-age=1800,stale-while-revalidate=7200")
		return values

	try:
		values.update(get_value(doctype, fields, docname))
	except mrinimitable.PermissionError:
		mrinimitable.clear_last_message()
		mrinimitable.msgprint(
			_("You need {0} permission to fetch values from {1} {2}").format(
				mrinimitable.bold(_("Read")), mrinimitable.bold(doctype), mrinimitable.bold(docname)
			),
			title=_("Cannot Fetch Values"),
			indicator="orange",
		)

	return values


def insert_doc(doc) -> "Document":
	"""Insert document and return parent document object with appended child document if `doc` is child document else return the inserted document object.

	:param doc: doc to insert (dict)"""

	doc = mrinimitable._dict(doc)
	if mrinimitable.is_table(doc.doctype):
		if not (doc.parenttype and doc.parent and doc.parentfield):
			mrinimitable.throw(_("Parenttype, Parent and Parentfield are required to insert a child record"))

		# inserting a child record
		parent = mrinimitable.get_doc(doc.parenttype, doc.parent)
		parent.append(doc.parentfield, doc)
		parent.save()
		return parent

	return mrinimitable.get_doc(doc).insert()


def delete_doc(doctype, name):
	"""Deletes document
	if doctype is a child table, then deletes the child record using the parent doc
	so that the parent doc's `on_update` is called
	"""

	if mrinimitable.is_table(doctype):
		values = mrinimitable.db.get_value(doctype, name, ["parenttype", "parent", "parentfield"])
		if not values:
			raise mrinimitable.DoesNotExistError(doctype=doctype)

		parenttype, parent, parentfield = values
		parent = mrinimitable.get_doc(parenttype, parent)
		if not parent.has_permission("write"):
			raise mrinimitable.DoesNotExistError(doctype=doctype)

		for row in parent.get(parentfield):
			if row.name == name:
				parent.remove(row)
				parent.save()
				break
	else:
		mrinimitable.delete_doc(doctype, name, ignore_missing=False)
