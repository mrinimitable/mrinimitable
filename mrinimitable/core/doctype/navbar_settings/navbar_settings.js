// Copyright (c) 2020, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Navbar Settings", {
	after_save: function (frm) {
		mrinimitable.ui.toolbar.clear_cache();
	},
});
