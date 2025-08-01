// Copyright (c) 2017, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.webhook = {
	set_fieldname_select: (frm) => {
		if (frm.doc.webhook_doctype) {
			mrinimitable.model.with_doctype(frm.doc.webhook_doctype, () => {
				// get doctype fields
				let fields = $.map(
					mrinimitable.get_doc("DocType", frm.doc.webhook_doctype).fields,
					(d) => {
						if (
							mrinimitable.model.no_value_type.includes(d.fieldtype) &&
							!mrinimitable.model.table_fields.includes(d.fieldtype)
						) {
							return null;
						} else {
							return {
								label: `${__(d.label, null, d.parent)} (${__(d.fieldtype)})`,
								value: d.fieldname,
							};
						}
					}
				);

				// add meta fields
				for (let field of mrinimitable.model.std_fields) {
					if (field.fieldname == "name") {
						fields.unshift({ label: __("Name (Doc Name)"), value: "name" });
					} else {
						fields.push({
							label: `${__(field.label, null, field.parent)} (${__(
								field.fieldtype
							)})`,
							value: field.fieldname,
						});
					}
				}

				frm.fields_dict.webhook_data.grid.update_docfield_property(
					"fieldname",
					"options",
					[""].concat(fields)
				);
			});
		}
	},

	set_request_headers: (frm) => {
		if (frm.doc.request_structure) {
			let header_value;
			if (frm.doc.request_structure == "Form URL-Encoded") {
				header_value = "application/x-www-form-urlencoded";
			} else if (frm.doc.request_structure == "JSON") {
				header_value = "application/json";
			}

			if (header_value) {
				let header_row = (frm.doc.webhook_headers || []).find(
					(row) => row.key === "Content-Type"
				);
				if (header_row) {
					mrinimitable.model.set_value(
						header_row.doctype,
						header_row.name,
						"value",
						header_value
					);
				} else {
					frm.add_child("webhook_headers", {
						key: "Content-Type",
						value: header_value,
					});
				}
				frm.refresh();
			}
		}
	},
};

mrinimitable.ui.form.on("Webhook", {
	refresh: (frm) => {
		mrinimitable.webhook.set_fieldname_select(frm);
		frm.set_query(
			"background_jobs_queue",
			"mrinimitable.integrations.doctype.webhook.webhook.get_all_queues"
		);

		if (frm.doc.webhook_doctype) {
			frm.add_custom_button(__("Preview"), () => {
				const args = {
					doc: frm.doc,
					doctype: frm.doc.webhook_doctype,
					preview_fields: [
						{
							label: __("Meets Condition?"),
							fieldtype: "Data",
							method: "preview_meets_condition",
						},
						{
							label: __("Request Body"),
							fieldtype: "Code",
							method: "preview_request_body",
						},
					],
				};
				let dialog = new mrinimitable.views.RenderPreviewer(args);
				return dialog;
			});
		}
	},

	request_structure: (frm) => {
		mrinimitable.webhook.set_request_headers(frm);
	},

	webhook_doctype: (frm) => {
		mrinimitable.webhook.set_fieldname_select(frm);
	},

	enable_security: (frm) => {
		frm.toggle_reqd("webhook_secret", frm.doc.enable_security);
	},
});

mrinimitable.ui.form.on("Webhook Data", {
	fieldname: (frm, cdt, cdn) => {
		let row = locals[cdt][cdn];
		let df = mrinimitable
			.get_meta(frm.doc.webhook_doctype)
			.fields.filter((field) => field.fieldname == row.fieldname);

		if (!df.length) {
			// check if field is a meta field
			df = mrinimitable.model.std_fields.filter((field) => field.fieldname == row.fieldname);
		}

		row.key = df.length ? df[0].fieldname : "name";
		frm.refresh_field("webhook_data");
	},
});
