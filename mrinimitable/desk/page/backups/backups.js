mrinimitable.pages["backups"].on_page_load = function (wrapper) {
	var page = mrinimitable.ui.make_app_page({
		parent: wrapper,
		title: __("Download Backups"),
		single_column: true,
	});

	page.add_inner_button(__("Set Number of Backups"), function () {
		mrinimitable.set_route("Form", "System Settings").then(() => {
			cur_frm.scroll_to_field("backup_limit");
		});
	});

	page.add_inner_button(__("Download Files Backup"), function () {
		mrinimitable.call({
			method: "mrinimitable.desk.page.backups.backups.schedule_files_backup",
			args: { user_email: mrinimitable.session.user_email },
		});
	});

	page.add_inner_button(__("Get Backup Encryption Key"), function () {
		if (mrinimitable.user.has_role("System Manager")) {
			mrinimitable.verify_password(function () {
				mrinimitable.call({
					method: "mrinimitable.utils.backups.get_backup_encryption_key",
					callback: function (r) {
						mrinimitable.msgprint({
							title: __("Backup Encryption Key"),
							message: __(r.message),
							indicator: "blue",
						});
					},
				});
			});
		} else {
			mrinimitable.msgprint({
				title: __("Error"),
				message: __("System Manager privileges required."),
				indicator: "red",
			});
		}
	});

	mrinimitable.breadcrumbs.add("Setup");

	$(mrinimitable.render_template("backups")).appendTo(page.body.addClass("no-border"));
};
