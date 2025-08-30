// Copyright (c) 2020, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Workspace", {
	setup: function () {
		mrinimitable.meta.get_field("Workspace Link", "only_for").no_default = true;
	},

	refresh: function (frm) {
		frm.enable_save();

		let url = `/app/${
			frm.doc.public
				? mrinimitable.router.slug(frm.doc.title)
				: "private/" + mrinimitable.router.slug(frm.doc.title)
		}`;
		frm.sidebar
			.add_user_action(__("Go to Workspace"))
			.attr("href", url)
			.attr("target", "_blank");

		frm.layout.message.empty();
		let message = __("Please click Edit on the Workspace for best results");

		if (
			(frm.doc.for_user && frm.doc.for_user !== mrinimitable.session.user) ||
			(frm.doc.public && !mrinimitable.user.has_role("Workspace Manager"))
		) {
			frm.trigger("disable_form");

			if (frm.doc.public) {
				message = __("Only Workspace Manager can edit public workspaces");
			} else {
				message = __(
					"We do not allow editing of this document. Simply click the Edit button on the workspace page to make your workspace editable and customize it as you wish"
				);
			}
		}

		if (mrinimitable.boot.developer_mode) {
			frm.set_df_property("module", "read_only", 0);
		}

		frm.layout.show_message(message);
	},

	disable_form: function (frm) {
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},
});
