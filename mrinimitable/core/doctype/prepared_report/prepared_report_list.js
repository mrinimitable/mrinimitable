mrinimitable.listview_settings["Prepared Report"] = {
	onload: function (list_view) {
		mrinimitable.require("logtypes.bundle.js", () => {
			mrinimitable.utils.logtypes.show_log_retention_message(list_view.doctype);
		});
	},
};
