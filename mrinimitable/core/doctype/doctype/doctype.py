# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import copy
import json
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Union

import mrinimitable
from mrinimitable import _
from mrinimitable.cache_manager import clear_controller_cache, clear_user_cache
from mrinimitable.custom.doctype.custom_field.custom_field import create_custom_field
from mrinimitable.custom.doctype.property_setter.property_setter import make_property_setter
from mrinimitable.database import savepoint
from mrinimitable.database.schema import validate_column_length, validate_column_name
from mrinimitable.desk.notifications import delete_notification_count_for, get_filters_for
from mrinimitable.desk.utils import validate_route_conflict
from mrinimitable.model import (
	child_table_fields,
	data_field_options,
	default_fields,
	no_value_fields,
	table_fields,
)
from mrinimitable.model.base_document import RESERVED_KEYWORDS, get_controller
from mrinimitable.model.docfield import supports_translation
from mrinimitable.model.document import Document
from mrinimitable.model.meta import Meta
from mrinimitable.modules import get_doc_path, make_boilerplate
from mrinimitable.modules.import_file import get_file_path
from mrinimitable.permissions import ALL_USER_ROLE, AUTOMATIC_ROLES, SYSTEM_USER_ROLE
from mrinimitable.query_builder.functions import Concat
from mrinimitable.utils import cint, flt, get_datetime, is_a_property, random_string
from mrinimitable.website.utils import clear_cache

if TYPE_CHECKING:
	from mrinimitable.custom.doctype.customize_form.customize_form import CustomizeForm

DEPENDS_ON_PATTERN = re.compile(r'[\w\.:_]+\s*={1}\s*[\w\.@\'"]+')
ILLEGAL_FIELDNAME_PATTERN = re.compile("""['",./%@()<>{}]""")
WHITESPACE_PADDING_PATTERN = re.compile(r"^[ \t\n\r]+|[ \t\n\r]+$", flags=re.ASCII)
START_WITH_LETTERS_PATTERN = re.compile(r"^(?![\W])[^\d_\s][\w -]+$", flags=re.ASCII)
FIELD_PATTERN = re.compile("{(.*?)}", flags=re.UNICODE)


class InvalidFieldNameError(mrinimitable.ValidationError):
	pass


class UniqueFieldnameError(mrinimitable.ValidationError):
	pass


class IllegalMandatoryError(mrinimitable.ValidationError):
	pass


class DoctypeLinkError(mrinimitable.ValidationError):
	pass


class WrongOptionsDoctypeLinkError(mrinimitable.ValidationError):
	pass


class HiddenAndMandatoryWithoutDefaultError(mrinimitable.ValidationError):
	pass


class NonUniqueError(mrinimitable.ValidationError):
	pass


class CannotIndexedError(mrinimitable.ValidationError):
	pass


class CannotCreateStandardDoctypeError(mrinimitable.ValidationError):
	pass


form_grid_templates = {"fields": "templates/form_grid/fields.html"}


class DocType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.core.doctype.docfield.docfield import DocField
		from mrinimitable.core.doctype.docperm.docperm import DocPerm
		from mrinimitable.core.doctype.doctype_action.doctype_action import DocTypeAction
		from mrinimitable.core.doctype.doctype_link.doctype_link import DocTypeLink
		from mrinimitable.core.doctype.doctype_state.doctype_state import DocTypeState
		from mrinimitable.types import DF

		actions: DF.Table[DocTypeAction]
		allow_auto_repeat: DF.Check
		allow_copy: DF.Check
		allow_events_in_timeline: DF.Check
		allow_guest_to_view: DF.Check
		allow_import: DF.Check
		allow_rename: DF.Check
		autoname: DF.Data | None
		beta: DF.Check
		color: DF.Data | None
		custom: DF.Check
		default_email_template: DF.Link | None
		default_print_format: DF.Data | None
		default_view: DF.Literal[None]
		description: DF.SmallText | None
		document_type: DF.Literal["", "Document", "Setup", "System", "Other"]
		documentation: DF.Data | None
		editable_grid: DF.Check
		email_append_to: DF.Check
		engine: DF.Literal["InnoDB", "MyISAM"]
		fields: DF.Table[DocField]
		force_re_route_to_default_view: DF.Check
		grid_page_length: DF.Int
		has_web_view: DF.Check
		hide_toolbar: DF.Check
		icon: DF.Data | None
		image_field: DF.Data | None
		in_create: DF.Check
		index_web_pages_for_search: DF.Check
		is_calendar_and_gantt: DF.Check
		is_published_field: DF.Data | None
		is_submittable: DF.Check
		is_tree: DF.Check
		is_virtual: DF.Check
		issingle: DF.Check
		istable: DF.Check
		links: DF.Table[DocTypeLink]
		make_attachments_public: DF.Check
		max_attachments: DF.Int
		migration_hash: DF.Data | None
		module: DF.Link
		naming_rule: DF.Literal[
			"",
			"Set by user",
			"Autoincrement",
			"By fieldname",
			'By "Naming Series" field',
			"Expression",
			"Expression (old style)",
			"Random",
			"UUID",
			"By script",
		]
		nsm_parent_field: DF.Data | None
		permissions: DF.Table[DocPerm]
		protect_attached_files: DF.Check
		queue_in_background: DF.Check
		quick_entry: DF.Check
		read_only: DF.Check
		recipient_account_field: DF.Data | None
		restrict_to_domain: DF.Link | None
		route: DF.Data | None
		row_format: DF.Literal["Dynamic", "Compressed"]
		rows_threshold_for_grid_search: DF.Int
		search_fields: DF.Data | None
		sender_field: DF.Data | None
		sender_name_field: DF.Data | None
		show_name_in_global_search: DF.Check
		show_preview_popup: DF.Check
		show_title_field_in_link: DF.Check
		sort_field: DF.Data | None
		sort_order: DF.Literal["ASC", "DESC"]
		states: DF.Table[DocTypeState]
		subject_field: DF.Data | None
		timeline_field: DF.Data | None
		title_field: DF.Data | None
		track_changes: DF.Check
		track_seen: DF.Check
		track_views: DF.Check
		translated_doctype: DF.Check
		website_search_field: DF.Data | None
	# end: auto-generated types

	def validate(self):
		"""Validate DocType before saving.

		- Check if developer mode is set.
		- Validate series
		- Check fieldnames (duplication etc)
		- Clear permission table for child tables
		- Add `amended_from` and `amended_by` if Amendable
		- Add custom field `auto_repeat` if Repeatable
		- Check if links point to valid fieldnames"""

		self.check_developer_mode()

		self.validate_name()

		self.set_defaults_for_single_and_table()
		self.scrub_field_names()
		self.set_default_in_list_view()
		self.set_default_translatable()
		validate_series(self)
		self.set("can_change_name_type", validate_autoincrement_autoname(self))
		self.validate_document_type()
		validate_fields(self)
		self.check_indexing_for_dashboard_links()
		if not self.istable:
			validate_permissions(self)

		self.make_amendable()
		self.make_repeatable()
		self.validate_nestedset()
		self.validate_child_table()
		self.validate_website()
		self.validate_virtual_doctype_methods()
		self.ensure_minimum_max_attachment_limit()
		validate_links_table_fieldnames(self)

		if not self.is_new():
			self.before_update = mrinimitable.get_doc("DocType", self.name)
			self.setup_fields_to_fetch()
			self.validate_field_name_conflicts()

		check_email_append_to(self)

		if self.default_print_format and not self.custom:
			mrinimitable.throw(_("Standard DocType cannot have default print format, use Customize Form"))

	def validate_field_name_conflicts(self):
		"""Check if field names dont conflict with controller properties and methods"""
		core_doctypes = [
			"Custom DocPerm",
			"DocPerm",
			"Custom Field",
			"Customize Form Field",
			"Web Form Field",
			"DocField",
		]

		if self.name in core_doctypes:
			return

		try:
			controller = get_controller(self.name)
		except ImportError:
			controller = Document

		available_objects = {x for x in dir(controller) if isinstance(x, str)}
		property_set = {x for x in available_objects if is_a_property(getattr(controller, x, None))}
		method_set = {
			x for x in available_objects if x not in property_set and callable(getattr(controller, x, None))
		}

		for docfield in self.get("fields") or []:
			if docfield.fieldtype in no_value_fields:
				continue

			conflict_type = None
			field = docfield.fieldname
			field_label = docfield.label or docfield.fieldname

			if docfield.fieldname in method_set:
				conflict_type = "controller method"
			if docfield.fieldname in property_set and not docfield.is_virtual:
				conflict_type = "class property"

			if conflict_type:
				mrinimitable.throw(
					_("Fieldname '{0}' conflicting with a {1} of the name {2} in {3}").format(
						field_label, conflict_type, field, self.name
					)
				)

	def set_defaults_for_single_and_table(self):
		if self.issingle:
			self.allow_import = 0
			self.is_submittable = 0
			self.istable = 0

		elif self.istable:
			self.allow_import = 0
			self.permissions = []

	def set_default_in_list_view(self):
		"""Set default in-list-view for first 4 mandatory fields"""
		not_allowed_in_list_view = get_fields_not_allowed_in_list_view(self.meta)

		if not [d.fieldname for d in self.fields if d.in_list_view]:
			cnt = 0
			for d in self.fields:
				if d.reqd and not d.hidden and d.fieldtype not in not_allowed_in_list_view:
					d.in_list_view = 1
					cnt += 1
					if cnt == 4:
						break

	def set_default_translatable(self):
		"""Ensure that non-translatable never will be translatable"""
		for d in self.fields:
			if d.translatable and not supports_translation(d.fieldtype):
				d.translatable = 0

	def check_indexing_for_dashboard_links(self):
		"""Enable indexing for outgoing links used in dashboard"""
		for d in self.fields:
			if d.fieldtype == "Link" and not d.unique and not d.search_index:
				referred_as_link = mrinimitable.db.exists(
					"DocType Link",
					{"parent": d.options, "link_doctype": self.name, "link_fieldname": d.fieldname},
				)
				if not referred_as_link:
					continue

				mrinimitable.msgprint(
					_("{0} should be indexed because it's referred in dashboard connections").format(
						_(d.label, context=d.parent)
					),
					alert=True,
					indicator="orange",
				)

	def check_developer_mode(self):
		"""Throw exception if not developer mode or via patch"""
		if mrinimitable.flags.in_patch or mrinimitable.in_test:
			return

		if not mrinimitable.conf.get("developer_mode") and not self.custom:
			mrinimitable.throw(
				_("Not in Developer Mode! Set in site_config.json or make 'Custom' DocType."),
				CannotCreateStandardDoctypeError,
			)

		if self.is_virtual and self.custom:
			mrinimitable.throw(_("Not allowed to create custom Virtual DocType."), CannotCreateStandardDoctypeError)

		if mrinimitable.conf.developer_mode and not self.owner:
			self.owner = "Administrator"
			self.modified_by = "Administrator"

	def setup_fields_to_fetch(self):
		"""Setup query to update values for newly set fetch values"""
		try:
			old_meta = mrinimitable.get_meta(mrinimitable.get_doc("DocType", self.name), cached=False)
			old_fields_to_fetch = [df.fieldname for df in old_meta.get_fields_to_fetch()]
		except mrinimitable.DoesNotExistError:
			old_fields_to_fetch = []

		new_meta = mrinimitable.get_meta(self, cached=False)

		self.flags.update_fields_to_fetch_queries = []

		new_fields_to_fetch = new_meta.get_fields_to_fetch()

		if set(old_fields_to_fetch) != {df.fieldname for df in new_fields_to_fetch}:
			for df in new_fields_to_fetch:
				if df.fieldname not in old_fields_to_fetch:
					link_fieldname, source_fieldname = df.fetch_from.split(".", 1)
					if not source_fieldname:
						continue  # Invalid expression
					link_df = new_meta.get_field(link_fieldname)

					if mrinimitable.db.db_type == "postgres":
						update_query = """
							UPDATE `tab{doctype}`
							SET `{fieldname}` = source.`{source_fieldname}`
							FROM `tab{link_doctype}` as source
							WHERE `{link_fieldname}` = source.name
						"""
						if df.not_nullable:
							update_query += "AND `{fieldname}`=''"
						else:
							update_query += "AND ifnull(`{fieldname}`, '')=''"

					else:
						update_query = """
							UPDATE `tab{doctype}` as target
							INNER JOIN `tab{link_doctype}` as source
							ON `target`.`{link_fieldname}` = `source`.`name`
							SET `target`.`{fieldname}` = `source`.`{source_fieldname}`
						"""
						if df.not_nullable:
							update_query += "WHERE `target`.`{fieldname}`=''"
						else:
							update_query += "WHERE ifnull(`target`.`{fieldname}`, '')=''"

					self.flags.update_fields_to_fetch_queries.append(
						update_query.format(
							link_doctype=link_df.options,
							source_fieldname=source_fieldname,
							doctype=self.name,
							fieldname=df.fieldname,
							link_fieldname=link_fieldname,
						)
					)

	def update_fields_to_fetch(self):
		"""Update fetch values based on queries setup"""
		if self.flags.update_fields_to_fetch_queries and not self.issingle:
			for query in self.flags.update_fields_to_fetch_queries:
				mrinimitable.db.sql(query)

	def validate_document_type(self):
		if self.document_type == "Transaction":  # type: ignore[comparison-overlap]
			self.document_type = "Document"
		if self.document_type == "Master":  # type: ignore[comparison-overlap]
			self.document_type = "Setup"

	def validate_website(self):
		"""Ensure that website generator has field 'route'"""
		if self.route:
			self.route = self.route.strip("/")

		if self.has_web_view:
			# route field must be present
			if "route" not in [d.fieldname for d in self.fields]:
				mrinimitable.throw(_('Field "route" is mandatory for Web Views'), title="Missing Field")

			# clear website cache
			clear_cache()

	def validate_virtual_doctype_methods(self):
		if not self.get("is_virtual") or self.is_new():
			return

		from mrinimitable.model.virtual_doctype import validate_controller

		validate_controller(self.name)

	def ensure_minimum_max_attachment_limit(self):
		"""Ensure that max_attachments is *at least* bigger than number of attach fields."""
		from mrinimitable.model import attachment_fieldtypes

		if not self.max_attachments:
			return

		total_attach_fields = len([d for d in self.fields if d.fieldtype in attachment_fieldtypes])
		if total_attach_fields > self.max_attachments:
			self.max_attachments = total_attach_fields
			field_label = mrinimitable.bold(self.meta.get_field("max_attachments").label)
			mrinimitable.msgprint(
				_("Number of attachment fields are more than {}, limit updated to {}.").format(
					field_label, total_attach_fields
				),
				title=_("Insufficient attachment limit"),
				alert=True,
			)

	def change_modified_of_parent(self):
		"""Change the timestamp of parent DocType if the current one is a child to clear caches."""
		if mrinimitable.flags.in_import:
			return
		parent_list = mrinimitable.get_all(
			"DocField", "parent", dict(fieldtype=["in", mrinimitable.model.table_fields], options=self.name)
		)
		for p in parent_list:
			mrinimitable.db.set_value("DocType", p.parent, {})

	def scrub_field_names(self):
		"""Sluggify fieldnames if not set from Label."""
		restricted = (
			"name",
			"parent",
			"creation",
			"owner",
			"modified",
			"modified_by",
			"parentfield",
			"parenttype",
			"file_list",
			"flags",
			"docstatus",
		)
		for d in self.get("fields"):
			if d.fieldtype:
				if not getattr(d, "fieldname", None):
					if d.label:
						d.fieldname = d.label.strip().lower().replace(" ", "_").strip("?")
						if d.fieldname in restricted:
							d.fieldname = d.fieldname + "1"
						if d.fieldtype == "Section Break":
							d.fieldname = d.fieldname + "_section"
						elif d.fieldtype == "Column Break":
							d.fieldname = d.fieldname + "_column"
						elif d.fieldtype == "Tab Break":
							d.fieldname = d.fieldname + "_tab"
					elif d.fieldtype in ("Section Break", "Column Break", "Tab Break"):
						d.fieldname = d.fieldtype.lower().replace(" ", "_") + "_" + str(random_string(4))
					else:
						mrinimitable.throw(
							_("Row #{}: Fieldname is required").format(d.idx), title="Missing Fieldname"
						)
				else:
					if d.fieldname in restricted:
						mrinimitable.throw(
							_("Fieldname {0} is restricted").format(d.fieldname), InvalidFieldNameError
						)
				d.fieldname = ILLEGAL_FIELDNAME_PATTERN.sub("", d.fieldname)

				# fieldnames should be lowercase
				d.fieldname = d.fieldname.lower()

			# unique is automatically an index
			if d.unique:
				d.search_index = 0

	def get_permission_log_options(self, event=None):
		if self.custom and event != "after_delete":
			return {
				"fields": ("permissions", {"fields": ("fieldname", "ignore_user_permissions", "permlevel")})
			}

		self._no_perm_log = True

	def on_update(self):
		"""Update database schema, make controller templates if `custom` is not set and clear cache."""

		if self.get("can_change_name_type"):
			self.setup_autoincrement_and_sequence()

		try:
			mrinimitable.db.updatedb(self.name, Meta(self))
		except Exception as e:
			print(f"\n\nThere was an issue while migrating the DocType: {self.name}\n")
			raise e

		self.change_modified_of_parent()
		make_module_and_roles(self)

		self.update_fields_to_fetch()

		allow_doctype_export = (
			not self.custom
			and not mrinimitable.flags.in_import
			and (mrinimitable.conf.developer_mode or mrinimitable.flags.allow_doctype_export)
		)
		if allow_doctype_export:
			self.export_doc()
			self.make_controller_template()
			self.set_base_class_for_controller()
			self.export_types_to_controller()

		# update index
		if not self.custom:
			self.run_module_method("on_doctype_update")
			if self.flags.in_insert:
				self.run_module_method("after_doctype_insert")

		self.sync_doctype_layouts()
		delete_notification_count_for(doctype=self.name)

		mrinimitable.clear_cache(doctype=self.name)

		# clear user cache so that on the next reload this doctype is included in boot
		clear_user_cache(mrinimitable.session.user)

		if not mrinimitable.flags.in_install and hasattr(self, "before_update"):
			self.sync_global_search()

		clear_linked_doctype_cache()

	@savepoint(catch=Exception)
	def sync_doctype_layouts(self):
		"""Sync Doctype Layout"""
		doctype_layouts = mrinimitable.get_all(
			"DocType Layout", filters={"document_type": self.name}, pluck="name", ignore_ddl=True
		)
		for layout in doctype_layouts:
			layout_doc = mrinimitable.get_doc("DocType Layout", layout)
			layout_doc.sync_fields()
			layout_doc.save()

	def setup_autoincrement_and_sequence(self):
		"""Changes name type and makes sequence on change (if required)"""

		name_type = f"varchar({mrinimitable.db.VARCHAR_LEN})"

		if self.autoname == "autoincrement":
			name_type = "bigint"
			mrinimitable.db.create_sequence(self.name, check_not_exists=True)

		change_name_column_type(self.name, name_type)

	def sync_global_search(self):
		"""If global search settings are changed, rebuild search properties for this table"""
		global_search_fields_before_update = [
			d.fieldname for d in self.before_update.fields if d.in_global_search
		]
		if self.before_update.show_name_in_global_search:
			global_search_fields_before_update.append("name")

		global_search_fields_after_update = [d.fieldname for d in self.fields if d.in_global_search]
		if self.show_name_in_global_search:
			global_search_fields_after_update.append("name")

		if set(global_search_fields_before_update) != set(global_search_fields_after_update):
			now = (not mrinimitable.request) or mrinimitable.in_test or mrinimitable.flags.in_install
			mrinimitable.enqueue("mrinimitable.utils.global_search.rebuild_for_doctype", now=now, doctype=self.name)

	def set_base_class_for_controller(self):
		"""If DocType.has_web_view has been changed, updates the controller class and import
		from `WebsiteGenertor` to `Document` or viceversa"""

		if not self.has_value_changed("has_web_view"):
			return

		despaced_name = self.name.replace(" ", "")
		scrubbed_name = mrinimitable.scrub(self.name)
		scrubbed_module = mrinimitable.scrub(self.module)
		controller_path = mrinimitable.get_module_path(
			scrubbed_module, "doctype", scrubbed_name, f"{scrubbed_name}.py"
		)

		document_cls_tag = f"class {despaced_name}(Document)"
		document_import_tag = "from mrinimitable.model.document import Document"
		website_generator_cls_tag = f"class {despaced_name}(WebsiteGenerator)"
		website_generator_import_tag = "from mrinimitable.website.website_generator import WebsiteGenerator"

		with open(controller_path) as f:
			code = f.read()
		updated_code = code

		is_website_generator_class = all(
			[website_generator_cls_tag in code, website_generator_import_tag in code]
		)

		if self.has_web_view and not is_website_generator_class:
			updated_code = updated_code.replace(document_import_tag, website_generator_import_tag).replace(
				document_cls_tag, website_generator_cls_tag
			)
		elif not self.has_web_view and is_website_generator_class:
			updated_code = updated_code.replace(website_generator_import_tag, document_import_tag).replace(
				website_generator_cls_tag, document_cls_tag
			)

		if updated_code != code:
			with open(controller_path, "w") as f:
				f.write(updated_code)

	def run_module_method(self, method):
		from mrinimitable.modules import load_doctype_module

		module = load_doctype_module(self.name, self.module)
		if hasattr(module, method):
			getattr(module, method)()

	def before_rename(self, old, new, merge=False):
		"""Throw exception if merge. DocTypes cannot be merged."""
		if not self.custom and mrinimitable.session.user != "Administrator":
			mrinimitable.throw(_("DocType can only be renamed by Administrator"))

		self.check_developer_mode()
		self.validate_name(new)

		if merge:
			mrinimitable.throw(_("DocType can not be merged"))

	def after_rename(self, old, new, merge=False):
		"""Change table name using `RENAME TABLE` if table exists. Or update
		`doctype` property for Single type."""

		if self.issingle:
			mrinimitable.db.sql("""update tabSingles set doctype=%s where doctype=%s""", (new, old))
			mrinimitable.db.sql(
				"""update tabSingles set value=%s
				where doctype=%s and field='name' and value = %s""",
				(new, new, old),
			)
		else:
			mrinimitable.db.rename_table(old, new)
			mrinimitable.db.commit()

		# Do not rename and move files and folders for custom doctype
		if not self.custom:
			if not mrinimitable.flags.in_patch:
				self.rename_files_and_folders(old, new)

			clear_controller_cache(old)

	def after_delete(self):
		if not self.custom:
			clear_controller_cache(self.name)

	def rename_files_and_folders(self, old, new):
		# move files
		new_path = get_doc_path(self.module, "doctype", new)
		old_path = get_doc_path(self.module, "doctype", old)
		shutil.move(old_path, new_path)

		# rename files
		for fname in os.listdir(new_path):
			if mrinimitable.scrub(old) in fname:
				old_file_name = os.path.join(new_path, fname)
				new_file_name = os.path.join(new_path, fname.replace(mrinimitable.scrub(old), mrinimitable.scrub(new)))
				shutil.move(old_file_name, new_file_name)

		self.rename_inside_controller(new, old, new_path)
		mrinimitable.msgprint(_("Renamed files and replaced code in controllers, please check!"))

	def rename_inside_controller(self, new, old, new_path):
		for fname in ("{}.js", "{}.py", "{}_list.js", "{}_calendar.js", "test_{}.py", "test_{}.js"):
			fname = os.path.join(new_path, fname.format(mrinimitable.scrub(new)))
			if os.path.exists(fname):
				with open(fname) as f:
					code = f.read()
				with open(fname, "w") as f:
					if fname.endswith(".js"):
						file_content = code.replace(old, new)  # replace str with full str (js controllers)

					elif fname.endswith(".py"):
						new_scrub = mrinimitable.scrub(new)
						new_no_space_no_hyphen = new.replace(" ", "").replace("-", "")
						new_no_space = new.replace(" ", "")
						old_scrub = mrinimitable.scrub(old)
						old_no_space_no_hyphen = old.replace(" ", "").replace("-", "")
						old_no_space = old.replace(" ", "")
						# replace in one go
						file_content = re.sub(
							rf"{old_scrub}|{old_no_space}|{old_no_space_no_hyphen}",
							lambda x: new_scrub
							if x.group() == old_scrub
							else new_no_space_no_hyphen
							if x.group() == old_no_space_no_hyphen
							else new_no_space,
							code,
						)

					f.write(file_content)

		# updating json file with new name
		doctype_json_path = os.path.join(new_path, f"{mrinimitable.scrub(new)}.json")
		current_data = mrinimitable.get_file_json(doctype_json_path)
		current_data["name"] = new

		with open(doctype_json_path, "w") as f:
			json.dump(current_data, f, indent=1)

	def before_reload(self):
		"""Preserve naming series changes in Property Setter."""
		if not (self.issingle and self.istable):
			self.preserve_naming_series_options_in_property_setter()

	def preserve_naming_series_options_in_property_setter(self):
		"""Preserve naming_series as property setter if it does not exist"""
		naming_series = self.get("fields", {"fieldname": "naming_series"})

		if not naming_series:
			return

		# check if atleast 1 record exists
		if not (
			mrinimitable.db.table_exists(self.name)
			and mrinimitable.get_all(self.name, fields=["name"], limit=1, as_list=True)
		):
			return

		existing_property_setter = mrinimitable.db.get_value(
			"Property Setter", {"doc_type": self.name, "property": "options", "field_name": "naming_series"}
		)

		if not existing_property_setter:
			make_property_setter(
				self.name,
				"naming_series",
				"options",
				naming_series[0].options,
				"Text",
				validate_fields_for_doctype=False,
			)
			if naming_series[0].default:
				make_property_setter(
					self.name,
					"naming_series",
					"default",
					naming_series[0].default,
					"Text",
					validate_fields_for_doctype=False,
				)

	def before_export(self, docdict):
		# remove null and empty fields
		def remove_null_fields(o):
			to_remove = []
			for attr, value in o.items():
				if isinstance(value, list):
					for v in value:
						remove_null_fields(v)
				elif not value:
					to_remove.append(attr)

			for attr in to_remove:
				del o[attr]

		remove_null_fields(docdict)

		# retain order of 'fields' table and change order in 'field_order'
		docdict["field_order"] = [f.fieldname for f in self.fields]

		if self.custom:
			return

		path = get_file_path(self.module, "DocType", self.name)
		if os.path.exists(path):
			try:
				with open(path) as txtfile:
					olddoc = json.loads(txtfile.read())

				old_field_names = [f["fieldname"] for f in olddoc.get("fields", [])]
				if old_field_names:
					new_field_dicts = []
					remaining_field_names = [f.fieldname for f in self.fields]

					for fieldname in old_field_names:
						field_dict = [f for f in docdict["fields"] if f["fieldname"] == fieldname]
						if field_dict:
							new_field_dicts.append(field_dict[0])
							if fieldname in remaining_field_names:
								remaining_field_names.remove(fieldname)

					for fieldname in remaining_field_names:
						field_dict = [f for f in docdict["fields"] if f["fieldname"] == fieldname]
						new_field_dicts.append(field_dict[0])

					docdict["fields"] = new_field_dicts
			except ValueError:
				pass

	@staticmethod
	def prepare_for_import(docdict):
		# set order of fields from field_order
		if docdict.get("field_order"):
			new_field_dicts = []
			remaining_field_names = [f["fieldname"] for f in docdict.get("fields", [])]

			for fieldname in docdict.get("field_order"):
				field_dict = [f for f in docdict.get("fields", []) if f["fieldname"] == fieldname]
				if field_dict:
					new_field_dicts.append(field_dict[0])
					if fieldname in remaining_field_names:
						remaining_field_names.remove(fieldname)

			for fieldname in remaining_field_names:
				field_dict = [f for f in docdict.get("fields", []) if f["fieldname"] == fieldname]
				new_field_dicts.append(field_dict[0])

			docdict["fields"] = new_field_dicts

		if "field_order" in docdict:
			del docdict["field_order"]

	def export_doc(self):
		"""Export to standard folder `[module]/doctype/[name]/[name].json`."""
		from mrinimitable.modules.export_file import export_to_files

		export_to_files(record_list=[["DocType", self.name]], create_init=True)

	def make_controller_template(self):
		"""Make boilerplate controller template."""
		make_boilerplate("controller._py", self)

		if not self.istable:
			make_boilerplate("test_controller._py", self.as_dict())
			make_boilerplate("controller.js", self.as_dict())
			# make_boilerplate("controller_list.js", self.as_dict())

		if self.has_web_view:
			templates_path = mrinimitable.get_module_path(
				mrinimitable.scrub(self.module), "doctype", mrinimitable.scrub(self.name), "templates"
			)
			if not os.path.exists(templates_path):
				os.makedirs(templates_path)
			make_boilerplate("templates/controller.html", self.as_dict())
			make_boilerplate("templates/controller_row.html", self.as_dict())

	def export_types_to_controller(self):
		from mrinimitable.modules.utils import get_module_app
		from mrinimitable.types.exporter import TypeExporter

		try:
			app = get_module_app(self.module)
		except mrinimitable.DoesNotExistError:
			return

		if any(mrinimitable.get_hooks("export_python_type_annotations", app_name=app)):
			TypeExporter(self).export_types()

	def make_amendable(self):
		"""If is_submittable is set, add amended_from docfields."""
		if self.is_submittable:
			docfield = [f for f in self.fields if f.fieldname == "amended_from"]
			if docfield:
				docfield[0].options = self.name
			else:
				self.append(
					"fields",
					{
						"label": "Amended From",
						"fieldtype": "Link",
						"fieldname": "amended_from",
						"options": self.name,
						"read_only": 1,
						"print_hide": 1,
						"no_copy": 1,
						"search_index": 1,
					},
				)

	def make_repeatable(self):
		"""If allow_auto_repeat is set, add auto_repeat custom field."""
		if self.allow_auto_repeat:
			if not mrinimitable.db.exists(
				"Custom Field", {"fieldname": "auto_repeat", "dt": self.name}
			) and not mrinimitable.db.exists("DocField", {"fieldname": "auto_repeat", "parent": self.name}):
				insert_after = self.fields[len(self.fields) - 1].fieldname
				df = dict(
					fieldname="auto_repeat",
					label="Auto Repeat",
					fieldtype="Link",
					options="Auto Repeat",
					insert_after=insert_after,
					read_only=1,
					no_copy=1,
					print_hide=1,
				)
				create_custom_field(self.name, df, ignore_validate=True)

	def validate_nestedset(self):
		if not self.get("is_tree"):
			return
		self.add_nestedset_fields()

		if not self.nsm_parent_field:
			field_label = mrinimitable.bold(_("Parent Field (Tree)"))
			mrinimitable.throw(_("{0} is a mandatory field").format(field_label), mrinimitable.MandatoryError)

		# check if field is valid
		fieldnames = [df.fieldname for df in self.fields]
		if self.nsm_parent_field and self.nsm_parent_field not in fieldnames:
			mrinimitable.throw(_("Parent Field must be a valid fieldname"), InvalidFieldNameError)

	def add_nestedset_fields(self):
		"""If is_tree is set, add parent_field, lft, rgt, is_group fields."""
		fieldnames = [df.fieldname for df in self.fields]
		if "lft" in fieldnames:
			return

		self.append(
			"fields",
			{
				"label": "Left",
				"fieldtype": "Int",
				"fieldname": "lft",
				"read_only": 1,
				"hidden": 1,
				"no_copy": 1,
			},
		)

		self.append(
			"fields",
			{
				"label": "Right",
				"fieldtype": "Int",
				"fieldname": "rgt",
				"read_only": 1,
				"hidden": 1,
				"no_copy": 1,
			},
		)

		self.append("fields", {"label": "Is Group", "fieldtype": "Check", "fieldname": "is_group"})
		self.append(
			"fields",
			{"label": "Old Parent", "fieldtype": "Link", "options": self.name, "fieldname": "old_parent"},
		)

		parent_field_label = f"Parent {self.name}"
		parent_field_name = mrinimitable.scrub(parent_field_label)
		self.append(
			"fields",
			{
				"label": parent_field_label,
				"fieldtype": "Link",
				"options": self.name,
				"fieldname": parent_field_name,
				"ignore_user_permissions": 1,
			},
		)
		self.nsm_parent_field = parent_field_name

	def validate_child_table(self):
		if not self.get("istable") or self.is_new() or self.get("is_virtual"):
			# if the doctype is not a child table then return
			# if the doctype is a new doctype and also a child table then
			# don't move forward as it will be handled via schema
			return

		self.add_child_table_fields()

	def add_child_table_fields(self):
		from mrinimitable.database.schema import add_column

		add_column(self.name, "parent", "Data")
		add_column(self.name, "parenttype", "Data")
		add_column(self.name, "parentfield", "Data")

	def get_max_idx(self):
		"""Return the highest `idx`."""
		max_idx = mrinimitable.db.sql("""select max(idx) from `tabDocField` where parent = %s""", self.name)
		return (max_idx and max_idx[0][0]) or 0

	def validate_name(self, name=None):
		if not name:
			name = self.name

		# a Doctype name is the tablename created in database
		# `tab<Doctype Name>` the length of tablename is limited to 64 characters
		max_length = mrinimitable.db.MAX_COLUMN_LENGTH - 3
		if len(name) > max_length:
			# length(tab + <Doctype Name>) should be equal to 64 characters hence doctype should be 61 characters
			mrinimitable.throw(
				_("Doctype name is limited to {0} characters ({1})").format(max_length, name),
				mrinimitable.NameError,
			)

		# a DocType name should not start or end with an empty space
		if WHITESPACE_PADDING_PATTERN.search(name):
			mrinimitable.throw(_("DocType's name should not start or end with whitespace"), mrinimitable.NameError)

		# a DocType's name should not start with a number or underscore
		# and should only contain letters, numbers, underscore, and hyphen
		if not START_WITH_LETTERS_PATTERN.match(name):
			mrinimitable.throw(
				_(
					"A DocType's name should start with a letter and can only "
					"consist of letters, numbers, spaces, underscores and hyphens"
				),
				mrinimitable.NameError,
				title="Invalid Name",
			)

		validate_route_conflict(self.doctype, self.name)

	@mrinimitable.whitelist()
	def check_pending_migration(self) -> bool:
		"""Checks if all migrations are applied on doctype."""
		if self.is_new() or self.custom:
			return

		file = Path(get_file_path(mrinimitable.scrub(self.module), self.doctype, self.name))
		content = json.loads(file.read_text())
		if content.get("modified") and get_datetime(self.modified) < get_datetime(content.get("modified")):
			mrinimitable.msgprint(
				_(
					"This doctype has pending migrations, run 'shashi migrate' before modifying the doctype to avoid losing changes."
				),
				alert=True,
				indicator="yellow",
			)
			return True


def validate_series(dt, autoname=None, name=None):
	"""Validate if `autoname` property is correctly set."""
	if not autoname:
		autoname = dt.autoname
	if not name:
		name = dt.name

	if not autoname and dt.get("fields", {"fieldname": "naming_series"}):
		dt.autoname = "naming_series:"
	elif dt.autoname and dt.autoname.startswith("naming_series:"):
		fieldname = dt.autoname.split("naming_series:", 1)[0] or "naming_series"
		if not dt.get("fields", {"fieldname": fieldname}):
			mrinimitable.throw(
				_("Fieldname called {0} must exist to enable autonaming").format(mrinimitable.bold(fieldname)),
				title=_("Field Missing"),
			)

	# validate field name if autoname field:fieldname is used
	# Create unique index on autoname field automatically.
	if autoname and autoname.startswith("field:"):
		field = autoname.split(":")[1]
		if not field or field not in [df.fieldname for df in dt.fields]:
			mrinimitable.throw(_("Invalid fieldname '{0}' in autoname").format(field))
		else:
			for df in dt.fields:
				if df.fieldname == field:
					df.unique = 1
					break

	if (
		autoname
		and (not autoname.startswith("field:"))
		and (not autoname.startswith("eval:"))
		and (autoname.lower() not in ("prompt", "hash"))
		and (not autoname.startswith("naming_series:"))
		and (not autoname.startswith("format:"))
	):
		prefix = autoname.split(".", 1)[0]
		doctype = mrinimitable.qb.DocType("DocType")
		used_in = (
			mrinimitable.qb.from_(doctype)
			.select(doctype.name)
			.where(doctype.autoname.like(Concat(prefix, ".%")))
			.where(doctype.name != name)
		).run()
		if used_in:
			mrinimitable.throw(_("Series {0} already used in {1}").format(prefix, used_in[0][0]))

	validate_empty_name(dt, autoname)


def validate_empty_name(dt, autoname):
	if dt.doctype == "Customize Form":
		return

	if not autoname and not (dt.issingle or dt.istable):
		try:
			controller = get_controller(dt.name)
		except ImportError:
			controller = None

		if not controller or (not hasattr(controller, "autoname")):
			mrinimitable.toast(_("Warning: Naming is not set"), indicator="yellow")


def validate_autoincrement_autoname(dt: Union[DocType, "CustomizeForm"]) -> bool:
	"""Checks if can doctype can change to/from autoincrement autoname"""

	def get_autoname_before_save(dt: Union[DocType, "CustomizeForm"]) -> str:
		if dt.doctype == "Customize Form":
			property_value = mrinimitable.db.get_value(
				"Property Setter", {"doc_type": dt.doc_type, "property": "autoname"}, "value"
			)
			# initially no property setter is set,
			# hence getting autoname value from the doctype itself
			if not property_value:
				return mrinimitable.db.get_value("DocType", dt.doc_type, "autoname") or ""

			return property_value

		return getattr(dt.get_doc_before_save(), "autoname", "")

	if not dt.is_new():
		autoname_before_save = get_autoname_before_save(dt)
		is_autoname_autoincrement = dt.autoname == "autoincrement"

		if (is_autoname_autoincrement and autoname_before_save != "autoincrement") or (
			not is_autoname_autoincrement and autoname_before_save == "autoincrement"
		):
			if dt.doctype == "Customize Form":
				mrinimitable.throw(_("Cannot change to/from autoincrement autoname in Customize Form"))

			if mrinimitable.get_meta(dt.name).issingle:
				return False

			if not mrinimitable.get_all(dt.name, limit=1):
				# allow changing the column type if there is no data
				return True

			mrinimitable.throw(
				_("Can only change to/from Autoincrement naming rule when there is no data in the doctype")
			)

	return False


def change_name_column_type(doctype_name: str, type: str) -> None:
	"""Changes name column type"""

	args = (
		(doctype_name, "name", type, False, True)
		if (mrinimitable.db.db_type == "postgres")
		else (doctype_name, "name", type, True)
	)

	mrinimitable.db.change_column_type(*args)


def validate_links_table_fieldnames(meta):
	"""Validate fieldnames in Links table"""
	if not meta.links or mrinimitable.flags.in_patch or mrinimitable.flags.in_fixtures or mrinimitable.flags.in_migrate:
		return

	fieldnames = tuple(field.fieldname for field in meta.fields)
	for index, link in enumerate(meta.links, 1):
		_test_connection_query(doctype=link.link_doctype, field=link.link_fieldname, idx=index)

		if not link.is_child_table:
			continue

		if not link.parent_doctype:
			message = _("Document Links Row #{0}: Parent DocType is mandatory for internal links").format(
				index
			)
			mrinimitable.throw(message, mrinimitable.ValidationError, _("Parent Missing"))

		if not link.table_fieldname:
			message = _("Document Links Row #{0}: Table Fieldname is mandatory for internal links").format(
				index
			)
			mrinimitable.throw(message, mrinimitable.ValidationError, _("Table Fieldname Missing"))

		if meta.name == link.parent_doctype:
			field_exists = link.table_fieldname in fieldnames
		else:
			field_exists = mrinimitable.get_meta(link.parent_doctype).has_field(link.table_fieldname)

		if not field_exists:
			message = _("Document Links Row #{0}: Could not find field {1} in {2} DocType").format(
				index, mrinimitable.bold(link.table_fieldname), mrinimitable.bold(meta.name)
			)
			mrinimitable.throw(message, mrinimitable.ValidationError, _("Invalid Table Fieldname"))


def _test_connection_query(doctype, field, idx):
	"""Make sure that connection can be queried.

	This function executes query similar to one that would be executed for
	finding count on dashboard and hence validates if fieldname/doctype are
	correct.
	"""
	filters = get_filters_for(doctype) or {}
	filters[field] = ""

	try:
		mrinimitable.get_all(doctype, filters=filters, limit=1, distinct=True, ignore_ifnull=True)
	except Exception as e:
		mrinimitable.clear_last_message()
		msg = _("Document Links Row #{0}: Invalid doctype or fieldname.").format(idx)
		msg += "<br>" + str(e)
		mrinimitable.throw(msg, InvalidFieldNameError)


def validate_fields_for_doctype(doctype):
	meta = mrinimitable.get_meta(doctype, cached=False)
	validate_links_table_fieldnames(meta)
	validate_fields(meta)


# this is separate because it is also called via custom field
def validate_fields(meta: Meta):
	"""Validate doctype fields. Checks
	1. There are no illegal characters in fieldnames
	2. If fieldnames are unique.
	3. Validate column length.
	4. Fields that do have database columns are not mandatory.
	5. `Link` and `Table` options are valid.
	6. **Hidden** and **Mandatory** are not set simultaneously.
	7. `Check` type field has default as 0 or 1.
	8. `Dynamic Links` are correctly defined.
	9. Precision is set in numeric fields and is between 1 & 6.
	10. Fold is not at the end (if set).
	11. `search_fields` are valid.
	12. `title_field` and title field pattern are valid.
	13. `unique` check is only valid for Data, Link and Read Only fieldtypes.
	14. `unique` cannot be checked if there exist non-unique values.

	:param meta: `mrinimitable.model.meta.Meta` object to check."""

	def check_illegal_characters(fieldname):
		validate_column_name(fieldname)

	def check_invalid_fieldnames(docname, fieldname):
		if fieldname in RESERVED_KEYWORDS:
			mrinimitable.throw(
				_("{0}: fieldname cannot be set to reserved keyword {1}").format(
					mrinimitable.bold(docname),
					mrinimitable.bold(fieldname),
				),
				title=_("Invalid Fieldname"),
			)

	def check_unique_fieldname(docname, fieldname):
		duplicates = list(
			filter(None, map(lambda df: (df.fieldname == fieldname and str(df.idx)) or None, fields))
		)
		if len(duplicates) > 1:
			mrinimitable.throw(
				_("{0}: Fieldname {1} appears multiple times in rows {2}").format(
					docname, fieldname, ", ".join(duplicates)
				),
				UniqueFieldnameError,
			)

	def check_fieldname_length(fieldname):
		validate_column_length(fieldname)

	def check_illegal_mandatory(docname, d):
		if (d.fieldtype in no_value_fields) and d.fieldtype not in table_fields and d.reqd:
			mrinimitable.throw(
				_("{0}: Field {1} of type {2} cannot be mandatory").format(docname, d.label, d.fieldtype),
				IllegalMandatoryError,
			)

	def check_link_table_options(docname, d):
		if mrinimitable.flags.in_patch or mrinimitable.flags.in_fixtures:
			return

		if d.fieldtype in ("Link", *table_fields):
			if not d.options:
				mrinimitable.throw(
					_("{0}: Options required for Link or Table type field {1} in row {2}").format(
						docname, d.label, d.idx
					),
					DoctypeLinkError,
				)
			if d.options == "[Select]" or d.options == d.parent:
				return
			if d.options != d.parent:
				options = mrinimitable.db.get_value("DocType", d.options, "name")
				if not options:
					mrinimitable.throw(
						_("{0}: Options must be a valid DocType for field {1} in row {2}").format(
							docname, d.label, d.idx
						),
						WrongOptionsDoctypeLinkError,
					)
				elif options != d.options:
					mrinimitable.throw(
						_("{0}: Options {1} must be the same as doctype name {2} for the field {3}").format(
							docname, d.options, options, d.label
						),
						DoctypeLinkError,
					)
				else:
					# fix case
					d.options = options

	def check_hidden_and_mandatory(docname, d):
		if d.hidden and d.reqd and not d.default and not mrinimitable.flags.in_migrate:
			mrinimitable.throw(
				_("{0}: Field {1} in row {2} cannot be hidden and mandatory without default").format(
					docname, d.label, d.idx
				),
				HiddenAndMandatoryWithoutDefaultError,
			)

	def check_width(d):
		if d.fieldtype == "Currency" and cint(d.width) < 100:
			mrinimitable.throw(_("Max width for type Currency is 100px in row {0}").format(d.idx))

	def check_in_list_view(is_table, d):
		if d.in_list_view and (d.fieldtype in not_allowed_in_list_view):
			property_label = "In Grid View" if is_table else "In List View"
			mrinimitable.throw(
				_("'{0}' not allowed for type {1} in row {2}").format(property_label, d.fieldtype, d.idx)
			)

	def check_in_global_search(d):
		if d.in_global_search and d.fieldtype in no_value_fields:
			mrinimitable.throw(
				_("'In Global Search' not allowed for type {0} in row {1}").format(d.fieldtype, d.idx)
			)

	def check_dynamic_link_options(d):
		if d.fieldtype == "Dynamic Link":
			doctype_pointer = list(filter(lambda df: df.fieldname == d.options, fields))
			if (
				not doctype_pointer
				or (doctype_pointer[0].fieldtype not in ("Link", "Select"))
				or (doctype_pointer[0].fieldtype == "Link" and doctype_pointer[0].options != "DocType")
			):
				mrinimitable.throw(
					_(
						"Options 'Dynamic Link' type of field must point to another Link Field with options as 'DocType'"
					)
				)

	def check_illegal_default(d):
		if d.fieldtype == "Check" and not d.default:
			d.default = "0"
		if d.fieldtype == "Check" and cint(d.default) not in (0, 1):
			mrinimitable.throw(
				_("Default for 'Check' type of field {0} must be either '0' or '1'").format(
					mrinimitable.bold(d.fieldname)
				)
			)
		if d.fieldtype == "Select" and d.default:
			if not d.options:
				mrinimitable.throw(
					_("Options for {0} must be set before setting the default value.").format(
						mrinimitable.bold(d.fieldname)
					)
				)
			elif d.default not in d.options.split("\n"):
				mrinimitable.throw(
					_("Default value for {0} must be in the list of options.").format(
						mrinimitable.bold(d.fieldname)
					)
				)

	def check_precision(d):
		if (
			d.fieldtype in ("Currency", "Float", "Percent")
			and d.precision is not None
			and not (1 <= cint(d.precision) <= 6)
		):
			mrinimitable.throw(_("Precision should be between 1 and 6"))

	def check_unique_and_text(docname, d):
		if meta.is_virtual:
			return

		if meta.issingle:
			d.unique = 0
			d.search_index = 0

		if getattr(d, "unique", False):
			if d.fieldtype not in ("Data", "Link", "Read Only", "Int"):
				mrinimitable.throw(
					_("{0}: Fieldtype {1} for {2} cannot be unique").format(docname, d.fieldtype, d.label),
					NonUniqueError,
				)

			if not d.get("__islocal") and mrinimitable.db.has_column(d.parent, d.fieldname):
				has_non_unique_values = mrinimitable.db.sql(
					f"""select `{d.fieldname}`, count(*)
					from `tab{d.parent}` where ifnull(`{d.fieldname}`, '') != ''
					group by `{d.fieldname}` having count(*) > 1 limit 1"""
				)

				if has_non_unique_values and has_non_unique_values[0][0]:
					mrinimitable.throw(
						_("{0}: Field '{1}' cannot be set as Unique as it has non-unique values").format(
							docname, d.label
						),
						NonUniqueError,
					)

		if d.search_index and d.fieldtype in ("Text", "Long Text", "Small Text", "Code", "Text Editor"):
			mrinimitable.throw(
				_("{0}:Fieldtype {1} for {2} cannot be indexed").format(docname, d.fieldtype, d.label),
				CannotIndexedError,
			)

	def check_fold(fields):
		fold_exists = False
		for i, f in enumerate(fields):
			if f.fieldtype == "Fold":
				if fold_exists:
					mrinimitable.throw(_("There can be only one Fold in a form"))
				fold_exists = True
				if i < len(fields) - 1:
					nxt = fields[i + 1]
					if nxt.fieldtype != "Section Break":
						mrinimitable.throw(_("Fold must come before a Section Break"))
				else:
					mrinimitable.throw(_("Fold can not be at the end of the form"))

	def check_search_fields(meta, fields):
		"""Throw exception if `search_fields` don't contain valid fields."""
		if not meta.search_fields:
			return

		# No value fields should not be included in search field
		search_fields = [field.strip() for field in (meta.search_fields or "").split(",")]
		fieldtype_mapper = {
			field.fieldname: field.fieldtype
			for field in filter(lambda field: field.fieldname in search_fields, fields)
		}

		for fieldname in search_fields:
			fieldname = fieldname.strip()
			if (fieldtype_mapper.get(fieldname) in no_value_fields) or (fieldname not in fieldname_list):
				mrinimitable.throw(_("Search field {0} is not valid").format(fieldname))

	def check_title_field(meta):
		"""Throw exception if `title_field` isn't a valid fieldname."""
		if not meta.get("title_field"):
			return

		if meta.title_field not in fieldname_list:
			mrinimitable.throw(_("Title field must be a valid fieldname"), InvalidFieldNameError)

		def _validate_title_field_pattern(pattern):
			if not pattern:
				return

			for fieldname in FIELD_PATTERN.findall(pattern):
				if fieldname.startswith("{"):
					# edge case when double curlies are used for escape
					continue

				if fieldname not in fieldname_list:
					mrinimitable.throw(
						_("{{{0}}} is not a valid fieldname pattern. It should be {{field_name}}.").format(
							fieldname
						),
						InvalidFieldNameError,
					)

		df = meta.get("fields", filters={"fieldname": meta.title_field})[0]
		if df:
			_validate_title_field_pattern(df.options)
			_validate_title_field_pattern(df.default)

	def check_image_field(meta):
		'''check image_field exists and is of type "Attach Image"'''
		if not meta.image_field:
			return

		df = meta.get("fields", {"fieldname": meta.image_field})
		if not df:
			mrinimitable.throw(_("Image field must be a valid fieldname"), InvalidFieldNameError)
		if df[0].fieldtype != "Attach Image":
			mrinimitable.throw(_("Image field must be of type Attach Image"), InvalidFieldNameError)

	def check_is_published_field(meta):
		if not meta.is_published_field:
			return

		if meta.is_published_field not in fieldname_list:
			mrinimitable.throw(_("Is Published Field must be a valid fieldname"), InvalidFieldNameError)

	def check_website_search_field(meta):
		if not meta.get("website_search_field"):
			return

		if meta.website_search_field not in fieldname_list:
			mrinimitable.throw(_("Website Search Field must be a valid fieldname"), InvalidFieldNameError)

		if "title" not in fieldname_list:
			mrinimitable.throw(
				_('Field "title" is mandatory if "Website Search Field" is set.'), title=_("Missing Field")
			)

	def check_timeline_field(meta):
		if not meta.timeline_field:
			return

		if meta.timeline_field not in fieldname_list:
			mrinimitable.throw(_("Timeline field must be a valid fieldname"), InvalidFieldNameError)

		df = meta.get("fields", {"fieldname": meta.timeline_field})[0]
		if df.fieldtype not in ("Link", "Dynamic Link"):
			mrinimitable.throw(_("Timeline field must be a Link or Dynamic Link"), InvalidFieldNameError)

	def check_sort_field(meta):
		"""Validate that sort_field(s) is a valid field"""
		if meta.sort_field:
			sort_fields = [meta.sort_field]
			if "," in meta.sort_field:
				sort_fields = [d.split(maxsplit=1)[0] for d in meta.sort_field.split(",")]

			for fieldname in sort_fields:
				if fieldname not in (fieldname_list + list(default_fields) + list(child_table_fields)):
					mrinimitable.throw(
						_("Sort field {0} must be a valid fieldname").format(fieldname), InvalidFieldNameError
					)

	def check_illegal_depends_on_conditions(docfield):
		"""assignment operation should not be allowed in the depends on condition."""
		depends_on_fields = [
			"depends_on",
			"collapsible_depends_on",
			"mandatory_depends_on",
			"read_only_depends_on",
		]
		for field in depends_on_fields:
			depends_on = docfield.get(field, None)
			if depends_on and ("=" in depends_on) and DEPENDS_ON_PATTERN.match(depends_on):
				mrinimitable.throw(_("Invalid {0} condition").format(mrinimitable.unscrub(field)), mrinimitable.ValidationError)

	def check_table_multiselect_option(docfield):
		"""check if the doctype provided in Option has atleast 1 Link field"""
		if docfield.fieldtype != "Table MultiSelect":
			return

		doctype = docfield.options
		meta = mrinimitable.get_meta(doctype)
		link_field = [df for df in meta.fields if df.fieldtype == "Link"]

		if not link_field:
			mrinimitable.throw(
				_(
					"DocType <b>{0}</b> provided for the field <b>{1}</b> must have atleast one Link field"
				).format(doctype, docfield.fieldname),
				mrinimitable.ValidationError,
			)

	def scrub_options_in_select(field):
		"""Strip options for whitespaces"""

		if field.fieldtype == "Select" and field.options is not None:
			options_list = []
			for i, option in enumerate(field.options.split("\n")):
				_option = option.strip()
				if i == 0 or _option:
					options_list.append(_option)
			field.options = "\n".join(options_list)

	def validate_fetch_from(field):
		if not field.get("fetch_from"):
			return

		field.fetch_from = field.fetch_from.strip()

		if "." not in field.fetch_from:
			return
		source_field, _target_field = field.fetch_from.split(".", maxsplit=1)

		if source_field == field.fieldname:
			msg = _(
				"{0} contains an invalid Fetch From expression, Fetch From can't be self-referential."
			).format(_(field.label, context=field.parent))
			mrinimitable.throw(msg, title=_("Recursive Fetch From"))

	def validate_data_field_type(docfield):
		if docfield.get("is_virtual"):
			return

		if docfield.fieldtype == "Data" and not (docfield.oldfieldtype and docfield.oldfieldtype != "Data"):
			if docfield.options and (docfield.options not in data_field_options):
				df_str = mrinimitable.bold(_(docfield.label, context=docfield.parent))
				text_str = (
					_("{0} is an invalid Data field.").format(df_str)
					+ "<br>" * 2
					+ _("Only Options allowed for Data field are:")
					+ "<br>"
				)
				df_options_str = "<ul><li>" + "</li><li>".join(_(x) for x in data_field_options) + "</ul>"

				mrinimitable.msgprint(text_str + df_options_str, title="Invalid Data Field", alert=True)

	def check_child_table_option(docfield):
		if mrinimitable.flags.in_fixtures:
			return
		if docfield.fieldtype not in ["Table MultiSelect", "Table"]:
			return

		doctype = docfield.options
		child_doctype_meta = mrinimitable.get_meta(doctype)

		if not child_doctype_meta.istable:
			mrinimitable.throw(
				_("Option {0} for field {1} is not a child table").format(
					mrinimitable.bold(doctype), mrinimitable.bold(docfield.fieldname)
				),
				title=_("Invalid Option"),
			)

		if meta.is_virtual != child_doctype_meta.is_virtual:
			error_msg = " should be virtual." if meta.is_virtual else " cannot be virtual."
			mrinimitable.throw(
				_("Child Table {0} for field {1}" + error_msg).format(
					mrinimitable.bold(doctype), mrinimitable.bold(docfield.fieldname)
				),
				title=_("Invalid Option"),
			)

	def check_max_height(docfield):
		if getattr(docfield, "max_height", None) and (docfield.max_height[-2:] not in ("px", "em")):
			mrinimitable.throw(f"Max for {mrinimitable.bold(docfield.fieldname)} height must be in px, em, rem")

	def check_no_of_ratings(docfield):
		if docfield.fieldtype == "Rating":
			if docfield.options and (int(docfield.options) > 10 or int(docfield.options) < 3):
				mrinimitable.throw(_("Options for Rating field can range from 3 to 10"))

	fields = meta.get("fields")
	fieldname_list = [d.fieldname for d in fields]

	in_ci = os.environ.get("CI")

	not_allowed_in_list_view = get_fields_not_allowed_in_list_view(meta)

	for d in fields:
		if not d.permlevel:
			d.permlevel = 0
		if d.fieldtype not in table_fields:
			d.allow_bulk_edit = 0

		check_illegal_characters(d.fieldname)
		check_invalid_fieldnames(meta.get("name"), d.fieldname)
		check_fieldname_length(d.fieldname)
		check_hidden_and_mandatory(meta.get("name"), d)
		check_unique_and_text(meta.get("name"), d)
		check_table_multiselect_option(d)
		scrub_options_in_select(d)
		validate_fetch_from(d)
		validate_data_field_type(d)

		if not mrinimitable.flags.in_migrate or in_ci:
			check_unique_fieldname(meta.get("name"), d.fieldname)
			check_link_table_options(meta.get("name"), d)
			check_illegal_mandatory(meta.get("name"), d)
			check_dynamic_link_options(d)
			check_in_list_view(meta.get("istable"), d)
			check_in_global_search(d)
			check_illegal_depends_on_conditions(d)
			check_illegal_default(d)
			check_child_table_option(d)
			check_max_height(d)
			check_no_of_ratings(d)

	if not mrinimitable.flags.in_migrate or in_ci:
		check_fold(fields)
		check_search_fields(meta, fields)
		check_title_field(meta)
		check_timeline_field(meta)
		check_is_published_field(meta)
		check_website_search_field(meta)
		check_sort_field(meta)
		check_image_field(meta)


def get_fields_not_allowed_in_list_view(meta) -> list[str]:
	not_allowed_in_list_view = list(copy.copy(no_value_fields))
	not_allowed_in_list_view.append("Attach Image")
	if meta.istable:
		not_allowed_in_list_view.remove("Button")
		not_allowed_in_list_view.remove("HTML")
	return not_allowed_in_list_view


def validate_permissions_for_doctype(doctype, for_remove=False, alert=False):
	"""Validates if permissions are set correctly."""
	doctype = mrinimitable.get_doc("DocType", doctype)
	validate_permissions(doctype, for_remove, alert=alert)

	# save permissions
	for perm in doctype.get("permissions"):
		perm.db_update()

	clear_permissions_cache(doctype.name)


def clear_permissions_cache(doctype):
	from mrinimitable.cache_manager import clear_user_cache

	mrinimitable.clear_cache(doctype=doctype)
	delete_notification_count_for(doctype)

	clear_user_cache()


def validate_permissions(doctype, for_remove=False, alert=False):
	permissions = doctype.get("permissions")
	# Some DocTypes may not have permissions by default, don't show alert for them
	if not permissions and alert:
		mrinimitable.msgprint(_("No Permissions Specified"), alert=True, indicator="orange")
	issingle = issubmittable = isimportable = False
	if doctype:
		issingle = cint(doctype.issingle)
		issubmittable = cint(doctype.is_submittable)
		isimportable = cint(doctype.allow_import)

	def get_txt(d):
		return _("For {0} at level {1} in {2} in row {3}").format(d.role, d.permlevel, d.parent, d.idx)

	def check_atleast_one_set(d):
		if not d.select and not d.read and not d.write and not d.submit and not d.cancel and not d.create:
			mrinimitable.throw(_("{0}: No basic permissions set").format(get_txt(d)))

	def check_double(d):
		has_similar = False
		similar_because_of = ""
		for p in permissions:
			if p.role == d.role and p.permlevel == d.permlevel and p != d:
				if p.if_owner == d.if_owner:
					similar_because_of = _("If Owner")
					has_similar = True
					break

		if has_similar:
			mrinimitable.throw(
				_("{0}: Only one rule allowed with the same Role, Level and {1}").format(
					get_txt(d), similar_because_of
				)
			)

	def check_level_zero_is_set(d):
		if cint(d.permlevel) > 0 and d.role not in (ALL_USER_ROLE, SYSTEM_USER_ROLE):
			has_zero_perm = False
			for p in permissions:
				if p.role == d.role and (p.permlevel or 0) == 0 and p != d:
					has_zero_perm = True
					break

			if not has_zero_perm:
				mrinimitable.throw(
					_("{0}: Permission at level 0 must be set before higher levels are set").format(
						get_txt(d)
					)
				)

			for invalid in ("create", "submit", "cancel", "amend"):
				if d.get(invalid):
					d.set(invalid, 0)

	def check_permission_dependency(d):
		if d.cancel and not d.submit:
			mrinimitable.throw(_("{0}: Cannot set Cancel without Submit").format(get_txt(d)))

		if (d.submit or d.cancel or d.amend) and not d.write:
			mrinimitable.throw(_("{0}: Cannot set Submit, Cancel, Amend without Write").format(get_txt(d)))
		if d.amend and not d.write:
			mrinimitable.throw(_("{0}: Cannot set Amend without Cancel").format(get_txt(d)))
		if d.get("import") and not d.create:
			mrinimitable.throw(_("{0}: Cannot set Import without Create").format(get_txt(d)))

	def remove_rights_for_single(d):
		if not issingle:
			return

		if d.report:
			mrinimitable.msgprint(_("Report cannot be set for Single types"))
			d.report = 0
			d.set("import", 0)
			d.set("export", 0)

	def check_if_submittable(d):
		if d.submit and not issubmittable:
			mrinimitable.throw(_("{0}: Cannot set Assign Submit if not Submittable").format(get_txt(d)))
		elif d.amend and not issubmittable:
			mrinimitable.throw(_("{0}: Cannot set Assign Amend if not Submittable").format(get_txt(d)))

	def check_if_importable(d):
		if d.get("import") and not isimportable:
			mrinimitable.throw(_("{0}: Cannot set import as {1} is not importable").format(get_txt(d), doctype))

	def validate_permission_for_all_role(d):
		if mrinimitable.session.user == "Administrator":
			return

		if doctype.custom:
			if d.role in AUTOMATIC_ROLES:
				mrinimitable.throw(
					_(
						"Row # {0}: Non administrator user can not set the role {1} to the custom doctype"
					).format(d.idx, mrinimitable.bold(_(d.role))),
					title=_("Permissions Error"),
				)

			roles = [row.name for row in mrinimitable.get_all("Role", filters={"is_custom": 1})]

			if d.role in roles:
				mrinimitable.throw(
					_(
						"Row # {0}: Non administrator user can not set the role {1} to the custom doctype"
					).format(d.idx, mrinimitable.bold(_(d.role))),
					title=_("Permissions Error"),
				)

	for d in permissions:
		if not d.permlevel:
			d.permlevel = 0
		check_atleast_one_set(d)
		if not for_remove:
			check_double(d)
			check_permission_dependency(d)
			check_if_submittable(d)
			check_if_importable(d)
		check_level_zero_is_set(d)
		remove_rights_for_single(d)
		validate_permission_for_all_role(d)


def make_module_and_roles(doc, perm_fieldname="permissions"):
	"""Make `Module Def` and `Role` records if already not made. Called while installing."""
	try:
		if (
			hasattr(doc, "restrict_to_domain")
			and doc.restrict_to_domain
			and not mrinimitable.db.exists("Domain", doc.restrict_to_domain)
		):
			mrinimitable.get_doc(doctype="Domain", domain=doc.restrict_to_domain).insert()

		if "tabModule Def" in mrinimitable.db.get_tables() and not mrinimitable.db.exists("Module Def", doc.module):
			m = mrinimitable.get_doc({"doctype": "Module Def", "module_name": doc.module})
			if mrinimitable.scrub(doc.module) in mrinimitable.local.module_app:
				m.app_name = mrinimitable.local.module_app[mrinimitable.scrub(doc.module)]
			else:
				m.app_name = "mrinimitable"
			m.flags.ignore_mandatory = m.flags.ignore_permissions = True
			if mrinimitable.flags.package:
				m.package = mrinimitable.flags.package.name
				m.custom = 1
			m.insert()

		roles = [p.role for p in doc.get("permissions") or []] + list(AUTOMATIC_ROLES)

		for role in list(set(roles)):
			if mrinimitable.db.table_exists("Role", cached=False) and not mrinimitable.db.exists("Role", role):
				r = mrinimitable.new_doc("Role")
				r.role_name = role
				r.desk_access = 1
				r.flags.ignore_mandatory = r.flags.ignore_permissions = True
				r.insert()
	except mrinimitable.DoesNotExistError:
		pass
	except mrinimitable.db.ProgrammingError as e:
		if mrinimitable.db.is_table_missing(e):
			pass
		else:
			raise


def check_fieldname_conflicts(docfield):
	"""Checks if fieldname conflicts with methods or properties"""
	doc = mrinimitable.get_doc({"doctype": docfield.dt})
	available_objects = [x for x in dir(doc) if isinstance(x, str)]
	property_list = [x for x in available_objects if is_a_property(getattr(type(doc), x, None))]
	method_list = [x for x in available_objects if x not in property_list and callable(getattr(doc, x))]
	msg = _("Fieldname {0} conflicting with meta object").format(docfield.fieldname)

	if docfield.fieldname in method_list + property_list:
		mrinimitable.msgprint(msg, raise_exception=not docfield.is_virtual)


def clear_linked_doctype_cache():
	mrinimitable.cache.delete_value("linked_doctypes_without_ignore_user_permissions_enabled")


def check_email_append_to(doc):
	if not hasattr(doc, "email_append_to") or not doc.email_append_to:
		return

	# Subject Field
	doc.subject_field = doc.subject_field.strip() if doc.subject_field else None
	subject_field = get_field(doc, doc.subject_field)

	if doc.subject_field and not subject_field:
		mrinimitable.throw(_("Select a valid Subject field for creating documents from Email"))

	if subject_field and subject_field.fieldtype not in [
		"Data",
		"Text",
		"Long Text",
		"Small Text",
		"Text Editor",
	]:
		mrinimitable.throw(_("Subject Field type should be Data, Text, Long Text, Small Text, Text Editor"))

	# Sender Field is mandatory
	doc.sender_field = doc.sender_field.strip() if doc.sender_field else None
	sender_field = get_field(doc, doc.sender_field)

	if doc.sender_field and not sender_field:
		mrinimitable.throw(_("Select a valid Sender Field for creating documents from Email"))

	if sender_field.options != "Email":
		mrinimitable.throw(_("Sender Field should have Email in options"))


def get_field(doc, fieldname):
	if not (doc or fieldname):
		return

	for field in doc.fields:
		if field.fieldname == fieldname:
			return field


@mrinimitable.whitelist()
def get_row_size_utilization(doctype: str) -> float:
	"""Get row size utilization in percentage"""

	mrinimitable.has_permission("DocType", throw=True)
	try:
		return flt(mrinimitable.db.get_row_size(doctype) / mrinimitable.db.MAX_ROW_SIZE_LIMIT * 100, 2)
	except Exception:
		return 0.0
