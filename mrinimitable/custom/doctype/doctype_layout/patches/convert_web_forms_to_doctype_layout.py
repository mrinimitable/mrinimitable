import mrinimitable


def execute():
	for web_form_name in mrinimitable.get_all("Web Form", pluck="name"):
		web_form = mrinimitable.get_doc("Web Form", web_form_name)
		doctype_layout = mrinimitable.get_doc(
			doctype="DocType Layout",
			document_type=web_form.doc_type,
			name=web_form.title,
			route=web_form.route,
			fields=[
				dict(fieldname=d.fieldname, label=d.label) for d in web_form.web_form_fields if d.fieldname
			],
		).insert()
		print(doctype_layout.name)
