// Copyright (c) 2017, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Print Style", {
	refresh: function (frm) {
		frm.add_custom_button(__("Print Settings"), () => {
			mrinimitable.set_route("Form", "Print Settings");
		});
	},
});
