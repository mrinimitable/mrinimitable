# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import shutil
from pathlib import Path

import mrinimitable
import mrinimitable.model
from mrinimitable.modules import get_module_path, scrub, scrub_dt_dn


def export_doc(doc):
	write_document_file(doc)


def export_to_files(record_list=None, record_module=None, verbose=0, create_init=None):
	"""
	Export record_list to files. record_list is a list of lists ([doctype, docname, folder name],)  ,
	"""
	if mrinimitable.flags.in_import:
		return

	if record_list:
		for record in record_list:
			folder_name = record[2] if len(record) == 3 else None
			write_document_file(
				mrinimitable.get_doc(record[0], record[1]),
				record_module,
				create_init=create_init,
				folder_name=folder_name,
			)


def write_document_file(doc, record_module=None, create_init=True, folder_name=None):
	doc_export = doc.as_dict(no_nulls=True)
	doc.run_method("before_export", doc_export)

	doc_export = strip_default_fields(doc, doc_export)
	module = record_module or get_module_name(doc)
	is_custom_module = mrinimitable.db.get_value("Module Def", module, "custom")

	# create folder
	if folder_name:
		folder = create_folder(module, folder_name, doc.name, create_init, is_custom_module)
	else:
		folder = create_folder(module, doc.doctype, doc.name, create_init, is_custom_module)

	fname = scrub(doc.name)
	write_code_files(folder, fname, doc, doc_export)

	# write the data file
	path = os.path.join(folder, f"{fname}.json")
	if is_custom_module and not Path(path).resolve().is_relative_to(Path(mrinimitable.get_site_path()).resolve()):
		mrinimitable.throw("Invalid export path: " + Path(path).as_posix())
	with open(path, "w+") as txtfile:
		txtfile.write(mrinimitable.as_json(doc_export) + "\n")
	print(f"Wrote document file for {doc.doctype} {doc.name} at {path}")


def strip_default_fields(doc, doc_export):
	# strip out default fields from children
	if doc.doctype == "DocType" and doc.migration_hash:
		del doc_export["migration_hash"]

	for df in doc.meta.get_table_fields():
		for d in doc_export.get(df.fieldname):
			for fieldname in mrinimitable.model.default_fields + mrinimitable.model.child_table_fields:
				if fieldname in d:
					del d[fieldname]

	return doc_export


def write_code_files(folder, fname, doc, doc_export):
	"""Export code files and strip from values"""
	if hasattr(doc, "get_code_fields"):
		for key, extn in doc.get_code_fields().items():
			if doc.get(key):
				path = os.path.join(folder, fname + "." + extn)
				if not Path(path).resolve().is_relative_to(Path(mrinimitable.get_site_path()).resolve()):
					mrinimitable.throw("Invalid export path: " + Path(path).as_posix())
				with open(path, "w+") as txtfile:
					txtfile.write(doc.get(key))

				# remove from exporting
				del doc_export[key]


def get_module_name(doc):
	if doc.doctype == "Module Def":
		module = doc.name
	elif doc.doctype == "Workflow":
		module = mrinimitable.db.get_value("DocType", doc.document_type, "module")
	elif hasattr(doc, "module"):
		module = doc.module
	else:
		module = mrinimitable.db.get_value("DocType", doc.doctype, "module")

	return module


def delete_folder(module, dt, dn):
	if mrinimitable.db.get_value("Module Def", module, "custom"):
		module_path = get_custom_module_path(module)
	else:
		module_path = get_module_path(module)

	dt, dn = scrub_dt_dn(dt, dn)

	# delete folder
	folder = os.path.join(module_path, dt, dn)

	if os.path.exists(folder):
		shutil.rmtree(folder)


def create_folder(module, dt, dn, create_init, is_custom_module):
	if is_custom_module:
		module_path = get_custom_module_path(module)
	else:
		module_path = get_module_path(module)

	dt, dn = scrub_dt_dn(dt, dn)

	# create folder
	folder = os.path.join(module_path, dt, dn)

	mrinimitable.create_folder(folder)

	# create init_py_files
	if create_init:
		create_init_py(module_path, dt, dn)

	return folder


def get_custom_module_path(module):
	package = mrinimitable.db.get_value("Module Def", module, "package")
	if not package:
		mrinimitable.throw(f"Package must be set for custom Module <b>{module}</b>")

	path = os.path.join(get_package_path(package), scrub(module))
	if not Path(path).resolve().is_relative_to(Path(mrinimitable.get_site_path()).resolve()):
		mrinimitable.throw("Invalid module path: " + Path(path).as_posix())

	if not os.path.exists(path):
		os.makedirs(path)

	return path


def get_package_path(package):
	path = os.path.join(
		mrinimitable.get_site_path("packages"), mrinimitable.db.get_value("Package", package, "package_name")
	)
	if not os.path.exists(path):
		os.makedirs(path)
	return path


def create_init_py(module_path, dt, dn):
	def create_if_not_exists(path):
		initpy = os.path.join(path, "__init__.py")
		if not os.path.exists(initpy):
			open(initpy, "w").close()

	create_if_not_exists(os.path.join(module_path))
	create_if_not_exists(os.path.join(module_path, dt))
	create_if_not_exists(os.path.join(module_path, dt, dn))
