mrinimitable.user_info = function (uid) {
	if (!uid) uid = mrinimitable.session.user;

	let user_info;
	if (!(mrinimitable.boot.user_info && mrinimitable.boot.user_info[uid])) {
		user_info = { fullname: uid || "Unknown" };
	} else {
		user_info = mrinimitable.boot.user_info[uid];
	}

	user_info.abbr = mrinimitable.get_abbr(user_info.fullname);
	user_info.color = mrinimitable.get_palette(user_info.fullname);

	return user_info;
};

mrinimitable.update_user_info = function (user_info) {
	for (let user in user_info) {
		if (mrinimitable.boot.user_info[user]) {
			Object.assign(mrinimitable.boot.user_info[user], user_info[user]);
		} else {
			mrinimitable.boot.user_info[user] = user_info[user];
		}
	}
};

mrinimitable.provide("mrinimitable.user");

$.extend(mrinimitable.user, {
	name: "Guest",
	full_name: function (uid) {
		return uid === mrinimitable.session.user
			? __(
					"You",
					null,
					"Name of the current user. For example: You edited this 5 hours ago."
			  )
			: mrinimitable.user_info(uid).fullname;
	},
	image: function (uid) {
		return mrinimitable.user_info(uid).image;
	},
	abbr: function (uid) {
		return mrinimitable.user_info(uid).abbr;
	},
	has_role: function (rl) {
		if (typeof rl == "string") rl = [rl];
		for (var i in rl) {
			if ((mrinimitable.boot ? mrinimitable.boot.user.roles : ["Guest"]).indexOf(rl[i]) != -1)
				return true;
		}
	},
	get_desktop_items: function () {
		// hide based on permission
		var modules_list = $.map(mrinimitable.boot.allowed_modules, function (icon) {
			var m = icon.module_name;
			var type = mrinimitable.modules[m] && mrinimitable.modules[m].type;

			if (mrinimitable.boot.user.allow_modules.indexOf(m) === -1) return null;

			var ret = null;
			if (type === "module") {
				if (mrinimitable.boot.user.allow_modules.indexOf(m) != -1 || mrinimitable.modules[m].is_help)
					ret = m;
			} else if (type === "page") {
				if (mrinimitable.boot.allowed_pages.indexOf(mrinimitable.modules[m].link) != -1) ret = m;
			} else if (type === "list") {
				if (mrinimitable.model.can_read(mrinimitable.modules[m]._doctype)) ret = m;
			} else if (type === "view") {
				ret = m;
			} else if (type === "setup") {
				if (
					mrinimitable.user.has_role("System Manager") ||
					mrinimitable.user.has_role("Administrator")
				)
					ret = m;
			} else {
				ret = m;
			}

			return ret;
		});

		return modules_list;
	},

	is_report_manager: function () {
		return mrinimitable.user.has_role(["Administrator", "System Manager", "Report Manager"]);
	},

	get_formatted_email: function (email) {
		var fullname = mrinimitable.user.full_name(email);

		if (!fullname) {
			return email;
		} else {
			// to quote or to not
			var quote = "";

			// only if these special characters are found
			// why? To make the output same as that in python!
			if (fullname.search(/[\[\]\\()<>@,:;".]/) !== -1) {
				quote = '"';
			}

			return repl("%(quote)s%(fullname)s%(quote)s <%(email)s>", {
				fullname: fullname,
				email: email,
				quote: quote,
			});
		}
	},

	get_emails: () => {
		return Object.keys(mrinimitable.boot.user_info).map((key) => mrinimitable.boot.user_info[key].email);
	},

	/* Normally mrinimitable.user is an object
	 * having properties and methods.
	 * But in the following case
	 *
	 * if (mrinimitable.user === 'Administrator')
	 *
	 * mrinimitable.user will cast to a string
	 * returning mrinimitable.user.name
	 */
	toString: function () {
		return this.name;
	},
});

mrinimitable.session_alive = true;
$(document).bind("mousemove", function () {
	if (mrinimitable.session_alive === false) {
		$(document).trigger("session_alive");
	}
	mrinimitable.session_alive = true;
	if (mrinimitable.session_alive_timeout) clearTimeout(mrinimitable.session_alive_timeout);
	mrinimitable.session_alive_timeout = setTimeout("mrinimitable.session_alive=false;", 30000);
});
