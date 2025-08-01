// Copyright (c) 2020, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Module Onboarding", {
	refresh: function (frm) {
		mrinimitable.boot.developer_mode &&
			frm.set_intro(
				__(
					"Saving this will export this document as well as the steps linked here as json."
				),
				true
			);
		if (!mrinimitable.boot.developer_mode) {
			frm.trigger("disable_form");
		}

		frm.add_custom_button(__("Reset"), () => {
			frm.call("reset_progress");
		});
	},

	disable_form: function (frm) {
		frm.set_read_only();
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},
});
