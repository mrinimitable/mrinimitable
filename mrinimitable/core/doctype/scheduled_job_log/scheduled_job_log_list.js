mrinimitable.listview_settings["Scheduled Job Log"] = {
	onload: function (listview) {
		mrinimitable.require("logtypes.bundle.js", () => {
			mrinimitable.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
