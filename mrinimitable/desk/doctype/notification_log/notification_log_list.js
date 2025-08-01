mrinimitable.listview_settings["Notification Log"] = {
	onload: function (listview) {
		mrinimitable.require("logtypes.bundle.js", () => {
			mrinimitable.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
