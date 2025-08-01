# Copyright (c) 2022, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import json
import weakref
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeVar

import mrinimitable
from mrinimitable import _, _dict
from mrinimitable.model import (
	child_table_fields,
	datetime_fields,
	default_fields,
	display_fieldtypes,
	float_like_fields,
	get_permitted_fields,
	table_fields,
)
from mrinimitable.model.docstatus import DocStatus
from mrinimitable.model.dynamic_links import invalidate_distinct_link_doctypes
from mrinimitable.model.naming import set_new_name
from mrinimitable.model.utils.link_count import notify_link_count
from mrinimitable.modules import load_doctype_module
from mrinimitable.utils import (
	cached_property,
	cast_fieldtype,
	cint,
	compare,
	cstr,
	flt,
	is_a_property,
	now,
	sanitize_html,
	strip_html,
)
from mrinimitable.utils.defaults import get_not_null_defaults
from mrinimitable.utils.html_utils import unescape_html

if TYPE_CHECKING:
	from mrinimitable.model.document import Document

D = TypeVar("D", bound="Document")
DatetimeTypes = datetime.date | datetime.datetime | datetime.time | datetime.timedelta


max_positive_value = {"smallint": 2**15 - 1, "int": 2**31 - 1, "bigint": 2**63 - 1}

DOCTYPE_TABLE_FIELDS = [
	_dict(fieldname="fields", options="DocField"),
	_dict(fieldname="permissions", options="DocPerm"),
	_dict(fieldname="actions", options="DocType Action"),
	_dict(fieldname="links", options="DocType Link"),
	_dict(fieldname="states", options="DocType State"),
]

TABLE_DOCTYPES_FOR_DOCTYPE = MappingProxyType({df["fieldname"]: df["options"] for df in DOCTYPE_TABLE_FIELDS})

# child tables cannot have child tables
TABLE_DOCTYPES_FOR_CHILD_TABLES = MappingProxyType({})

DOCTYPES_FOR_DOCTYPE = {"DocType", *TABLE_DOCTYPES_FOR_DOCTYPE.values()}

UNPICKLABLE_KEYS = (
	"meta",
	"permitted_fieldnames",
	"_parent_doc",
	"_weakref",
	"_table_fieldnames",
)


def get_controller(doctype):
	"""Return the locally cached **class** object of the given DocType.

	For `custom` type, return `mrinimitable.model.document.Document`.

	:param doctype: DocType name as string.
	"""

	site_controllers = mrinimitable.controllers.setdefault(mrinimitable.local.site, {})
	if doctype not in site_controllers:
		site_controllers[doctype] = import_controller(doctype)

	return site_controllers[doctype]


def import_controller(doctype):
	from mrinimitable.model.document import Document
	from mrinimitable.utils.nestedset import NestedSet

	module_name = "Core"
	if doctype not in DOCTYPES_FOR_DOCTYPE:
		doctype_info = mrinimitable.db.get_value("DocType", doctype, ("module", "custom", "is_tree"), as_dict=True)
		if doctype_info:
			if doctype_info.custom:
				return NestedSet if doctype_info.is_tree else Document
			module_name = doctype_info.module

	module_path = None
	class_overrides = mrinimitable.get_hooks("override_doctype_class")

	module = load_doctype_module(doctype, module_name)
	classname = doctype.replace(" ", "").replace("-", "")
	class_ = getattr(module, classname, None)

	if class_overrides and class_overrides.get(doctype):
		import_path = class_overrides[doctype][-1]
		module_path, custom_classname = import_path.rsplit(".", 1)
		custom_module = mrinimitable.get_module(module_path)
		custom_class_ = getattr(custom_module, custom_classname, None)
		if not issubclass(custom_class_, class_):
			original_class_path = mrinimitable.bold(f"{class_.__module__}.{class_.__name__}")
			mrinimitable.throw(
				f"{doctype}: {mrinimitable.bold(import_path)} must be a subclass of {original_class_path}",
				title=_("Invalid Override"),
			)
		class_ = custom_class_

	if class_ is None:
		raise ImportError(
			doctype
			if module_path is None
			else f"{doctype}: {classname} does not exist in module {module_path}"
		)

	if not issubclass(class_, BaseDocument):
		raise ImportError(f"{doctype}: {classname} is not a subclass of BaseDocument")

	return class_


RESERVED_KEYWORDS = frozenset(
	(
		"doctype",
		"meta",
		"flags",
		"_weakref",
		"_parent_doc",
		"_table_fields",
		"_doc_before_save",
		"_table_fieldnames",
		"permitted_fieldnames",
		"dont_update_if_missing",
	)
)


class BaseDocument:
	def __init__(self, d):
		if d.get("doctype"):
			self.doctype = d["doctype"]

		self.update(d)
		self.dont_update_if_missing = []

		if hasattr(self, "__setup__"):
			self.__setup__()

	def __json__(self):
		return self.as_dict(no_nulls=True)

	@cached_property
	def meta(self):
		return mrinimitable.get_meta(self.doctype)

	@cached_property
	def permitted_fieldnames(self) -> set[str]:
		return set(get_permitted_fields(doctype=self.doctype, parenttype=getattr(self, "parenttype", None)))

	@cached_property
	def _weakref(self):
		return weakref.ref(self)

	def __getstate__(self):
		"""Return a copy of `__dict__` excluding unpicklable values like `meta`.

		Called when pickling.
		More info: https://docs.python.org/3/library/pickle.html#handling-stateful-objects
		"""

		# Always use the dict.copy() method to avoid modifying the original state
		state = self.__dict__.copy()
		self.remove_unpicklable_values(state)

		return state

	def remove_unpicklable_values(self, state):
		"""Remove unpicklable values before pickling"""

		for key in UNPICKLABLE_KEYS:
			if key in state:
				del state[key]

	def update(self, d):
		"""Update multiple fields of a doctype using a dictionary of key-value pairs.

		Example:
		        doc.update({
		                "user": "admin",
		                "balance": 42000
		        })

		Developer Note: Logic in the set method is re-implemented here for perf
		"""

		self.__dict__.update(key_val for key_val in d.items() if key_val[0] not in RESERVED_KEYWORDS)
		if not self._table_fieldnames or self.flags.get("ignore_children", False):
			return self

		__dict = self.__dict__
		for key in self._table_fieldnames:
			if key not in __dict:
				continue

			value = __dict[key]
			__dict[key] = []

			if value:
				self.extend(key, value)

		return self

	def update_if_missing(self, d):
		"""Set default values for fields without existing values"""
		if isinstance(d, BaseDocument):
			d = d.get_valid_dict()

		for key, value in d.items():
			if (
				value is not None
				and self.get(key) is None
				# dont_update_if_missing is a list of fieldnames
				# for which you don't want to set default value
				and key not in self.dont_update_if_missing
			):
				self.set(key, value)

	def get_db_value(self, key):
		return mrinimitable.db.get_value(self.doctype, self.name, key)

	def get(self, key, filters=None, limit=None, default=None):
		if isinstance(key, dict):
			return _filter(self.get_all_children(), key, limit=limit)

		if filters:
			if isinstance(filters, dict):
				return _filter(self.__dict__.get(key, []), filters, limit=limit)

			# perhaps you wanted to set a default instead
			default = filters

		value = self.__dict__.get(key, default)

		if limit and isinstance(value, list | tuple) and len(value) > limit:
			value = value[:limit]

		return value

	def getone(self, key, filters=None):
		return self.get(key, filters=filters, limit=1)[0]

	def set(self, key, value, as_value=False):
		if key in RESERVED_KEYWORDS:
			return

		if not as_value and key in self._table_fieldnames:
			self.__dict__[key] = []

			# if value is falsy, just init to an empty list
			if value:
				self.extend(key, value)

			return

		self.__dict__[key] = value

	def delete_key(self, key):
		if key in self.__dict__:
			del self.__dict__[key]

	def append(self, key: str, value: D | dict | None = None, position: int = -1) -> D:
		"""Append an item to a child table.

		Example:
		        doc.append("childtable", {
		                "child_table_field": "value",
		                "child_table_int_field": 0,
		                ...
		        })
		"""
		if value is None:
			value = {}

		if (table := self.__dict__.get(key)) is None:
			self.__dict__[key] = table = []

		d = self._init_child(value, key)

		if position == -1:
			table.append(d)

			if not getattr(d, "idx", False):
				d.idx = len(table)
		else:
			# insert at specific position
			table.insert(position, d)

			# re number idx
			for i, _d in enumerate(table, 1):
				_d.idx = i

		# reference parent document but with weak reference, parent_doc will be deleted if self is garbage collected.
		d._parent_doc = self._weakref

		return d

	@property
	def parent_doc(self):
		parent_doc_ref = getattr(self, "_parent_doc", None)

		if isinstance(parent_doc_ref, weakref.ReferenceType):
			return parent_doc_ref()
		elif isinstance(parent_doc_ref, BaseDocument):
			return parent_doc_ref

	@parent_doc.setter
	def parent_doc(self, value):
		self._parent_doc = value

	@parent_doc.deleter
	def parent_doc(self):
		self._parent_doc = None

	def extend(self, key, value):
		try:
			value = iter(value)
		except TypeError:
			raise ValueError

		for v in value:
			self.append(key, v)

	def remove(self, doc):
		"""Usage: from the parent doc, pass the child table doc to remove that child doc from the
		child table, thus removing it from the parent doc
		"""
		if doc.get("parentfield"):
			self.get(doc.parentfield).remove(doc)

			# re-number idx
			for i, _d in enumerate(self.get(doc.parentfield)):
				_d.idx = i + 1

	def _init_child(self, value, key):
		if isinstance(value, BaseDocument):
			child = value
		else:
			doctype = self._table_fieldnames.get(key)
			if not doctype:
				raise AttributeError(key)

			value["doctype"] = doctype
			controller = get_controller(doctype)
			child = controller.__new__(controller)
			child._table_fieldnames = TABLE_DOCTYPES_FOR_CHILD_TABLES
			child.__init__(value)

		__dict = child.__dict__
		__dict["parent"] = self.name
		__dict["parenttype"] = self.doctype
		__dict["parentfield"] = key

		if __dict.get("docstatus") is None:
			__dict["docstatus"] = DocStatus.DRAFT

		if not __dict.get("name"):
			__dict["__islocal"] = 1
			__dict["__temporary_name"] = mrinimitable.generate_hash(length=10)

		return child

	@cached_property
	def _table_fieldnames(self) -> dict:
		if self.doctype == "DocType":
			return TABLE_DOCTYPES_FOR_DOCTYPE

		if self.doctype in DOCTYPES_FOR_DOCTYPE:
			return TABLE_DOCTYPES_FOR_CHILD_TABLES

		return self.meta._table_doctypes

	def _get_table_fields(self):
		"""
		To get table fields during Document init
		Meta.get_table_fields goes into recursion for special doctypes
		"""

		if self.doctype == "DocType":
			return DOCTYPE_TABLE_FIELDS

		# child tables don't have child tables
		if self.doctype in DOCTYPES_FOR_DOCTYPE:
			return ()

		return self.meta.get_table_fields()

	def get_valid_dict(
		self, sanitize=True, convert_dates_to_str=False, ignore_nulls=False, ignore_virtual=False
	) -> _dict:
		d = _dict()
		field_values = self.__dict__
		field_map = self.meta._fields

		for fieldname in self.meta.get_valid_fields():
			value = field_values.get(fieldname)

			# if no need for sanitization and value is None, continue
			if not sanitize and value is None:
				d[fieldname] = None
				continue

			df = field_map.get(fieldname)
			is_virtual_field = getattr(df, "is_virtual", False)

			if df:
				if is_virtual_field:
					if ignore_virtual or fieldname not in self.permitted_fieldnames:
						continue

					if (prop := getattr(type(self), fieldname, None)) and is_a_property(prop):
						value = getattr(self, fieldname)

					elif options := getattr(df, "options", None):
						from mrinimitable.utils.safe_exec import get_safe_globals

						value = mrinimitable.safe_eval(
							code=options,
							eval_globals=get_safe_globals(),
							eval_locals={"doc": self},
						)

				fieldtype = df.fieldtype
				if isinstance(value, list) and fieldtype not in table_fields:
					mrinimitable.throw(_("Value for {0} cannot be a list").format(_(df.label, context=df.parent)))

				if fieldtype == "Check":
					value = 1 if cint(value) else 0

				elif fieldtype == "Int" and not isinstance(value, int):
					value = cint(value)

				elif fieldtype == "JSON" and isinstance(value, dict):
					value = json.dumps(value, separators=(",", ":"))

				elif fieldtype in float_like_fields and not isinstance(value, float):
					value = flt(value)

				elif (fieldtype in datetime_fields and value == "") or (
					getattr(df, "unique", False) and cstr(value).strip() == ""
				):
					value = None

			if convert_dates_to_str and isinstance(value, DatetimeTypes):
				value = str(value)

			if ignore_nulls and not is_virtual_field and value is None:
				continue

			# If the docfield is not nullable - set a default non-null value
			if value is None and getattr(df, "not_nullable", False):
				if df.default:
					value = df.default
				else:
					value = get_not_null_defaults(df.fieldtype)

			d[fieldname] = value

		return d

	def init_child_tables(self):
		"""
		This is needed so that one can loop over child table properties
		without worrying about whether or not they have values
		"""

		if not self._table_fieldnames:
			return

		__dict = self.__dict__

		for fieldname in self._table_fieldnames:
			if __dict.get(fieldname) is None:
				__dict[fieldname] = []

	def init_valid_columns(self):
		__dict = self.__dict__

		if __dict.get("docstatus") is None:
			__dict["docstatus"] = DocStatus.DRAFT

		if __dict.get("idx") is None:
			__dict["idx"] = 0

		for key in self.get_valid_columns():
			if key not in __dict:
				__dict[key] = None

	def get_valid_columns(self) -> list[str]:
		valid_columns_cache = mrinimitable.local.valid_columns

		if self.doctype not in valid_columns_cache:
			if self.doctype in DOCTYPES_FOR_DOCTYPE:
				from mrinimitable.model.meta import get_table_columns

				valid = get_table_columns(self.doctype)
			else:
				valid = self.meta.get_valid_columns()

			valid_columns_cache[self.doctype] = valid

		return valid_columns_cache[self.doctype]

	def is_new(self) -> bool:
		return self.get("__islocal")

	@property
	def docstatus(self) -> DocStatus:
		value = self.__dict__.get("docstatus")

		if not isinstance(value, DocStatus):
			value = DocStatus(value or 0)
			self.__dict__["docstatus"] = value

		return value

	@docstatus.setter
	def docstatus(self, value) -> None:
		if not isinstance(value, DocStatus):
			value = DocStatus(value or 0)

		self.__dict__["docstatus"] = value

	def as_dict(
		self,
		no_nulls=False,
		no_default_fields=False,
		convert_dates_to_str=False,
		no_child_table_fields=False,
		no_private_properties=False,
	) -> dict:
		doc = self.get_valid_dict(convert_dates_to_str=convert_dates_to_str, ignore_nulls=no_nulls)
		doc["doctype"] = self.doctype

		for fieldname in self._table_fieldnames:
			children = self.get(fieldname) or []
			doc[fieldname] = [
				d.as_dict(
					convert_dates_to_str=convert_dates_to_str,
					no_nulls=no_nulls,
					no_default_fields=no_default_fields,
					no_child_table_fields=no_child_table_fields,
					no_private_properties=no_private_properties,
				)
				for d in children
			]

		if no_default_fields:
			for key in default_fields:
				if key in doc:
					del doc[key]

		if no_child_table_fields:
			for key in child_table_fields:
				if key in doc:
					del doc[key]

		if not no_private_properties:
			for key in (
				"_user_tags",
				"__islocal",
				"__onload",
				"_liked_by",
				"__run_link_triggers",
				"__unsaved",
			):
				if value := getattr(self, key, None):
					doc[key] = value

		return doc

	def as_json(self):
		return mrinimitable.as_json(self.as_dict())

	def get_table_field_doctype(self, fieldname):
		return self._table_fieldnames.get(fieldname)

	def get_parentfield_of_doctype(self, doctype):
		return next(
			(
				fieldname
				for fieldname, child_doctype in self._table_fieldnames.items()
				if child_doctype == doctype
			),
			None,
		)

	def db_insert(self, ignore_if_duplicate=False):
		"""INSERT the document (with valid columns) in the database.

		args:
		        ignore_if_duplicate: ignore primary key collision
		                                        at database level (postgres)
		                                        in python (mariadb)
		"""
		if not self.name:
			# name will be set by document class in most cases
			set_new_name(self)

		conflict_handler = ""
		# On postgres we can't implcitly ignore PK collision
		# So instruct pg to ignore `name` field conflicts
		if ignore_if_duplicate and mrinimitable.db.db_type == "postgres":
			conflict_handler = "on conflict (name) do nothing"

		if not self.creation:
			self.creation = self.modified = now()
			self.owner = self.modified_by = mrinimitable.session.user

		# if doctype is "DocType", don't insert null values as we don't know who is valid yet
		d = self.get_valid_dict(
			convert_dates_to_str=True,
			ignore_nulls=self.doctype in DOCTYPES_FOR_DOCTYPE,
			ignore_virtual=True,
		)

		columns = list(d)
		try:
			mrinimitable.db.sql(
				"""INSERT INTO `tab{doctype}` ({columns})
					VALUES ({values}) {conflict_handler}""".format(
					doctype=self.doctype,
					columns=", ".join("`" + c + "`" for c in columns),
					values=", ".join(["%s"] * len(columns)),
					conflict_handler=conflict_handler,
				),
				list(d.values()),
			)
		except Exception as e:
			if mrinimitable.db.is_primary_key_violation(e):
				if self.meta.autoname == "hash":
					# hash collision? try again
					self.flags.retry_count = (self.flags.retry_count or 0) + 1
					if self.flags.retry_count > 5:
						raise
					self.name = None
					self.db_insert()
					return

				if not ignore_if_duplicate:
					mrinimitable.msgprint(
						_("{0} {1} already exists").format(_(self.doctype), mrinimitable.bold(self.name)),
						title=_("Duplicate Name"),
						indicator="red",
					)
					raise mrinimitable.DuplicateEntryError(self.doctype, self.name, e)

			elif mrinimitable.db.is_unique_key_violation(e):
				# unique constraint
				self.show_unique_validation_message(e)

			else:
				raise

		self.set("__islocal", False)

	def db_update(self):
		if self.get("__islocal") or not self.name:
			self.db_insert()
			return

		d = self.get_valid_dict(
			convert_dates_to_str=True,
			ignore_nulls=self.doctype in DOCTYPES_FOR_DOCTYPE,
			ignore_virtual=True,
		)

		# don't update name, as case might've been changed
		name = cstr(d["name"])
		del d["name"]

		columns = list(d)

		try:
			mrinimitable.db.sql(
				"""UPDATE `tab{doctype}`
				SET {values} WHERE `name`=%s""".format(
					doctype=self.doctype, values=", ".join("`" + c + "`=%s" for c in columns)
				),
				[*list(d.values()), name],
			)
		except Exception as e:
			if mrinimitable.db.is_unique_key_violation(e):
				self.show_unique_validation_message(e)
			else:
				raise

	def db_update_all(self):
		"""Raw update parent + children
		DOES NOT VALIDATE AND CALL TRIGGERS"""
		self.db_update()
		for fieldname in self._table_fieldnames:
			for doc in self.get(fieldname):
				doc.db_update()

	def show_unique_validation_message(self, e):
		if mrinimitable.db.db_type == "mariadb":
			fieldname = str(e).split("'")[-2]
			label = None

			# MariaDB gives key_name in error. Extracting fieldname from key name
			try:
				fieldname = self.get_field_name_by_key_name(fieldname)
			except IndexError:
				pass

			label = self.get_label_from_fieldname(fieldname)

			mrinimitable.msgprint(_("{0} must be unique").format(label or fieldname))

		# this is used to preserve traceback
		raise mrinimitable.UniqueValidationError(self.doctype, self.name, e)

	def get_field_name_by_key_name(self, key_name):
		"""MariaDB stores a mapping between `key_name` and `column_name`.
		Return the `column_name` associated with the `key_name` passed.

		Args:
		        key_name (str): The name of the database index.

		Raises:
		        IndexError: If the key is not found in the table.

		Return:
		        str: The column name associated with the key.
		"""
		return mrinimitable.db.sql(
			f"""
			SHOW
				INDEX
			FROM
				`tab{self.doctype}`
			WHERE
				key_name=%s
			AND
				Non_unique=0
			""",
			key_name,
			as_dict=True,
		)[0].get("Column_name")

	def get_label_from_fieldname(self, fieldname):
		"""Return the associated label for fieldname.

		Args:
		        fieldname (str): The fieldname in the DocType to use to pull the label.

		Return:
		        str: The label associated with the fieldname, if found, otherwise `None`.
		"""
		df = self.meta.get_field(fieldname)
		if df:
			return _(df.label) if df.label else None

	def update_modified(self):
		"""Update modified timestamp"""
		self.set("modified", now())
		if getattr(self.meta, "issingle", False):
			mrinimitable.db.set_single_value(self.doctype, "modified", self.modified, update_modified=False)
		else:
			mrinimitable.db.set_value(self.doctype, self.name, "modified", self.modified, update_modified=False)

	def _fix_numeric_types(self):
		for df in self.meta.get("fields"):
			if df.fieldtype == "Check":
				self.set(df.fieldname, cint(self.get(df.fieldname)))

			elif self.get(df.fieldname) is not None:
				if df.fieldtype == "Int":
					self.set(df.fieldname, cint(self.get(df.fieldname)))

				elif df.fieldtype in ("Float", "Currency", "Percent"):
					self.set(df.fieldname, flt(self.get(df.fieldname)))

		# calling the docstatus property does the job
		self.docstatus

	def _get_missing_mandatory_fields(self):
		"""Get mandatory fields that do not have any values"""

		def get_msg(df):
			if df.fieldtype in table_fields:
				return _("Error: Data missing in table {0}").format(_(df.label, context=df.parent))

			# check if parentfield exists (only applicable for child table doctype)
			elif self.get("parentfield"):
				return _("Error: {0} Row #{1}: Value missing for: {2}").format(
					mrinimitable.bold(_(self.doctype)),
					self.idx,
					_(df.label, context=df.parent),
				)

			return _("Error: Value missing for {0}: {1}").format(_(df.parent), _(df.label, context=df.parent))

		def has_content(df):
			value = cstr(self.get(df.fieldname))
			has_text_content = strip_html(value).strip()
			has_img_tag = "<img" in value
			has_text_or_img_tag = has_text_content or has_img_tag

			if df.fieldtype == "Text Editor" and has_text_or_img_tag:
				return True
			elif df.fieldtype == "Code" and df.options == "HTML" and has_text_or_img_tag:
				return True
			elif df.fieldtype == "Check":
				return True  # Checkboxes can't be mandatory, they're 0 by default
			else:
				return has_text_content

		missing = []

		for df in self.meta.get("fields", {"reqd": ("=", 1)}):
			if self.get(df.fieldname) in (None, []) or not has_content(df):
				missing.append((df.fieldname, get_msg(df)))

		# check for missing parent and parenttype
		if self.meta.istable:
			for fieldname in ("parent", "parenttype"):
				if not self.get(fieldname):
					missing.append((fieldname, get_msg(_dict(label=fieldname))))

		return missing

	def get_invalid_links(self, is_submittable=False):
		"""Return list of invalid links and also update fetch values if not set."""

		is_submittable = is_submittable or self.meta.is_submittable

		def get_msg(df, docname):
			# check if parentfield exists (only applicable for child table doctype)
			if self.get("parentfield"):
				return "{} #{}: {}: {}".format(_("Row"), self.idx, _(df.label, context=df.parent), docname)

			return f"{_(df.label, context=df.parent)}: {docname}"

		invalid_links = []
		cancelled_links = []

		for df in self.meta.get_link_fields() + self.meta.get("fields", {"fieldtype": ("=", "Dynamic Link")}):
			docname = self.get(df.fieldname)
			if not docname:
				continue

			assert isinstance(docname, str | int) or (
				isinstance(docname, list | tuple | set) and len(docname) == 1
			), f"Unexpected value for field {df.fieldname}: {docname}"

			if df.fieldtype == "Link":
				doctype = df.options
				if not doctype:
					mrinimitable.throw(_("Options not set for link field {0}").format(df.fieldname))
			else:
				assert df.fieldtype == "Dynamic Link"
				doctype = self.get(df.options)
				if not doctype:
					mrinimitable.throw(_("{0} must be set first").format(_(self.meta.get_label(df.options))))
				invalidate_distinct_link_doctypes(df.parent, df.options, doctype)

			meta = mrinimitable.get_meta(doctype)
			if not meta.istable:
				notify_link_count(doctype, docname)

			check_docstatus = is_submittable and mrinimitable.get_meta(doctype).is_submittable

			# get a map of values ot fetch along with this link query
			# that are mapped as link_fieldname.source_fieldname in Options of
			# Readonly or Data or Text type fields
			fields_to_fetch = [
				_df
				for _df in self.meta.get_fields_to_fetch(df.fieldname)
				if not _df.get("fetch_if_empty")
				or (_df.get("fetch_if_empty") and not self.get(_df.fieldname))
			]
			values_to_fetch = (
				"name",
				*(_df.fetch_from.split(".")[-1] for _df in fields_to_fetch),
			)
			if check_docstatus:
				values_to_fetch += ("docstatus",)

			if not meta.get("is_virtual"):
				values = mrinimitable.db.get_value(
					doctype, docname, values_to_fetch, as_dict=True, cache=True, order_by=None
				)
				if not values:  # NOTE: DB Value cache does negative caching, which is hard to remove now.
					values = mrinimitable.db.get_value(
						doctype, docname, values_to_fetch, as_dict=True, order_by=None
					)
			else:
				values = mrinimitable.get_doc(doctype, docname).as_dict()

			# fallback to dict with field_to_fetch=None if link field value is not found
			# (for compatibility, `values` must have same data type)
			values = values or _dict.fromkeys(values_to_fetch, None)

			if getattr(meta, "issingle", 0):
				values.name = doctype

			if not df.get("is_virtual"):
				# MySQL is case insensitive. Preserve case of the original docname in the Link Field.
				setattr(self, df.fieldname, values.name)

			for _df in fields_to_fetch:
				if self.is_new() or not self.docstatus.is_submitted() or _df.allow_on_submit:
					self.set_fetch_from_value(doctype, _df, values)

			if not values.name:
				invalid_links.append((df.fieldname, docname, get_msg(df, docname)))

			elif (
				df.fieldname != "amended_from"
				and check_docstatus
				and DocStatus(values.docstatus or 0).is_cancelled()
			):
				cancelled_links.append((df.fieldname, docname, get_msg(df, docname)))

		return invalid_links, cancelled_links

	def set_fetch_from_value(self, doctype, df, values):
		fetch_from_fieldname = df.fetch_from.split(".")[-1]
		value = values[fetch_from_fieldname]
		if df.fieldtype in ["Small Text", "Text", "Data"]:
			from mrinimitable.model.meta import get_default_df

			fetch_from_df = get_default_df(fetch_from_fieldname) or mrinimitable.get_meta(doctype).get_field(
				fetch_from_fieldname
			)

			if not fetch_from_df:
				mrinimitable.throw(
					_('Please check the value of "Fetch From" set for field {0}').format(
						mrinimitable.bold(df.label)
					),
					title=_("Wrong Fetch From value"),
				)

			fetch_from_ft = fetch_from_df.get("fieldtype")
			if fetch_from_ft == "Text Editor" and value:
				value = unescape_html(strip_html(value))
		setattr(self, df.fieldname, value)

	def _validate_selects(self):
		if mrinimitable.flags.in_import:
			return

		for df in self.meta.get_select_fields():
			if df.fieldname == "naming_series" or not self.get(df.fieldname) or not df.options:
				continue

			options = (df.options or "").split("\n")

			# if only empty options
			if not filter(None, options):
				continue

			# strip and set
			self.set(df.fieldname, cstr(self.get(df.fieldname)).strip())
			value = self.get(df.fieldname)

			if value not in options and not (mrinimitable.in_test and value.startswith("_T-")):
				# show an elaborate message
				prefix = _("Row #{0}:").format(self.idx) if self.get("parentfield") else ""
				label = _(self.meta.get_label(df.fieldname))
				comma_options = '", "'.join(_(each) for each in options)

				mrinimitable.throw(
					_('{0} {1} cannot be "{2}". It should be one of "{3}"').format(
						prefix, label, value, comma_options
					)
				)

	def _validate_data_fields(self):
		from mrinimitable.utils import (
			split_emails,
			validate_email_address,
			validate_name,
			validate_phone_number,
			validate_phone_number_with_country_code,
			validate_url,
		)

		for phone_field in self.meta.get_phone_fields():
			phone = self.get(phone_field.fieldname)
			validate_phone_number_with_country_code(phone, phone_field.fieldname)

		# data_field options defined in mrinimitable.model.data_field_options
		for data_field in self.meta.get_data_fields():
			data = self.get(data_field.fieldname)
			if not data:
				continue

			data_field_options = data_field.get("options")
			old_fieldtype = data_field.get("oldfieldtype")

			if old_fieldtype and old_fieldtype != "Data":
				continue

			if data_field_options == "Email":
				if (self.owner in mrinimitable.STANDARD_USERS) and (data in mrinimitable.STANDARD_USERS):
					continue

				for email_address in split_emails(data):
					validate_email_address(email_address, throw=True)

			if data_field_options == "Name":
				validate_name(data, throw=True)

			if data_field_options == "Phone":
				validate_phone_number(data, throw=True)

			if data_field_options == "URL":
				validate_url(data, throw=True)

	def _validate_constants(self):
		if mrinimitable.flags.in_import or self.is_new() or self.flags.ignore_validate_constants:
			return

		constants = [d.fieldname for d in self.meta.get("fields", {"set_only_once": ("=", 1)})]
		if constants:
			values = mrinimitable.db.get_value(self.doctype, self.name, constants, as_dict=True)

		for fieldname in constants:
			df = self.meta.get_field(fieldname)

			# This conversion to string only when fieldtype is Date
			if df.fieldtype == "Date" or df.fieldtype == "Datetime":
				value = str(values.get(fieldname))

			else:
				value = values.get(fieldname)

			if self.get(fieldname) != value:
				mrinimitable.throw(
					_("Value cannot be changed for {0}").format(_(self.meta.get_label(fieldname))),
					mrinimitable.CannotChangeConstantError,
				)

	def _validate_length(self):
		if mrinimitable.flags.in_install:
			return

		if getattr(self.meta, "issingle", 0):
			# single doctype value type is mediumtext
			return

		type_map = mrinimitable.db.type_map

		for fieldname, value in self.get_valid_dict(ignore_virtual=True).items():
			df = self.meta.get_field(fieldname)

			if not df or df.fieldtype == "Check":
				# skip standard fields and Check fields
				continue

			column_type = type_map[df.fieldtype][0] or None

			if column_type == "varchar":
				default_column_max_length = type_map[df.fieldtype][1] or None
				max_length = cint(df.get("length")) or cint(default_column_max_length)

				if len(cstr(value)) > max_length:
					self.throw_length_exceeded_error(df, max_length, value)

			elif column_type in ("int", "bigint", "smallint"):
				if cint(df.get("length")) > 11:  # We implicitl switch to bigint for >11
					column_type = "bigint"

				max_length = max_positive_value[column_type]

				if abs(cint(value)) > max_length:
					self.throw_length_exceeded_error(df, max_length, value)

	def _validate_code_fields(self):
		for field in self.meta.get_code_fields():
			code_string = self.get(field.fieldname)
			language = field.get("options")

			if language == "Python":
				mrinimitable.utils.validate_python_code(code_string, fieldname=field.label, is_expression=False)

			elif language == "PythonExpression":
				mrinimitable.utils.validate_python_code(code_string, fieldname=field.label)

	def _sync_autoname_field(self):
		"""Keep autoname field in sync with `name`"""
		autoname = self.meta.autoname or ""
		_empty, _field_specifier, fieldname = autoname.partition("field:")

		if fieldname and self.name and self.name != self.get(fieldname):
			self.set(fieldname, self.name)

	def throw_length_exceeded_error(self, df, max_length, value):
		# check if parentfield exists (only applicable for child table doctype)
		if self.get("parentfield"):
			reference = _("{0}, Row {1}").format(_(self.doctype), self.idx)
		else:
			reference = f"{_(self.doctype)} {self.name}"

		mrinimitable.throw(
			_("{0}: '{1}' ({3}) will get truncated, as max characters allowed is {2}").format(
				reference, mrinimitable.bold(_(df.label, context=df.parent)), max_length, value
			),
			mrinimitable.CharacterLengthExceededError,
			title=_("Value too big"),
		)

	def _validate_update_after_submit(self):
		# get the full doc with children
		db_values = mrinimitable.get_doc(self.doctype, self.name).as_dict()

		for key in self.as_dict():
			df = self.meta.get_field(key)
			db_value = db_values.get(key)

			if df and not df.allow_on_submit and (self.get(key) or db_value):
				if df.fieldtype in table_fields:
					# just check if the table size has changed
					# individual fields will be checked in the loop for children
					self_value = len(self.get(key))
					db_value = len(db_value)

				else:
					self_value = self.get_value(key)
				# Postgres stores values as `datetime.time`, MariaDB as `timedelta`
				if isinstance(self_value, datetime.timedelta) and isinstance(db_value, datetime.time):
					db_value = datetime.timedelta(
						hours=db_value.hour,
						minutes=db_value.minute,
						seconds=db_value.second,
						microseconds=db_value.microsecond,
					)
				if self_value != db_value:
					mrinimitable.throw(
						_("{0} Not allowed to change {1} after submission from {2} to {3}").format(
							f"Row #{self.idx}:" if self.get("parent") else "",
							mrinimitable.bold(_(df.label, context=df.parent)),
							mrinimitable.bold(db_value),
							mrinimitable.bold(self_value),
						),
						mrinimitable.UpdateAfterSubmitError,
						title=_("Cannot Update After Submit"),
					)

	def _sanitize_content(self):
		"""Sanitize HTML and Email in field values. Used to prevent XSS.

		- Ignore if 'Ignore XSS Filter' is checked or fieldtype is 'Code'
		"""
		from bs4 import BeautifulSoup

		if mrinimitable.flags.in_install:
			return

		for fieldname, value in self.get_valid_dict(ignore_virtual=True).items():
			if not value or not isinstance(value, str):
				continue

			value = mrinimitable.as_unicode(value)

			if "<" not in value and ">" not in value:
				# doesn't look like html so no need
				continue

			elif "<!-- markdown -->" in value and not bool(BeautifulSoup(value, "html.parser").find()):
				# should be handled separately via the markdown converter function
				continue

			df = self.meta.get_field(fieldname)
			sanitized_value = value

			if df and (
				df.get("ignore_xss_filter")
				or (df.get("fieldtype") in ("Data", "Small Text", "Text") and df.get("options") == "Email")
				or df.get("fieldtype") in ("Attach", "Attach Image", "Barcode", "Code")
				# cancelled and submit but not update after submit should be ignored
				or self.docstatus.is_cancelled()
				or (self.docstatus.is_submitted() and not df.get("allow_on_submit"))
			):
				continue

			else:
				sanitized_value = sanitize_html(value, linkify=df and df.fieldtype == "Text Editor")

			self.set(fieldname, sanitized_value)

	def _save_passwords(self):
		"""Save password field values in __Auth table"""
		from mrinimitable.utils.password import remove_encrypted_password, set_encrypted_password

		if self.flags.ignore_save_passwords is True:
			return

		for df in self.meta.get("fields", {"fieldtype": ("=", "Password")}):
			if self.flags.ignore_save_passwords and df.fieldname in self.flags.ignore_save_passwords:
				continue
			new_password = self.get(df.fieldname)

			if not new_password:
				remove_encrypted_password(self.doctype, self.name, df.fieldname)

			if new_password and not self.is_dummy_password(new_password):
				# is not a dummy password like '*****'
				set_encrypted_password(self.doctype, self.name, new_password, df.fieldname)

				# set dummy password like '*****'
				self.set(df.fieldname, "*" * len(new_password))

	def get_password(self, fieldname="password", raise_exception=True):
		from mrinimitable.utils.password import get_decrypted_password

		if self.get(fieldname) and not self.is_dummy_password(self.get(fieldname)):
			return self.get(fieldname)

		return get_decrypted_password(self.doctype, self.name, fieldname, raise_exception=raise_exception)

	def is_dummy_password(self, pwd):
		return "".join(set(pwd)) == "*"

	def precision(self, fieldname, parentfield=None) -> int | None:
		"""Return float precision for a particular field (or get global default).

		:param fieldname: Fieldname for which precision is required.
		:param parentfield: If fieldname is in child table."""
		from mrinimitable.model.meta import get_field_precision

		if parentfield and not isinstance(parentfield, str) and parentfield.get("parentfield"):
			parentfield = parentfield.parentfield

		cache_key = parentfield or "main"

		if not hasattr(self, "_precision"):
			self._precision = _dict()

		if cache_key not in self._precision:
			self._precision[cache_key] = _dict()

		if fieldname not in self._precision[cache_key]:
			self._precision[cache_key][fieldname] = None

			doctype = self.meta.get_field(parentfield).options if parentfield else self.doctype
			df = mrinimitable.get_meta(doctype).get_field(fieldname)

			if df and df.fieldtype in ("Currency", "Float", "Percent"):
				self._precision[cache_key][fieldname] = get_field_precision(df, self)

		return self._precision[cache_key][fieldname]

	def get_formatted(
		self, fieldname, doc=None, currency=None, absolute_value=False, translated=False, format=None
	):
		from mrinimitable.utils.formatters import format_value

		df = self.meta.get_field(fieldname)
		if not df:
			from mrinimitable.model.meta import get_default_df

			df = get_default_df(fieldname)

		if (
			df
			and df.fieldtype == "Currency"
			and not currency
			and (currency_field := df.get("options"))
			and (currency_value := self.get(currency_field))
		):
			currency = mrinimitable.db.get_value("Currency", currency_value, cache=True)

		val = self.get(fieldname)

		if translated:
			val = _(val)

		if not doc:
			doc = getattr(self, "parent_doc", None) or self

		if (absolute_value or doc.get("absolute_value")) and isinstance(val, int | float):
			val = abs(self.get(fieldname))

		return format_value(val, df=df, doc=doc, currency=currency, format=format)

	def is_print_hide(self, fieldname, df=None, for_print=True):
		"""Return True if fieldname is to be hidden for print.

		Print Hide can be set via the Print Format Builder or in the controller as a list
		of hidden fields. Example

		        class MyDoc(Document):
		                def __setup__(self):
		                        self.print_hide = ["field1", "field2"]

		:param fieldname: Fieldname to be checked if hidden.
		"""
		meta_df = self.meta.get_field(fieldname)
		if meta_df and meta_df.get("__print_hide"):
			return True

		print_hide = 0

		if self.get(fieldname) == 0 and not self.meta.istable:
			print_hide = (df and df.print_hide_if_no_value) or (meta_df and meta_df.print_hide_if_no_value)

		if not print_hide:
			if df and df.print_hide is not None:
				print_hide = df.print_hide
			elif meta_df:
				print_hide = meta_df.print_hide

		return print_hide

	def in_format_data(self, fieldname):
		"""Return True if shown via Print Format::`format_data` property.

		Called from within standard print format."""
		doc = getattr(self, "parent_doc", self)

		if hasattr(doc, "format_data_map"):
			return fieldname in doc.format_data_map
		else:
			return True

	def reset_values_if_no_permlevel_access(self, has_access_to, high_permlevel_fields):
		"""If the user does not have permissions at permlevel > 0, then reset the values to original / default"""
		to_reset = [
			df
			for df in high_permlevel_fields
			if (
				df.permlevel not in has_access_to
				and df.fieldtype not in display_fieldtypes
				and df.fieldname not in self.flags.get("ignore_permlevel_for_fields", [])
			)
		]

		if to_reset:
			if self.is_new():
				# if new, set default value
				ref_doc = mrinimitable.new_doc(self.doctype)
			else:
				# get values from old doc
				if self.parent_doc:
					parent_doc = self.parent_doc.get_latest()
					child_docs = [d for d in parent_doc.get(self.parentfield) if d.name == self.name]
					if not child_docs:
						return
					ref_doc = child_docs[0]
				else:
					ref_doc = self.get_latest()

			for df in to_reset:
				self.set(df.fieldname, ref_doc.get(df.fieldname))

	def get_value(self, fieldname):
		df = self.meta.get_field(fieldname)
		val = self.get(fieldname)

		return self.cast(val, df)

	def cast(self, value, df):
		return cast_fieldtype(df.fieldtype, value, show_warning=False)

	def _extract_images_from_text_editor(self):
		from mrinimitable.core.doctype.file.utils import extract_images_from_doc

		if self.doctype != "DocType":
			for df in self.meta.get("fields", {"fieldtype": ("=", "Text Editor")}):
				extract_images_from_doc(self, df.fieldname)


def _filter(data, filters, limit=None):
	"""pass filters as:
	{"key": "val", "key": ["!=", "val"],
	"key": ["in", "val"], "key": ["not in", "val"], "key": "^val",
	"key" : True (exists), "key": False (does not exist) }"""

	out, _filters = [], {}

	if not data:
		return out

	# setup filters as tuples
	if filters:
		for f in filters:
			fval = filters[f]

			if not isinstance(fval, tuple | list):
				if fval is True:
					fval = ("not None", fval)
				elif fval is False:
					fval = ("None", fval)
				elif isinstance(fval, str) and fval.startswith("^"):
					fval = ("^", fval[1:])
				else:
					fval = ("=", fval)

			_filters[f] = fval

	for d in data:
		for f, fval in _filters.items():
			if not compare(getattr(d, f, None), fval[0], fval[1]):
				break
		else:
			out.append(d)
			if limit and len(out) >= limit:
				break

	return out
