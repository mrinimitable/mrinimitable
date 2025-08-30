import json

from werkzeug.routing import Rule

import mrinimitable
from mrinimitable import _
from mrinimitable.utils.data import sbool


def document_list(doctype: str):
	if mrinimitable.form_dict.get("fields"):
		mrinimitable.form_dict["fields"] = json.loads(mrinimitable.form_dict["fields"])

	# set limit of records for mrinimitable.get_list
	mrinimitable.form_dict.setdefault(
		"limit_page_length",
		mrinimitable.form_dict.limit or mrinimitable.form_dict.limit_page_length or 20,
	)

	# convert strings to native types - only as_dict and debug accept bool
	for param in ["as_dict", "debug"]:
		param_val = mrinimitable.form_dict.get(param)
		if param_val is not None:
			mrinimitable.form_dict[param] = sbool(param_val)

	# evaluate mrinimitable.get_list
	return mrinimitable.call(mrinimitable.client.get_list, doctype, **mrinimitable.form_dict)


def handle_rpc_call(method: str):
	import mrinimitable.handler

	method = method.split("/")[0]  # for backward compatiblity

	mrinimitable.form_dict.cmd = method
	return mrinimitable.handler.handle()


def create_doc(doctype: str):
	data = get_request_form_data()
	data.pop("doctype", None)
	return mrinimitable.new_doc(doctype, **data).insert()


def update_doc(doctype: str, name: str):
	data = get_request_form_data()

	doc = mrinimitable.get_doc(doctype, name, for_update=True)
	if "flags" in data:
		del data["flags"]

	doc.update(data)
	doc.save()

	# check for child table doctype
	if doc.get("parenttype"):
		mrinimitable.get_doc(doc.parenttype, doc.parent).save()

	return doc


def delete_doc(doctype: str, name: str):
	# TODO: child doc handling
	mrinimitable.delete_doc(doctype, name, ignore_missing=False)
	mrinimitable.response.http_status_code = 202
	return "ok"


def read_doc(doctype: str, name: str):
	# Backward compatiblity
	if "run_method" in mrinimitable.form_dict:
		return execute_doc_method(doctype, name)

	doc = mrinimitable.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	return doc


def execute_doc_method(doctype: str, name: str, method: str | None = None):
	method = method or mrinimitable.form_dict.pop("run_method")
	doc = mrinimitable.get_doc(doctype, name)
	doc.is_whitelisted(method)

	if mrinimitable.request.method == "GET":
		doc.check_permission("read")
		return doc.run_method(method, **mrinimitable.form_dict)

	elif mrinimitable.request.method == "POST":
		doc.check_permission("write")
		return doc.run_method(method, **mrinimitable.form_dict)


def get_request_form_data():
	if mrinimitable.form_dict.data is None:
		data = mrinimitable.safe_decode(mrinimitable.request.get_data())
	else:
		data = mrinimitable.form_dict.data

	try:
		return mrinimitable.parse_json(data)
	except ValueError:
		return mrinimitable.form_dict


url_rules = [
	Rule("/method/<path:method>", endpoint=handle_rpc_call),
	Rule("/resource/<doctype>", methods=["GET"], endpoint=document_list),
	Rule("/resource/<doctype>", methods=["POST"], endpoint=create_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["GET"], endpoint=read_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["PUT"], endpoint=update_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["DELETE"], endpoint=delete_doc),
	Rule("/resource/<doctype>/<path:name>/", methods=["POST"], endpoint=execute_doc_method),
]
