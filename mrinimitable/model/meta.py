# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# metadata

"""
Load metadata (DocType) class

Example:

	meta = mrinimitable.get_meta('User')
	if meta.has_field('first_name'):
		print("DocType" table has field "first_name")


"""

import json
import os
import typing
from datetime import datetime

import click

import mrinimitable
from mrinimitable import _, _lt
from mrinimitable.model import (
	NO_VALUE_FIELDS,
	child_table_fields,
	data_fieldtypes,
	default_fields,
	optional_fields,
	table_fields,
)
from mrinimitable.model.base_document import (
	DOCTYPE_TABLE_FIELDS,
	TABLE_DOCTYPES_FOR_DOCTYPE,
	BaseDocument,
)
from mrinimitable.model.document import Document
from mrinimitable.model.utils import is_single_doctype
from mrinimitable.model.workflow import get_workflow_name
from mrinimitable.modules import load_doctype_module
from mrinimitable.utils import cached_property, cast, cint, cstr
from mrinimitable.utils.caching import site_cache
from mrinimitable.utils.data import add_to_date, get_datetime

ListOrTuple = list | tuple
SerializableTypes = str | int | float | datetime

DEFAULT_FIELD_LABELS = {
	"name": _lt("ID"),
	"creation": _lt("Created On"),
	"docstatus": _lt("Document Status"),
	"idx": _lt("Index"),
	"modified": _lt("Last Updated On"),
	"modified_by": _lt("Last Updated By"),
	"owner": _lt("Created By"),
	"_user_tags": _lt("Tags"),
	"_liked_by": _lt("Liked By"),
	"_comments": _lt("Comments"),
	"_assign": _lt("Assigned To"),
}

# When number of rows in a table exceeds this number, we disable certain features automatically.
# This is done to avoid hammering the site with unnecessary requests that are just meant for
# improving UX.
LARGE_TABLE_SIZE_THRESHOLD = 100_000
LARGE_TABLE_RECENCY_THRESHOLD = 30  # days


def get_meta(doctype: "str | DocType", cached: bool = True) -> "_Meta":
	"""Get metadata for a doctype.

	Args:
	    doctype: The doctype as a string object.
	    cached: Whether to use cached metadata (default: True).

	Returns:
	    Meta object for the given doctype.
	"""
	if (
		cached
		and isinstance(doctype, str)
		and (meta := mrinimitable.client_cache.get_value(f"doctype_meta::{doctype}"))
	):
		return meta

	meta = Meta(doctype)
	key = f"doctype_meta::{meta.name}"
	mrinimitable.client_cache.set_value(key, meta)
	return meta


def clear_meta_cache(doctype: str = "*"):
	key = f"doctype_meta::{doctype}"
	if doctype == "*":
		mrinimitable.client_cache.delete_keys(key)
	else:
		mrinimitable.client_cache.delete_value(key)


def load_meta(doctype):
	return Meta(doctype)


def get_table_columns(doctype):
	return mrinimitable.db.get_table_columns(doctype)


def load_doctype_from_file(doctype):
	fname = mrinimitable.scrub(doctype)
	with open(mrinimitable.get_app_path("mrinimitable", "core", "doctype", fname, fname + ".json")) as f:
		txt = json.loads(f.read())

	for d in txt.get("fields", []):
		d["doctype"] = "DocField"

	for d in txt.get("permissions", []):
		d["doctype"] = "DocPerm"

	txt["fields"] = [BaseDocument(d) for d in txt["fields"]]
	if "permissions" in txt:
		txt["permissions"] = [BaseDocument(d) for d in txt["permissions"]]

	return txt


class Meta(Document):
	_metaclass = True
	default_fields = list(default_fields)[1:]
	special_doctypes = frozenset(
		(
			"DocField",
			"DocPerm",
			"DocType",
			"Module Def",
			"DocType Action",
			"DocType Link",
			"DocType State",
		)
	)
	standard_set_once_fields = (
		mrinimitable._dict(fieldname="creation", fieldtype="Datetime"),
		mrinimitable._dict(fieldname="owner", fieldtype="Data"),
	)

	def __init__(self, doctype: "str | DocType"):
		if isinstance(doctype, Document):
			super().__init__(doctype.as_dict())
		else:
			super().__init__("DocType", doctype)

		self.process()

	def load_from_db(self):
		try:
			super().load_from_db()
		except mrinimitable.DoesNotExistError:
			if self.doctype == "DocType" and self.name in self.special_doctypes:
				self.__dict__.update(load_doctype_from_file(self.name))
			else:
				raise

	def process(self):
		# don't process for special doctypes
		# prevents circular dependency
		if self.name in self.special_doctypes:
			self.init_field_caches()
			return

		self.add_custom_fields()
		self.apply_property_setters()
		self.init_field_caches()
		self.sort_fields()
		self.get_valid_columns()
		self.set_custom_permissions()
		self.add_custom_links_and_actions()
		self.check_if_large_table()

	def as_dict(self, no_nulls=False):
		return _serialize(self, no_nulls=no_nulls)

	def get_link_fields(self):
		return self.get("fields", {"fieldtype": "Link", "options": ["!=", "[Select]"]})

	def get_data_fields(self):
		return self.get("fields", {"fieldtype": "Data"})

	def get_phone_fields(self):
		return self.get("fields", {"fieldtype": "Phone"})

	def get_dynamic_link_fields(self):
		return self._dynamic_link_fields

	@cached_property
	def _dynamic_link_fields(self):
		return self.get("fields", {"fieldtype": "Dynamic Link"})

	def get_select_fields(self):
		return self.get("fields", {"fieldtype": "Select", "options": ["not in", ["[Select]", "Loading..."]]})

	def get_image_fields(self):
		return self.get("fields", {"fieldtype": "Attach Image"})

	def get_code_fields(self):
		return self.get("fields", {"fieldtype": "Code"})

	def get_set_only_once_fields(self):
		"""Return fields with `set_only_once` set"""
		return self._set_only_once_fields

	@cached_property
	def _set_only_once_fields(self):
		set_only_once_fields = self.get("fields", {"set_only_once": 1})
		fieldnames = [d.fieldname for d in set_only_once_fields]

		for df in self.standard_set_once_fields:
			if df.fieldname not in fieldnames:
				set_only_once_fields.append(df)

		return set_only_once_fields

	def get_table_fields(self):
		return self._table_fields

	def get_global_search_fields(self):
		"""Return list of fields with `in_global_search` set and `name` if set."""
		fields = self.get("fields", {"in_global_search": 1, "fieldtype": ["not in", NO_VALUE_FIELDS]})
		if getattr(self, "show_name_in_global_search", None):
			fields.append(mrinimitable._dict(fieldtype="Data", fieldname="name", label="Name"))

		return fields

	def get_valid_columns(self) -> list[str]:
		return self._valid_columns

	@cached_property
	def _valid_columns(self):
		table_exists = mrinimitable.db.table_exists(self.name)
		if self.name in self.special_doctypes and table_exists:
			valid_columns = get_table_columns(self.name)
		else:
			valid_columns = self.default_fields + [
				df.fieldname
				for df in self.get("fields")
				if not getattr(df, "is_virtual", False) and df.fieldtype in data_fieldtypes
			]
			if self.istable:
				valid_columns += list(child_table_fields)

		return valid_columns

	def get_valid_fields(self) -> list[str]:
		return self._valid_fields

	@cached_property
	def _valid_fields(self):
		if (mrinimitable.flags.in_install or mrinimitable.flags.in_migrate) and self.name in self.special_doctypes:
			valid_fields = get_table_columns(self.name)
		else:
			valid_fields = self.default_fields + [
				df.fieldname for df in self.get("fields") if df.fieldtype in data_fieldtypes
			]
			if self.istable:
				valid_fields += list(child_table_fields)

		return valid_fields

	def get_field(self, fieldname):
		"""Return docfield from meta."""

		return self._fields.get(fieldname)

	def has_field(self, fieldname):
		"""Return True if fieldname exists."""

		return fieldname in self._fields

	def get_label(self, fieldname):
		"""Return label of the given fieldname."""
		if df := self.get_field(fieldname):
			return df.get("label")

		if fieldname in DEFAULT_FIELD_LABELS:
			return str(DEFAULT_FIELD_LABELS[fieldname])

		return "No Label"

	def get_options(self, fieldname):
		return self.get_field(fieldname).options

	def get_link_doctype(self, fieldname):
		df = self.get_field(fieldname)

		if df.fieldtype == "Link":
			return df.options

		if df.fieldtype == "Dynamic Link":
			return self.get_options(df.options)

	def get_search_fields(self):
		search_fields = self.search_fields or "name"
		search_fields = [d.strip() for d in search_fields.split(",")]
		if "name" not in search_fields:
			search_fields.append("name")

		return search_fields

	def get_fields_to_fetch(self, link_fieldname=None):
		"""Return a list of docfield objects for fields whose values
		are to be fetched and updated for a particular link field.

		These fields are of type Data, Link, Text, Readonly and their
		fetch_from property is set as `link_fieldname`.`source_fieldname`"""

		out = []

		if not link_fieldname:
			link_fields = [df.fieldname for df in self.get_link_fields()]

		for df in self.fields:
			if df.fieldtype not in NO_VALUE_FIELDS and getattr(df, "fetch_from", None):
				if link_fieldname:
					if df.fetch_from.startswith(link_fieldname + "."):
						out.append(df)
				else:
					if "." in df.fetch_from:
						fieldname = df.fetch_from.split(".", 1)[0]
						if fieldname in link_fields:
							out.append(df)

		return out

	def get_list_fields(self):
		list_fields = ["name"] + [
			d.fieldname for d in self.fields if (d.in_list_view and d.fieldtype in data_fieldtypes)
		]
		if self.title_field and self.title_field not in list_fields:
			list_fields.append(self.title_field)
		return list_fields

	def get_custom_fields(self):
		return [d for d in self.fields if getattr(d, "is_custom_field", False)]

	def get_title_field(self):
		"""Return the title field of this doctype,
		explict via `title_field`, or `title` or `name`"""
		title_field = getattr(self, "title_field", None)
		if not title_field and self.has_field("title"):
			title_field = "title"
		if not title_field:
			title_field = "name"

		return title_field

	def get_translatable_fields(self):
		"""Return all fields that are translation enabled"""
		return [d.fieldname for d in self.fields if d.translatable]

	def is_translatable(self, fieldname):
		"""Return true of false given a field"""

		if field := self.get_field(fieldname):
			return field.translatable

	def get_workflow(self):
		return get_workflow_name(self.name)

	def get_naming_series_options(self) -> list[str]:
		"""Get list naming series options."""

		if field := self.get_field("naming_series"):
			options = field.options or ""
			return options.split("\n")

		return []

	def add_custom_fields(self):
		if not mrinimitable.db.table_exists("Custom Field"):
			return

		custom_fields = mrinimitable.db.get_values(
			"Custom Field",
			filters={"dt": self.name},
			fieldname="*",
			as_dict=True,
			order_by="idx",
			update={"is_custom_field": 1},
		)

		if not custom_fields:
			return

		self.extend("fields", custom_fields)

	def apply_property_setters(self):
		"""
		Property Setters are set via Customize Form. They override standard properties
		of the doctype or its child properties like fields, links etc. This method
		applies the customized properties over the standard meta object
		"""
		if not mrinimitable.db.table_exists("Property Setter"):
			return

		property_setters = mrinimitable.db.get_values(
			"Property Setter",
			filters={"doc_type": self.name},
			fieldname="*",
			as_dict=True,
		)

		if not property_setters:
			return

		for ps in property_setters:
			if ps.doctype_or_field == "DocType":
				self.set(ps.property, cast(ps.property_type, ps.value))

			elif ps.doctype_or_field == "DocField":
				for d in self.fields:
					if d.fieldname == ps.field_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

			elif ps.doctype_or_field == "DocType Link":
				for d in self.links:
					if d.name == ps.row_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

			elif ps.doctype_or_field == "DocType Action":
				for d in self.actions:
					if d.name == ps.row_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

			elif ps.doctype_or_field == "DocType State":
				for d in self.states:
					if d.name == ps.row_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

	def add_custom_links_and_actions(self):
		for doctype, fieldname in (
			("DocType Link", "links"),
			("DocType Action", "actions"),
			("DocType State", "states"),
		):
			# ignore_ddl because the `custom` column was added later via a patch
			for d in mrinimitable.get_all(
				doctype, fields="*", filters=dict(parent=self.name, custom=1), ignore_ddl=True
			):
				self.append(fieldname, d)

			# set the fields in order if specified
			# order is saved as `links_order`
			order = json.loads(self.get(f"{fieldname}_order") or "[]")
			if order:
				name_map = {d.name: d for d in self.get(fieldname)}
				new_list = [name_map[name] for name in order if name in name_map]
				# add the missing items that have not be added
				# maybe these items were added to the standard product
				# after the customization was done
				for d in self.get(fieldname):
					if d not in new_list:
						new_list.append(d)

				self.set(fieldname, new_list)

	def check_if_large_table(self):
		"""Apply some heuristics to detect large tables.

		UI code can use this information to adapt accordingly."""
		# Note: `modified` should be used in older versions.
		self.is_large_table = False
		if self.istable or not mrinimitable.db.table_exists(self.name):  # During install, new migrate
			return

		if mrinimitable.db.estimate_count(self.name) > LARGE_TABLE_SIZE_THRESHOLD:
			recent_change = mrinimitable.db.get_value(self.name, {}, "creation", order_by="creation desc")
			if get_datetime(recent_change) > add_to_date(None, days=-1 * LARGE_TABLE_RECENCY_THRESHOLD):
				self.is_large_table = True

	def init_field_caches(self):
		# field map
		self._fields = {field.fieldname: field for field in self.fields}

		# table fields
		if self.name == "DocType":
			self._table_fields = DOCTYPE_TABLE_FIELDS
		else:
			self._table_fields = self.get("fields", {"fieldtype": ["in", table_fields]})

		# table fieldname: doctype map
		self._table_doctypes = {field.fieldname: field.options for field in self._table_fields}

	def sort_fields(self):
		"""
		Sort fields on the basis of following rules (priority descending):
		- `field_order` property setter
		- `insert_after` computed based on default order for standard fields
		- `insert_after` property for custom fields
		"""

		if field_order := getattr(self, "field_order", []):
			field_order = [fieldname for fieldname in json.loads(field_order) if fieldname in self._fields]

			# all fields match, best case scenario
			if len(field_order) == len(self.fields):
				self._update_fields_based_on_order(field_order)
				return

			# if the first few standard fields are not in the field order, prepare to prepend them
			if self.fields[0].fieldname not in field_order:
				fields_to_prepend = []
				standard_field_found = False

				for fieldname, field in self._fields.items():
					if getattr(field, "is_custom_field", False):
						# all custom fields from here on
						break

					if fieldname in field_order:
						standard_field_found = True
						break

					fields_to_prepend.append(fieldname)

				if standard_field_found:
					field_order = fields_to_prepend + field_order
				else:
					# worst case scenario, invalidate field_order
					field_order = fields_to_prepend

		existing_fields = set(field_order) if field_order else False
		insertion_map = {}

		for index, field in enumerate(self.fields):
			if existing_fields and field.fieldname in existing_fields:
				continue

			if not getattr(field, "is_custom_field", False):
				if existing_fields:
					# compute insert_after from previous field
					insertion_map.setdefault(self.fields[index - 1].fieldname, []).append(field.fieldname)
				else:
					field_order.append(field.fieldname)

			elif target_position := getattr(field, "insert_after", None):
				original_target = target_position
				if field.fieldtype in ["Section Break", "Column Break"] and target_position in field_order:
					# Find the next section or column break and set target_position to just one field before
					for current_field in field_order[field_order.index(target_position) + 1 :]:
						if self._fields[current_field].fieldtype == "Section Break" or (
							self._fields[current_field].fieldtype == self._fields[original_target].fieldtype
						):
							# Break out to add this just after the last field
							break
						target_position = current_field
				insertion_map.setdefault(target_position, []).append(field.fieldname)

			else:
				# if custom field is at the top, insert after is None
				field_order.insert(0, field.fieldname)

		if insertion_map:
			_update_field_order_based_on_insert_after(field_order, insertion_map)

		self._update_fields_based_on_order(field_order)

	def _update_fields_based_on_order(self, field_order):
		sorted_fields = []

		for idx, fieldname in enumerate(field_order, 1):
			field = self._fields[fieldname]
			field.idx = idx
			sorted_fields.append(field)

		self.fields = sorted_fields

	def set_custom_permissions(self):
		"""Reset `permissions` with Custom DocPerm if exists"""
		if mrinimitable.flags.in_patch or mrinimitable.flags.in_install:
			return

		if not self.istable and self.name not in ("DocType", "DocField", "DocPerm", "Custom DocPerm"):
			custom_perms = mrinimitable.get_all(
				"Custom DocPerm",
				fields="*",
				filters=dict(parent=self.name),
				update=dict(doctype="Custom DocPerm"),
			)
			if custom_perms:
				self.permissions = [Document(d) for d in custom_perms]

	def get_fieldnames_with_value(self, with_field_meta=False, with_virtual_fields=False):
		def is_value_field(df):
			return (df.fieldtype not in NO_VALUE_FIELDS) and (
				with_virtual_fields or not getattr(df, "is_virtual", False)
			)

		if with_field_meta:
			return [df for df in self.fields if is_value_field(df)]

		return [df.fieldname for df in self.fields if is_value_field(df)]

	def get_fields_to_check_permissions(self, user_permission_doctypes):
		fields = self.get(
			"fields",
			{
				"fieldtype": "Link",
				"parent": self.name,
				"ignore_user_permissions": ("!=", 1),
				"options": ("in", user_permission_doctypes),
			},
		)

		if self.name in user_permission_doctypes:
			fields.append(mrinimitable._dict({"label": "Name", "fieldname": "name", "options": self.name}))

		return fields

	def get_high_permlevel_fields(self):
		"""Build list of fields with high perm level and all the higher perm levels defined."""
		return self.high_permlevel_fields

	@cached_property
	def high_permlevel_fields(self):
		return [df for df in self.fields if df.permlevel > 0]

	def get_permitted_fieldnames(
		self,
		parenttype=None,
		*,
		user=None,
		permission_type="read",
		with_virtual_fields=True,
	):
		"""Build list of `fieldname` with read perm level and all the higher perm levels defined.

		Note: If permissions are not defined for DocType, return all the fields with value.
		"""
		permitted_fieldnames = []

		if self.istable and not parenttype:
			return permitted_fieldnames

		if not permission_type:
			permission_type = "select" if mrinimitable.only_has_select_perm(self.name, user=user) else "read"

		if permission_type == "select":
			return self.get_search_fields()

		if not self.get_permissions(parenttype=parenttype):
			return self.get_fieldnames_with_value()

		permlevel_access = set(
			self.get_permlevel_access(permission_type=permission_type, parenttype=parenttype, user=user)
		)

		if 0 not in permlevel_access and permission_type in ("read", "select"):
			if mrinimitable.share.get_shared(self.name, user, rights=[permission_type], limit=1):
				permlevel_access.add(0)

		permitted_fieldnames.extend(
			df.fieldname
			for df in self.get_fieldnames_with_value(
				with_field_meta=True, with_virtual_fields=with_virtual_fields
			)
			if df.permlevel in permlevel_access
		)
		return permitted_fieldnames

	def get_permlevel_access(self, permission_type="read", parenttype=None, *, user=None):
		has_access_to = []
		roles = set(mrinimitable.get_roles(user))
		for perm in self.get_permissions(parenttype):
			if perm.role in roles and perm.get(permission_type):
				if perm.permlevel not in has_access_to:
					has_access_to.append(perm.permlevel)

		return has_access_to

	def get_permissions(self, parenttype=None):
		if self.istable and parenttype:
			# use parent permissions
			permissions = mrinimitable.get_meta(parenttype).permissions
		else:
			permissions = self.get("permissions", [])

		return permissions

	def get_dashboard_data(self):
		"""Return dashboard setup related to this doctype.

		This method will return the `data` property in the `[doctype]_dashboard.py`
		file in the doctype's folder, along with any overrides or extensions
		implemented in other Mrinimitable applications via hooks.
		"""
		data = mrinimitable._dict()
		if not self.custom:
			try:
				module = load_doctype_module(self.name, suffix="_dashboard")
				if hasattr(module, "get_data"):
					data = mrinimitable._dict(module.get_data())
			except ImportError:
				pass

		self.add_doctype_links(data)

		if not self.custom:
			for hook in mrinimitable.get_hooks("override_doctype_dashboards", {}).get(self.name, []):
				data = mrinimitable._dict(mrinimitable.get_attr(hook)(data=data))

		return data

	def add_doctype_links(self, data):
		"""add `links` child table in standard link dashboard format"""
		dashboard_links = []

		if getattr(self, "links", None):
			dashboard_links.extend(self.links)

		if not data.transactions:
			# init groups
			data.transactions = []

		if not data.non_standard_fieldnames:
			data.non_standard_fieldnames = {}

		if not data.internal_links:
			data.internal_links = {}

		for link in dashboard_links:
			link.added = False
			if link.hidden:
				continue

			for group in data.transactions:
				group = mrinimitable._dict(group)

				# For internal links parent doctype will be the key
				doctype = link.parent_doctype or link.link_doctype
				# group found
				if link.group and _(group.label) == _(link.group):
					if doctype not in group.get("items"):
						group.get("items").append(doctype)
					link.added = True

			if not link.added:
				# group not found, make a new group
				data.transactions.append(
					dict(label=link.group, items=[link.parent_doctype or link.link_doctype])
				)

			if not data.fieldname and link.link_fieldname:
				data.fieldname = link.link_fieldname

			if not link.is_child_table:
				data.non_standard_fieldnames[link.link_doctype] = link.link_fieldname
			elif link.is_child_table:
				data.internal_links[link.parent_doctype] = [link.table_fieldname, link.link_fieldname]

	def get_row_template(self):
		return self.get_web_template(suffix="_row")

	def get_list_template(self):
		return self.get_web_template(suffix="_list")

	def get_web_template(self, suffix=""):
		"""Return the relative path of the row template for this doctype."""
		module_name = mrinimitable.scrub(self.module)
		doctype = mrinimitable.scrub(self.name)
		template_path = mrinimitable.get_module_path(
			module_name, "doctype", doctype, "templates", doctype + suffix + ".html"
		)
		if os.path.exists(template_path):
			return f"{module_name}/doctype/{doctype}/templates/{doctype}{suffix}.html"
		return None

	def is_nested_set(self):
		return self.has_field("lft") and self.has_field("rgt")


#######


def get_parent_dt(dt):
	if not mrinimitable.is_table(dt):
		return ""

	return (
		mrinimitable.db.get_value(
			"DocField",
			{"fieldtype": ("in", mrinimitable.model.table_fields), "options": dt},
			"parent",
		)
		or ""
	)


def set_fieldname(field_id, fieldname):
	mrinimitable.db.set_value("DocField", field_id, "fieldname", fieldname)


def get_field_currency(df, doc=None):
	"""get currency based on DocField options and fieldvalue in doc"""
	currency = None

	if not df.get("options"):
		return None

	if not doc:
		return None

	if not getattr(mrinimitable.local, "field_currency", None):
		mrinimitable.local.field_currency = mrinimitable._dict()

	if not (
		mrinimitable.local.field_currency.get((doc.doctype, doc.name), {}).get(df.fieldname)
		or (
			doc.get("parent")
			and mrinimitable.local.field_currency.get((doc.doctype, doc.parent), {}).get(df.fieldname)
		)
	):
		ref_docname = doc.get("parent") or doc.name

		if ":" in cstr(df.get("options")):
			split_opts = df.get("options").split(":")
			if len(split_opts) == 3 and doc.get(split_opts[1]):
				currency = mrinimitable.get_cached_value(split_opts[0], doc.get(split_opts[1]), split_opts[2])
		else:
			currency = doc.get(df.get("options"))
			if doc.get("parenttype"):
				if currency:
					ref_docname = doc.name
				else:
					if mrinimitable.get_meta(doc.parenttype).has_field(df.get("options")):
						# only get_value if parent has currency field
						currency = mrinimitable.db.get_value(doc.parenttype, doc.parent, df.get("options"))

		if currency:
			mrinimitable.local.field_currency.setdefault((doc.doctype, ref_docname), mrinimitable._dict()).setdefault(
				df.fieldname, currency
			)

	return mrinimitable.local.field_currency.get((doc.doctype, doc.name), {}).get(df.fieldname) or (
		doc.get("parent") and mrinimitable.local.field_currency.get((doc.doctype, doc.parent), {}).get(df.fieldname)
	)


def get_field_precision(df, doc=None, currency=None):
	"""get precision based on DocField options and fieldvalue in doc"""
	from mrinimitable.locale import get_number_format

	if df.precision:
		precision = cint(df.precision)

	elif df.fieldtype == "Currency":
		precision = cint(mrinimitable.db.get_default("currency_precision"))
		if not precision:
			number_format = get_number_format()
			precision = number_format.precision
	else:
		precision = cint(mrinimitable.db.get_default("float_precision")) or 3

	return precision


def get_default_df(fieldname):
	if fieldname in (default_fields + child_table_fields):
		if fieldname in ("creation", "modified"):
			return mrinimitable._dict(fieldname=fieldname, fieldtype="Datetime")

		elif fieldname in ("idx", "docstatus"):
			return mrinimitable._dict(fieldname=fieldname, fieldtype="Int")

		elif fieldname in ("owner", "modified_by"):
			return mrinimitable._dict(fieldname=fieldname, fieldtype="Link", options="User")

		return mrinimitable._dict(fieldname=fieldname, fieldtype="Data")


def trim_tables(doctype=None, dry_run=False, quiet=False):
	"""
	Removes database fields that don't exist in the doctype (json or custom field). This may be needed
	as maintenance since removing a field in a DocType doesn't automatically
	delete the db field.
	"""
	UPDATED_TABLES = {}
	filters = {"issingle": 0, "is_virtual": 0}
	if doctype:
		filters["name"] = doctype

	for doctype in mrinimitable.get_all("DocType", filters=filters, pluck="name"):
		try:
			dropped_columns = trim_table(doctype, dry_run=dry_run)
			if dropped_columns:
				UPDATED_TABLES[doctype] = dropped_columns
		except mrinimitable.db.TableMissingError:
			if quiet:
				continue
			click.secho(f"Ignoring missing table for DocType: {doctype}", fg="yellow", err=True)
			click.secho(f"Consider removing record in the DocType table for {doctype}", fg="yellow", err=True)
		except Exception as e:
			if quiet:
				continue
			click.echo(e, err=True)

	return UPDATED_TABLES


def trim_table(doctype, dry_run=True):
	key = f"table_columns::tab{doctype}"
	mrinimitable.cache.delete_value(key)
	ignore_fields = default_fields + optional_fields + child_table_fields
	columns = mrinimitable.db.get_table_columns(doctype)
	fields = mrinimitable.get_meta(doctype, cached=False).get_fieldnames_with_value()

	def is_internal(field):
		return field not in ignore_fields and not field.startswith("_")

	columns_to_remove = [f for f in list(set(columns) - set(fields)) if is_internal(f)]
	DROPPED_COLUMNS = columns_to_remove[:]

	if columns_to_remove and not dry_run:
		columns_to_remove = ", ".join(f"DROP `{c}`" for c in columns_to_remove)
		mrinimitable.db.sql_ddl(f"ALTER TABLE `tab{doctype}` {columns_to_remove}")

	return DROPPED_COLUMNS


def _update_field_order_based_on_insert_after(field_order, insert_after_map):
	"""Update the field order based on insert_after_map"""

	retry_field_insertion = True

	while retry_field_insertion:
		retry_field_insertion = False

		for fieldname in list(insert_after_map):
			if fieldname not in field_order:
				continue

			custom_field_index = field_order.index(fieldname)
			for custom_field_name in insert_after_map.pop(fieldname):
				custom_field_index += 1
				field_order.insert(custom_field_index, custom_field_name)

			retry_field_insertion = True

	if insert_after_map:
		# insert_after is an invalid fieldname, add these fields to the end
		for fields in insert_after_map.values():
			field_order.extend(fields)


CACHE_PROPERTIES = frozenset(
	(
		"_fields",
		"_table_fields",
		"_table_doctypes",
		*(prop for prop, value in vars(Meta).items() if isinstance(value, cached_property)),
	)
)


def _serialize(doc, no_nulls=False, *, is_child=False):
	out = {}
	for key, value in doc.__dict__.items():
		if not is_child:
			if key in CACHE_PROPERTIES:
				continue

			if isinstance(value, ListOrTuple):
				if value and isinstance(value[0], BaseDocument):
					out[key] = [_serialize(d, no_nulls=no_nulls, is_child=True) for d in value]

				continue

		if (not no_nulls and value is None) or isinstance(value, SerializableTypes):
			out[key] = value

	if not is_child:
		# set empty lists for unset table fields
		for fieldname in TABLE_DOCTYPES_FOR_DOCTYPE:
			if out.get(fieldname) is None:
				out[fieldname] = []

	return out


if typing.TYPE_CHECKING:
	# This is DX hack to add all fields from DocType to meta for autocompletions.
	# Meta is technically doctype + special fields on meta.
	from mrinimitable.core.doctype.doctype.doctype import DocType

	class _Meta(Meta, DocType):
		pass


# backward compatibility
is_single = is_single_doctype
