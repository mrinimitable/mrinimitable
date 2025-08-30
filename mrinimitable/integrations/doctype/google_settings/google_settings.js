// Copyright (c) 2019, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Google Settings", {
	refresh: function (frm) {
		frm.dashboard.set_headline(
			__("For more information, {0}.", [
				`<a href='https://okayblue.com/docs/user/manual/en/google_settings'>${__(
					"Click here"
				)}</a>`,
			])
		);
	},
});
