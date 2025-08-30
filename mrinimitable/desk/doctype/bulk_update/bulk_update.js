// Copyright (c) 2016, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Bulk Update", {
	refresh: function (frm) {
		frm.set_query("document_type", function () {
			return {
				filters: [
					["DocType", "issingle", "=", 0],
					["DocType", "name", "not in", mrinimitable.model.core_doctypes_list],
				],
			};
		});

		frm.page.set_primary_action(__("Update"), function () {
			if (!frm.doc.update_value) {
				mrinimitable.throw(__('Field "value" is mandatory. Please specify value to be updated'));
			} else {
				frm.call("bulk_update").then((r) => {
					let failed = r.message;
					if (!failed) failed = [];

					if (failed.length && !r._server_messages) {
						mrinimitable.throw(
							__("Cannot update {0}", [
								failed.map((f) => (f.bold ? f.bold() : f)).join(", "),
							])
						);
					} else {
						mrinimitable.msgprint({
							title: __("Success"),
							message: __("Updated Successfully"),
							indicator: "green",
						});
					}

					mrinimitable.hide_progress();
					frm.save();
				});
			}
		});
	},

	document_type: function (frm) {
		// set field options
		if (!frm.doc.document_type) return;

		mrinimitable.model.with_doctype(frm.doc.document_type, function () {
			var options = $.map(mrinimitable.get_meta(frm.doc.document_type).fields, function (d) {
				if (d.fieldname && mrinimitable.model.no_value_type.indexOf(d.fieldtype) === -1) {
					return d.fieldname;
				}
				return null;
			});
			frm.set_df_property("field", "options", options);
		});
	},
});
