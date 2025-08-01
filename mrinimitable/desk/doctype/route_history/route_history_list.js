mrinimitable.listview_settings["Route History"] = {
	onload: function (listview) {
		mrinimitable.require("logtypes.bundle.js", () => {
			mrinimitable.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
