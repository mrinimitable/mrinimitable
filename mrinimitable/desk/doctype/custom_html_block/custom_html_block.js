// Copyright (c) 2023, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Custom HTML Block", {
	refresh(frm) {
		if (
			!has_common(mrinimitable.user_roles, [
				"Administrator",
				"System Manager",
				"Workspace Manager",
			])
		) {
			frm.set_value("private", true);
		} else {
			frm.set_df_property("private", "read_only", false);
		}

		let wrapper = frm.fields_dict["preview"].wrapper;
		wrapper.classList.add("mb-3");

		mrinimitable.create_shadow_element(wrapper, frm.doc.html, frm.doc.style, frm.doc.script);
	},
});
