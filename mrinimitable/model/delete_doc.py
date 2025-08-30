# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import shutil

import mrinimitable
import mrinimitable.defaults
import mrinimitable.model.meta
from mrinimitable import _, get_module_path
from mrinimitable.desk.doctype.tag.tag import delete_tags_for_document
from mrinimitable.model.docstatus import DocStatus
from mrinimitable.model.dynamic_links import get_dynamic_link_map
from mrinimitable.model.naming import revert_series_if_last
from mrinimitable.model.utils import is_virtual_doctype
from mrinimitable.utils.data import get_link_to_form
from mrinimitable.utils.file_manager import remove_all
from mrinimitable.utils.global_search import delete_for_document
from mrinimitable.utils.password import delete_all_passwords_for


def delete_doc(
	doctype=None,
	name=None,
	force=0,
	ignore_doctypes=None,
	for_reload=False,
	ignore_permissions=False,
	flags=None,
	ignore_on_trash=False,
	ignore_missing=True,
	delete_permanently=False,
):
	"""
	Deletes a doc(dt, dn) and validates if it is not submitted and not linked in a live record
	"""
	if not ignore_doctypes:
		ignore_doctypes = []

	# get from form
	if not doctype:
		doctype = mrinimitable.form_dict.get("dt")
		name = mrinimitable.form_dict.get("dn")

	is_virtual = is_virtual_doctype(doctype)

	names = name
	if isinstance(name, str) or isinstance(name, int):
		names = [name]

	for name in names or []:
		if is_virtual:
			mrinimitable.get_doc(doctype, name).delete()
			continue

		# already deleted..?
		if not mrinimitable.db.exists(doctype, name):
			if not ignore_missing:
				raise mrinimitable.DoesNotExistError(doctype=doctype)
			else:
				return False

		# delete passwords
		delete_all_passwords_for(doctype, name)

		doc = None
		if doctype == "DocType":
			if for_reload:
				try:
					doc = mrinimitable.get_doc(doctype, name)
				except mrinimitable.DoesNotExistError:
					pass
				else:
					doc.run_method("before_reload")

			else:
				doc = mrinimitable.get_doc(doctype, name)
				if not (doc.custom or mrinimitable.conf.developer_mode or mrinimitable.flags.in_patch or force):
					mrinimitable.throw(_("Standard DocType can not be deleted."))

				update_flags(doc, flags, ignore_permissions)
				check_permission_and_not_submitted(doc)
				# delete custom table fields using this doctype.
				mrinimitable.db.delete(
					"Custom Field", {"options": name, "fieldtype": ("in", mrinimitable.model.table_fields)}
				)
				mrinimitable.db.delete("__global_search", {"doctype": name})

			delete_from_table(doctype, name, ignore_doctypes, None)

			if (
				mrinimitable.conf.developer_mode
				and not doc.custom
				and not (
					for_reload
					or mrinimitable.flags.in_migrate
					or mrinimitable.flags.in_install
					or mrinimitable.flags.in_uninstall
				)
			):
				try:
					delete_controllers(name, doc.module)
				except (OSError, KeyError):
					# in case a doctype doesnt have any controller code  nor any app and module
					pass

		else:
			# Lock the doc without waiting
			try:
				mrinimitable.db.get_value(doctype, name, for_update=True, wait=False)
			except (mrinimitable.QueryTimeoutError, mrinimitable.QueryDeadlockError):
				mrinimitable.throw(
					_(
						"This document can not be deleted right now as it's being modified by another user. Please try again after some time."
					),
					exc=mrinimitable.QueryTimeoutError,
				)
			doc = mrinimitable.get_doc(doctype, name)

			if not for_reload:
				update_flags(doc, flags, ignore_permissions)
				check_permission_and_not_submitted(doc)

				if not ignore_on_trash:
					doc.run_method("on_trash")
					doc.flags.in_delete = True
					doc.run_method("on_change")

				# check if links exist
				if not force:
					try:
						check_if_doc_is_linked(doc)
						check_if_doc_is_dynamically_linked(doc)
					except mrinimitable.LinkExistsError as e:
						if doc.meta.has_field("enabled") or doc.meta.has_field("disabled"):
							mrinimitable.throw(
								_("You can disable this {0} instead of deleting it.").format(_(doctype)),
								mrinimitable.LinkExistsError,
							)
						else:
							raise e

			update_naming_series(doc)
			delete_from_table(doctype, name, ignore_doctypes, doc)
			doc.run_method("after_delete")

			# delete attachments
			remove_all(doctype, name, from_delete=True, delete_permanently=delete_permanently)

			if not for_reload:
				# Enqueued at the end, because it gets committed
				# All the linked docs should be checked beforehand
				mrinimitable.enqueue(
					"mrinimitable.model.delete_doc.delete_dynamic_links",
					doctype=doc.doctype,
					name=doc.name,
					now=mrinimitable.in_test,
					enqueue_after_commit=True,
				)

		# clear cache for Document
		doc.clear_cache()
		# delete global search entry
		delete_for_document(doc)
		# delete tag link entry
		delete_tags_for_document(doc)

		if for_reload:
			delete_permanently = True

		if not delete_permanently:
			add_to_deleted_document(doc)

		if doc and not for_reload:
			if not mrinimitable.flags.in_patch:
				try:
					doc.notify_update()
					insert_feed(doc)
				except ImportError:
					pass


def add_to_deleted_document(doc):
	"""Add this document to Deleted Document table. Called after delete"""
	if doc.doctype != "Deleted Document" and mrinimitable.flags.in_install != "mrinimitable":
		mrinimitable.get_doc(
			doctype="Deleted Document",
			deleted_doctype=doc.doctype,
			deleted_name=doc.name,
			data=doc.as_json(),
			owner=mrinimitable.session.user,
		).db_insert()


def update_naming_series(doc):
	if doc.meta.autoname:
		if doc.meta.autoname.startswith("naming_series:") and getattr(doc, "naming_series", None):
			revert_series_if_last(doc.naming_series, doc.name, doc)

		elif doc.meta.autoname.split(":", 1)[0] not in ("Prompt", "field", "hash", "autoincrement"):
			revert_series_if_last(doc.meta.autoname, doc.name, doc)


def delete_from_table(doctype: str, name: str, ignore_doctypes: list[str], doc):
	if doctype != "DocType" and doctype == name:
		mrinimitable.db.delete("Singles", {"doctype": name})
	else:
		mrinimitable.db.delete(doctype, {"name": name})
	if doc:
		child_doctypes = [
			d.options for d in doc.meta.get_table_fields() if mrinimitable.get_meta(d.options).is_virtual == 0
		]

	else:
		child_doctypes = mrinimitable.get_all(
			"DocField",
			fields="options",
			filters={"fieldtype": ["in", mrinimitable.model.table_fields], "parent": doctype},
			pluck="options",
		)

	child_doctypes_to_delete = set(child_doctypes) - set(ignore_doctypes)
	for child_doctype in child_doctypes_to_delete:
		mrinimitable.db.delete(child_doctype, {"parenttype": doctype, "parent": name})


def update_flags(doc, flags=None, ignore_permissions=False):
	if ignore_permissions:
		if not flags:
			flags = {}
		flags["ignore_permissions"] = ignore_permissions

	if flags:
		doc.flags.update(flags)


def check_permission_and_not_submitted(doc):
	# permission
	if not doc.flags.ignore_permissions and mrinimitable.session.user != "Administrator":
		if doc.doctype == "DocType" and not doc.custom:
			mrinimitable.throw(_("Only the Administrator can delete a standard DocType."))
		else:
			doc.check_permission("delete")

	# check if submitted
	if doc.meta.is_submittable and doc.docstatus.is_submitted():
		mrinimitable.msgprint(
			_("{0} {1}: Submitted Record cannot be deleted. You must {2} Cancel {3} it first.").format(
				_(doc.doctype),
				doc.name,
				"<a href='https://docs.okayblue.com//docs/user/manual/en/setting-up/articles/delete-submitted-document' target='_blank'>",
				"</a>",
			),
			raise_exception=True,
		)


def check_if_doc_is_linked(doc, method="Delete"):
	"""
	Raises exception if the given document is linked in another record.
	"""
	from mrinimitable.model.rename_doc import get_link_fields

	link_fields = get_link_fields(doc.doctype)
	ignored_doctypes = set()

	if method == "Cancel" and (doc_ignore_flags := doc.get("ignore_linked_doctypes")):
		ignored_doctypes.update(doc_ignore_flags)
	if method == "Delete":
		ignored_doctypes.update(mrinimitable.get_hooks("ignore_links_on_delete"))

	for lf in link_fields:
		link_dt, link_field, issingle = lf["parent"], lf["fieldname"], lf["issingle"]
		if link_dt in ignored_doctypes or (link_field == "amended_from" and method == "Cancel"):
			continue

		try:
			meta = mrinimitable.get_meta(link_dt)
		except mrinimitable.DoesNotExistError:
			mrinimitable.clear_last_message()
			# This mostly happens when app do not remove their customizations, we shouldn't
			# prevent link checks from failing in those cases
			continue

		if issingle:
			if mrinimitable.db.get_single_value(link_dt, link_field) == doc.name:
				raise_link_exists_exception(doc, link_dt, link_dt)
			continue

		fields = ["name", "docstatus"]

		if meta.istable:
			fields.extend(["parent", "parenttype"])

		for item in mrinimitable.db.get_values(link_dt, {link_field: doc.name}, fields, as_dict=True):
			# available only in child table cases
			item_parent = getattr(item, "parent", None)
			linked_parent_doctype = item.parenttype if item_parent else link_dt

			if linked_parent_doctype in ignored_doctypes:
				continue

			if method != "Delete" and (method != "Cancel" or not DocStatus(item.docstatus).is_submitted()):
				# don't raise exception if not
				# linked to a non-cancelled doc when deleting or to a submitted doc when cancelling
				continue
			elif link_dt == doc.doctype and (item_parent or item.name) == doc.name:
				# don't raise exception if not
				# linked to same item or doc having same name as the item
				continue
			else:
				reference_docname = item_parent or item.name
				raise_link_exists_exception(doc, linked_parent_doctype, reference_docname)


def check_if_doc_is_dynamically_linked(doc, method="Delete"):
	"""Raise `mrinimitable.LinkExistsError` if the document is dynamically linked"""
	for df in get_dynamic_link_map().get(doc.doctype, []):
		ignore_linked_doctypes = doc.get("ignore_linked_doctypes") or []

		if df.parent in mrinimitable.get_hooks("ignore_links_on_delete") or (
			df.parent in ignore_linked_doctypes and method == "Cancel"
		):
			# don't check for communication and todo!
			continue

		meta = mrinimitable.get_meta(df.parent)
		if meta.issingle:
			# dynamic link in single doc
			refdoc = mrinimitable.db.get_singles_dict(df.parent)
			if (
				refdoc.get(df.options) == doc.doctype
				and refdoc.get(df.fieldname) == doc.name
				and (
					# linked to an non-cancelled doc when deleting
					(method == "Delete" and not DocStatus(refdoc.docstatus).is_cancelled())
					# linked to a submitted doc when cancelling
					or (method == "Cancel" and DocStatus(refdoc.docstatus).is_submitted())
				)
			):
				raise_link_exists_exception(doc, df.parent, df.parent)
		else:
			# dynamic link in table
			df["table"] = ", `parent`, `parenttype`, `idx`" if meta.istable else ""
			for refdoc in mrinimitable.db.sql(
				"""select `name`, `docstatus` {table} from `tab{parent}` where
				`{options}`=%s and `{fieldname}`=%s""".format(**df),
				(doc.doctype, doc.name),
				as_dict=True,
			):
				# linked to an non-cancelled doc when deleting
				# or linked to a submitted doc when cancelling
				if (method == "Delete" and not DocStatus(refdoc.docstatus).is_cancelled()) or (
					method == "Cancel" and DocStatus(refdoc.docstatus).is_submitted()
				):
					reference_doctype = refdoc.parenttype if meta.istable else df.parent
					reference_docname = refdoc.parent if meta.istable else refdoc.name

					if reference_doctype in mrinimitable.get_hooks("ignore_links_on_delete") or (
						reference_doctype in ignore_linked_doctypes and method == "Cancel"
					):
						# don't check for communication and todo!
						continue

					at_position = f"at Row: {refdoc.idx}" if meta.istable else ""

					raise_link_exists_exception(doc, reference_doctype, reference_docname, at_position)


def raise_link_exists_exception(doc, reference_doctype, reference_docname, row=""):
	doc_link = get_link_to_form(doc.doctype, doc.name, doc.name)
	reference_link = get_link_to_form(reference_doctype, reference_docname, reference_docname)

	# hack to display Single doctype only once in message
	if reference_doctype == reference_docname:
		reference_doctype = ""

	mrinimitable.throw(
		_("Cannot delete or cancel because {0} {1} is linked with {2} {3} {4}").format(
			_(doc.doctype), doc_link, _(reference_doctype), reference_link, row
		),
		mrinimitable.LinkExistsError,
	)


def delete_dynamic_links(doctype, name):
	delete_references("ToDo", doctype, name, "reference_type")
	delete_references("Email Unsubscribe", doctype, name)
	delete_references("DocShare", doctype, name, "share_doctype", "share_name")
	delete_references("Version", doctype, name, "ref_doctype", "docname")
	delete_references("Comment", doctype, name)
	delete_references("View Log", doctype, name)
	delete_references("Document Follow", doctype, name, "ref_doctype", "ref_docname")
	delete_references("Notification Log", doctype, name, "document_type", "document_name")

	# unlink communications
	clear_timeline_references(doctype, name)
	clear_references("Communication", doctype, name)

	clear_references("Activity Log", doctype, name)
	clear_references("Activity Log", doctype, name, "timeline_doctype", "timeline_name")


def delete_references(
	doctype,
	reference_doctype,
	reference_name,
	reference_doctype_field="reference_doctype",
	reference_name_field="reference_name",
):
	mrinimitable.db.delete(
		doctype, {reference_doctype_field: reference_doctype, reference_name_field: reference_name}
	)


def clear_references(
	doctype,
	reference_doctype,
	reference_name,
	reference_doctype_field="reference_doctype",
	reference_name_field="reference_name",
):
	mrinimitable.db.sql(
		f"""update
			`tab{doctype}`
		set
			{reference_doctype_field}=NULL, {reference_name_field}=NULL
		where
			{reference_doctype_field}=%s and {reference_name_field}=%s""",  # nosec
		(reference_doctype, reference_name),
	)


def clear_timeline_references(link_doctype, link_name):
	mrinimitable.db.delete("Communication Link", {"link_doctype": link_doctype, "link_name": link_name})


def insert_feed(doc):
	if (
		mrinimitable.flags.in_install
		or mrinimitable.flags.in_uninstall
		or mrinimitable.flags.in_import
		or getattr(doc, "no_feed_on_delete", False)
	):
		return

	from mrinimitable.utils import get_fullname

	mrinimitable.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Deleted",
			"reference_doctype": doc.doctype,
			"subject": f"{_(doc.doctype)} {doc.name}",
			"full_name": get_fullname(doc.owner),
		}
	).insert(ignore_permissions=True)


def delete_controllers(doctype, module):
	"""
	Delete controller code in the doctype folder
	"""
	module_path = get_module_path(module)
	dir_path = os.path.join(module_path, "doctype", mrinimitable.scrub(doctype))

	shutil.rmtree(dir_path)
