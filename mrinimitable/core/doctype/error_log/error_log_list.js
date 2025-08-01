mrinimitable.listview_settings["Error Log"] = {
	add_fields: ["seen"],
	get_indicator: function (doc) {
		if (cint(doc.seen)) {
			return [__("Seen"), "green", "seen,=,1"];
		} else {
			return [__("Not Seen"), "red", "seen,=,0"];
		}
	},
	order_by: "creation desc",
	onload: function (listview) {
		listview.page.add_menu_item(__("Clear Error Logs"), function () {
			mrinimitable.call({
				method: "mrinimitable.core.doctype.error_log.error_log.clear_error_logs",
				callback: function () {
					listview.refresh();
				},
			});
		});

		mrinimitable.require("logtypes.bundle.js", () => {
			mrinimitable.utils.logtypes.show_log_retention_message(cur_list.doctype);
		});
	},
};
