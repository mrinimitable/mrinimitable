mrinimitable.provide("mrinimitable.ui.misc");
mrinimitable.ui.misc.about = function () {
	if (!mrinimitable.ui.misc.about_dialog) {
		var d = new mrinimitable.ui.Dialog({ title: __("Mrinimitable Framework") });

		$(d.body).html(
			repl(
				`<div>
					<p>${__("Open Source Applications for the Web")}</p>
					<p><i class='fa fa-globe fa-fw'></i>
						${__("Website")}:
						<a href='https://mrinimitableframework.com' target='_blank'>https://mrinimitableframework.com</a></p>
					<p><i class='fa fa-github fa-fw'></i>
						${__("Source")}:
						<a href='https://github.com/mrinimitable' target='_blank'>https://github.com/mrinimitable</a></p>
					<p><i class='fa fa-graduation-cap fa-fw'></i>
						Mrinimitable School: <a href='https://mrinimitable.school' target='_blank'>https://mrinimitable.school</a></p>
					<p><i class='fa fa-linkedin fa-fw'></i>
						Linkedin: <a href='https://linkedin.com/company/mrinimitable-tech' target='_blank'>https://linkedin.com/company/mrinimitable-tech</a></p>
					<p><i class='fa fa-twitter fa-fw'></i>
						Twitter: <a href='https://twitter.com/mrinimitabletech' target='_blank'>https://twitter.com/mrinimitabletech</a></p>
					<p><i class='fa fa-youtube fa-fw'></i>
						YouTube: <a href='https://www.youtube.com/@mrinimitabletech' target='_blank'>https://www.youtube.com/@mrinimitabletech</a></p>
					<hr>
					<h4>${__("Installed Apps")}</h4>
					<div id='about-app-versions'>${__("Loading versions...")}</div>
					<p>
						<b>
							<a href="/attribution" target="_blank" class="text-muted">
								${__("Dependencies & Licenses")}
							</a>
						</b>
					</p>
					<hr>
					<p class='text-muted'>${__("&copy; Mrinimitable Technologies Pvt. Ltd. and contributors")} </p>
					</div>`,
				mrinimitable.app
			)
		);

		mrinimitable.ui.misc.about_dialog = d;

		mrinimitable.ui.misc.about_dialog.on_page_show = function () {
			if (!mrinimitable.versions) {
				mrinimitable.call({
					method: "mrinimitable.utils.change_log.get_versions",
					callback: function (r) {
						show_versions(r.message);
					},
				});
			} else {
				show_versions(mrinimitable.versions);
			}
		};

		var show_versions = function (versions) {
			var $wrap = $("#about-app-versions").empty();
			$.each(Object.keys(versions).sort(), function (i, key) {
				var v = versions[key];
				let text;
				if (v.branch) {
					text = $.format("<p><b>{0}:</b> v{1} ({2})<br></p>", [
						v.title,
						v.branch_version || v.version,
						v.branch,
					]);
				} else {
					text = $.format("<p><b>{0}:</b> v{1}<br></p>", [v.title, v.version]);
				}
				$(text).appendTo($wrap);
			});

			mrinimitable.versions = versions;
		};
	}

	mrinimitable.ui.misc.about_dialog.show();
};
