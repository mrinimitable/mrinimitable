# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""
Create a new document with defaults set
"""

import copy

import mrinimitable
import mrinimitable.defaults
from mrinimitable.core.doctype.user_permission.user_permission import get_user_permissions
from mrinimitable.model import data_fieldtypes
from mrinimitable.permissions import filter_allowed_docs_for_doctype
from mrinimitable.utils import cstr, now_datetime, nowdate, nowtime


def get_new_doc(doctype, parent_doc=None, parentfield=None, as_dict=False):
	if doctype not in mrinimitable.local.new_doc_templates:
		# cache a copy of new doc as it is called
		# frequently for inserts
		mrinimitable.local.new_doc_templates[doctype] = make_new_doc(doctype)

	doc = copy.deepcopy(mrinimitable.local.new_doc_templates[doctype])

	set_dynamic_default_values(doc, parent_doc, parentfield)

	if as_dict:
		return doc
	else:
		return mrinimitable.get_doc(doc)


def make_new_doc(doctype):
	doc = mrinimitable.get_doc({"doctype": doctype, "__islocal": 1, "owner": mrinimitable.session.user, "docstatus": 0})

	set_user_and_static_default_values(doc)

	doc._fix_numeric_types()
	doc = doc.get_valid_dict(sanitize=False)
	doc["doctype"] = doctype
	doc["__islocal"] = 1

	if not getattr(doc.meta, "issingle", False):
		doc["__unsaved"] = 1

	return doc


def set_user_and_static_default_values(doc):
	user_permissions = get_user_permissions()
	defaults = mrinimitable.defaults.get_defaults()

	for df in doc.meta.get("fields"):
		if df.fieldtype in data_fieldtypes:
			# user permissions for link options
			doctype_user_permissions = user_permissions.get(df.options, [])
			# Allowed records for the reference doctype (link field) along with default doc
			allowed_records, default_doc = filter_allowed_docs_for_doctype(
				doctype_user_permissions, df.parent, with_default_doc=True
			)

			user_default_value = get_user_default_value(
				df, defaults, doctype_user_permissions, allowed_records, default_doc
			)
			if user_default_value is not None:
				# if fieldtype is link check if doc exists
				if df.fieldtype != "Link" or mrinimitable.db.exists(df.options, user_default_value, cache=True):
					doc.set(df.fieldname, user_default_value)

			else:
				if df.fieldname != doc.meta.title_field:
					static_default_value = get_static_default_value(
						df, doctype_user_permissions, allowed_records
					)
					if static_default_value is not None:
						doc.set(df.fieldname, static_default_value)


def get_user_default_value(df, defaults, doctype_user_permissions, allowed_records, default_doc):
	# don't set defaults for "User" link field using User Permissions!
	if df.fieldtype == "Link" and df.options != "User":
		# If user permission has Is Default enabled or single-user permission has found against respective doctype.
		if not df.ignore_user_permissions and default_doc:
			return default_doc

		# 2 - Look in user defaults
		user_default = defaults.get(df.fieldname)

		allowed_by_user_permission = validate_value_via_user_permissions(
			df, doctype_user_permissions, allowed_records, user_default=user_default
		)

		# is this user default also allowed as per user permissions?
		if user_default and allowed_by_user_permission:
			return user_default


def get_static_default_value(df, doctype_user_permissions, allowed_records):
	# 3 - look in default of docfield
	if df.get("default"):
		if df.default == "__user":
			return mrinimitable.session.user

		elif df.default == "Today":
			return nowdate()

		elif not cstr(df.default).startswith(":"):
			# a simple default value
			is_allowed_default_value = validate_value_via_user_permissions(
				df, doctype_user_permissions, allowed_records
			)

			if df.fieldtype != "Link" or df.options == "User" or is_allowed_default_value:
				return df.default

	elif df.fieldtype == "Select" and df.options and df.options not in ("[Select]", "Loading..."):
		return df.options.split("\n", 1)[0]


def validate_value_via_user_permissions(df, doctype_user_permissions, allowed_records, user_default=None):
	is_valid = True
	# If User Permission exists and allowed records is empty,
	# that means there are User Perms, but none applicable to this new doctype.

	if user_permissions_exist(df, doctype_user_permissions) and allowed_records:
		# If allowed records is not empty,
		# check if this field value is allowed via User Permissions applied to this doctype.
		value = user_default if user_default else df.default
		is_valid = value in allowed_records

	return is_valid


def set_dynamic_default_values(doc, parent_doc, parentfield):
	# these values should not be cached
	user_permissions = get_user_permissions()

	for df in mrinimitable.get_meta(doc["doctype"]).get("fields"):
		if df.get("default"):
			if cstr(df.default).startswith(":"):
				default_value = get_default_based_on_another_field(df, user_permissions, parent_doc)
				if default_value is not None and not doc.get(df.fieldname):
					doc[df.fieldname] = default_value

			elif df.fieldtype == "Datetime" and df.default.lower() == "now":
				doc[df.fieldname] = now_datetime()

		if df.fieldtype == "Time":
			doc[df.fieldname] = nowtime()

	if parent_doc:
		doc["parent"] = parent_doc.name
		doc["parenttype"] = parent_doc.doctype

	if parentfield:
		doc["parentfield"] = parentfield


def user_permissions_exist(df, doctype_user_permissions):
	return (
		df.fieldtype == "Link"
		and not getattr(df, "ignore_user_permissions", False)
		and doctype_user_permissions
	)


def get_default_based_on_another_field(df, user_permissions, parent_doc):
	# default value based on another document
	from mrinimitable.permissions import get_allowed_docs_for_doctype

	ref_doctype = df.default[1:]
	ref_fieldname = ref_doctype.lower().replace(" ", "_")
	reference_name = parent_doc.get(ref_fieldname) if parent_doc else mrinimitable.db.get_default(ref_fieldname)
	default_value = mrinimitable.db.get_value(ref_doctype, reference_name, df.fieldname)
	is_allowed_default_value = not user_permissions_exist(df, user_permissions.get(df.options)) or (
		default_value in get_allowed_docs_for_doctype(user_permissions[df.options], df.parent)
	)

	# is this allowed as per user permissions
	if is_allowed_default_value:
		return default_value
