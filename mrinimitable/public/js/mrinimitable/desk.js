// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
/* eslint-disable no-console */

// __('Modules') __('Domains') __('Places') __('Administration') # for translation, don't remove

mrinimitable.start_app = function () {
	if (!mrinimitable.Application) return;
	mrinimitable.assets.check();
	mrinimitable.provide("mrinimitable.app");
	mrinimitable.provide("mrinimitable.desk");
	mrinimitable.app = new mrinimitable.Application();
};

$(document).ready(function () {
	if (!mrinimitable.utils.supportsES6) {
		mrinimitable.msgprint({
			indicator: "red",
			title: __("Browser not supported"),
			message: __(
				"Some of the features might not work in your browser. Please update your browser to the latest version."
			),
		});
	}
	mrinimitable.start_app();
});

mrinimitable.Application = class Application {
	constructor() {
		this.startup();
	}

	startup() {
		mrinimitable.realtime.init();
		mrinimitable.model.init();

		this.load_bootinfo();
		this.load_user_permissions();
		this.make_nav_bar();
		this.make_sidebar();
		this.set_favicon();
		this.set_fullwidth_if_enabled();
		this.add_browser_class();
		this.setup_copy_doc_listener();
		this.setup_broadcast_listeners();

		mrinimitable.ui.keys.setup();

		this.setup_theme();

		// page container
		this.make_page_container();
		this.setup_tours();
		this.set_route();

		// trigger app startup
		$(document).trigger("startup");
		$(document).trigger("app_ready");

		this.show_notices();
		this.show_notes();

		if (mrinimitable.ui.startup_setup_dialog && !mrinimitable.boot.setup_complete) {
			mrinimitable.ui.startup_setup_dialog.pre_show();
			mrinimitable.ui.startup_setup_dialog.show();
		}

		// listen to build errors
		this.setup_build_events();

		if (mrinimitable.sys_defaults.email_user_password) {
			var email_list = mrinimitable.sys_defaults.email_user_password.split(",");
			for (var u in email_list) {
				if (email_list[u] === mrinimitable.user.name) {
					this.set_password(email_list[u]);
				}
			}
		}

		// REDESIGN-TODO: Fix preview popovers
		this.link_preview = new mrinimitable.ui.LinkPreview();

		mrinimitable.broadcast.emit("boot", {
			csrf_token: mrinimitable.csrf_token,
			user: mrinimitable.session.user,
		});
	}

	make_sidebar() {
		this.sidebar = new mrinimitable.ui.Sidebar({});
	}

	setup_theme() {
		mrinimitable.ui.keys.add_shortcut({
			shortcut: "shift+ctrl+g",
			description: __("Switch Theme"),
			action: () => {
				if (mrinimitable.theme_switcher && mrinimitable.theme_switcher.dialog.is_visible) {
					mrinimitable.theme_switcher.hide();
				} else {
					mrinimitable.theme_switcher = new mrinimitable.ui.ThemeSwitcher();
					mrinimitable.theme_switcher.show();
				}
			},
		});

		mrinimitable.ui.add_system_theme_switch_listener();
		const root = document.documentElement;

		const observer = new MutationObserver(() => {
			mrinimitable.ui.set_theme();
		});
		observer.observe(root, {
			attributes: true,
			attributeFilter: ["data-theme-mode"],
		});

		mrinimitable.ui.set_theme();
	}

	setup_tours() {
		if (
			!window.Cypress &&
			mrinimitable.boot.onboarding_tours &&
			mrinimitable.boot.user.onboarding_status != null
		) {
			let pending_tours = !mrinimitable.boot.onboarding_tours.every(
				(tour) => mrinimitable.boot.user.onboarding_status[tour[0]]?.is_complete
			);
			if (pending_tours && mrinimitable.boot.onboarding_tours.length > 0) {
				mrinimitable.require("onboarding_tours.bundle.js", () => {
					mrinimitable.utils.sleep(1000).then(() => {
						mrinimitable.ui.init_onboarding_tour();
					});
				});
			}
		}
	}

	show_notices() {
		if (mrinimitable.boot.messages) {
			mrinimitable.msgprint(mrinimitable.boot.messages);
		}

		if (mrinimitable.user_roles.includes("System Manager")) {
			// delayed following requests to make boot faster
			setTimeout(() => {
				this.show_change_log();
				this.show_update_available();
			}, 1000);
		}

		if (!mrinimitable.boot.developer_mode) {
			let console_security_message = __(
				"Using this console may allow attackers to impersonate you and steal your information. Do not enter or paste code that you do not understand."
			);
			console.log(`%c${console_security_message}`, "font-size: large");
		}

		mrinimitable.realtime.on("version-update", function () {
			var dialog = mrinimitable.msgprint({
				message: __(
					"The application has been updated to a new version, please refresh this page"
				),
				indicator: "green",
				title: __("Version Updated"),
			});
			dialog.set_primary_action(__("Refresh"), function () {
				location.reload(true);
			});
			dialog.get_close_btn().toggle(false);
		});
	}

	set_route() {
		if (mrinimitable.boot && localStorage.getItem("session_last_route")) {
			mrinimitable.set_route(localStorage.getItem("session_last_route"));
			localStorage.removeItem("session_last_route");
		} else {
			// route to home page
			mrinimitable.router.route();
		}
		mrinimitable.router.on("change", () => {
			$(".tooltip").hide();
			if (mrinimitable.mrinimitable_toolbar && mrinimitable.is_mobile()) mrinimitable.mrinimitable_toolbar.show_app_logo();
		});
	}

	set_password(user) {
		var me = this;
		mrinimitable.call({
			method: "mrinimitable.core.doctype.user.user.get_email_awaiting",
			args: {
				user: user,
			},
			callback: function (email_account) {
				email_account = email_account["message"];
				if (email_account) {
					var i = 0;
					if (i < email_account.length) {
						me.email_password_prompt(email_account, user, i);
					}
				}
			},
		});
	}

	email_password_prompt(email_account, user, i) {
		var me = this;
		const email_id = email_account[i]["email_id"];
		let d = new mrinimitable.ui.Dialog({
			title: __("Password missing in Email Account"),
			fields: [
				{
					fieldname: "password",
					fieldtype: "Password",
					label: __(
						"Please enter the password for: <b>{0}</b>",
						[email_id],
						"Email Account"
					),
					reqd: 1,
				},
				{
					fieldname: "submit",
					fieldtype: "Button",
					label: __("Submit", null, "Submit password for Email Account"),
				},
			],
		});
		d.get_input("submit").on("click", function () {
			//setup spinner
			d.hide();
			var s = new mrinimitable.ui.Dialog({
				title: __("Checking one moment"),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "checking",
					},
				],
			});
			s.fields_dict.checking.$wrapper.html('<i class="fa fa-spinner fa-spin fa-4x"></i>');
			s.show();
			mrinimitable.call({
				method: "mrinimitable.email.doctype.email_account.email_account.set_email_password",
				args: {
					email_account: email_account[i]["email_account"],
					password: d.get_value("password"),
				},
				callback: function (passed) {
					s.hide();
					d.hide(); //hide waiting indication
					if (!passed["message"]) {
						mrinimitable.show_alert(
							{ message: __("Login Failed please try again"), indicator: "error" },
							5
						);
						me.email_password_prompt(email_account, user, i);
					} else {
						if (i + 1 < email_account.length) {
							i = i + 1;
							me.email_password_prompt(email_account, user, i);
						}
					}
				},
			});
		});
		d.show();
	}
	load_bootinfo() {
		if (mrinimitable.boot) {
			this.setup_workspaces();
			mrinimitable.model.sync(mrinimitable.boot.docs);
			this.check_metadata_cache_status();
			this.set_globals();
			this.sync_pages();
			mrinimitable.router.setup();
			this.setup_moment();
			if (mrinimitable.boot.print_css) {
				mrinimitable.dom.set_style(mrinimitable.boot.print_css, "print-style");
			}

			mrinimitable.boot.setup_complete = mrinimitable.boot.sysdefaults["setup_complete"];
			mrinimitable.user.name = mrinimitable.boot.user.name;
			mrinimitable.router.setup();
		} else {
			this.set_as_guest();
		}
	}

	setup_workspaces() {
		mrinimitable.modules = {};
		mrinimitable.workspaces = {};
		mrinimitable.boot.allowed_workspaces = mrinimitable.boot.sidebar_pages.pages;

		for (let page of mrinimitable.boot.allowed_workspaces || []) {
			mrinimitable.modules[page.module] = page;
			mrinimitable.workspaces[mrinimitable.router.slug(page.name)] = page;
		}
	}

	load_user_permissions() {
		mrinimitable.defaults.load_user_permission_from_boot();

		mrinimitable.realtime.on(
			"update_user_permissions",
			mrinimitable.utils.debounce(() => {
				mrinimitable.defaults.update_user_permissions();
			}, 500)
		);
	}

	check_metadata_cache_status() {
		if (mrinimitable.boot.metadata_version != localStorage.metadata_version) {
			mrinimitable.assets.clear_local_storage();
			mrinimitable.assets.init_local_storage();
		}
	}

	set_globals() {
		mrinimitable.session.user = mrinimitable.boot.user.name;
		mrinimitable.session.logged_in_user = mrinimitable.boot.user.name;
		mrinimitable.session.user_email = mrinimitable.boot.user.email;
		mrinimitable.session.user_fullname = mrinimitable.user_info().fullname;

		mrinimitable.user_defaults = mrinimitable.boot.user.defaults;
		mrinimitable.user_roles = mrinimitable.boot.user.roles;
		mrinimitable.sys_defaults = mrinimitable.boot.sysdefaults;

		mrinimitable.ui.py_date_format = mrinimitable.boot.sysdefaults.date_format
			.replace("dd", "%d")
			.replace("mm", "%m")
			.replace("yyyy", "%Y");
		mrinimitable.boot.user.last_selected_values = {};
	}
	sync_pages() {
		// clear cached pages if timestamp is not found
		if (localStorage["page_info"]) {
			mrinimitable.boot.allowed_pages = [];
			var page_info = JSON.parse(localStorage["page_info"]);
			$.each(mrinimitable.boot.page_info, function (name, p) {
				if (!page_info[name] || page_info[name].modified != p.modified) {
					delete localStorage["_page:" + name];
				}
				mrinimitable.boot.allowed_pages.push(name);
			});
		} else {
			mrinimitable.boot.allowed_pages = Object.keys(mrinimitable.boot.page_info);
		}
		localStorage["page_info"] = JSON.stringify(mrinimitable.boot.page_info);
	}
	set_as_guest() {
		mrinimitable.session.user = "Guest";
		mrinimitable.session.user_email = "";
		mrinimitable.session.user_fullname = "Guest";

		mrinimitable.user_defaults = {};
		mrinimitable.user_roles = ["Guest"];
		mrinimitable.sys_defaults = {};
	}
	make_page_container() {
		if ($("#body").length) {
			$(".splash").remove();
			mrinimitable.temp_container = $("<div id='temp-container' style='display: none;'>").appendTo(
				"body"
			);
			mrinimitable.container = new mrinimitable.views.Container();
		}
	}
	make_nav_bar() {
		// toolbar
		if (mrinimitable.boot && mrinimitable.boot.home_page !== "setup-wizard") {
			mrinimitable.mrinimitable_toolbar = new mrinimitable.ui.toolbar.Toolbar();
		}
	}
	logout() {
		var me = this;
		me.logged_out = true;
		return mrinimitable.call({
			method: "logout",
			callback: function (r) {
				if (r.exc) {
					return;
				}

				me.redirect_to_login();
			},
		});
	}
	handle_session_expired() {
		mrinimitable.app.redirect_to_login();
	}
	redirect_to_login() {
		window.location.href = `/login?redirect-to=${encodeURIComponent(
			window.location.pathname + window.location.search
		)}`;
	}
	set_favicon() {
		var link = $('link[type="image/x-icon"]').remove().attr("href");
		$('<link rel="shortcut icon" href="' + link + '" type="image/x-icon">').appendTo("head");
		$('<link rel="icon" href="' + link + '" type="image/x-icon">').appendTo("head");
	}
	trigger_primary_action() {
		// to trigger change event on active input before triggering primary action
		$(document.activeElement).blur();
		// wait for possible JS validations triggered after blur (it might change primary button)
		setTimeout(() => {
			if (window.cur_dialog && cur_dialog.display && !cur_dialog.is_minimized) {
				// trigger primary
				cur_dialog.get_primary_btn().trigger("click");
			} else if (cur_frm && cur_frm.page.btn_primary.is(":visible")) {
				cur_frm.page.btn_primary.trigger("click");
			} else if (mrinimitable.container.page.save_action) {
				mrinimitable.container.page.save_action();
			}
		}, 100);
	}

	show_change_log() {
		var me = this;
		let change_log = mrinimitable.boot.change_log;

		// mrinimitable.boot.change_log = [{
		// 	"change_log": [
		// 		[<version>, <change_log in markdown>],
		// 		[<version>, <change_log in markdown>],
		// 	],
		// 	"description": "ERP made simple",
		// 	"title": "OKAYBlue",
		// 	"version": "12.2.0"
		// }];

		if (
			!Array.isArray(change_log) ||
			!change_log.length ||
			window.Cypress ||
			cint(mrinimitable.boot.sysdefaults.disable_change_log_notification)
		) {
			return;
		}

		// Iterate over changelog
		var change_log_dialog = mrinimitable.msgprint({
			message: mrinimitable.render_template("change_log", { change_log: change_log }),
			title: __("Updated To A New Version 🎉"),
			wide: true,
		});
		change_log_dialog.keep_open = true;
		change_log_dialog.custom_onhide = function () {
			mrinimitable.call({
				method: "mrinimitable.utils.change_log.update_last_known_versions",
			});
			me.show_notes();
		};
	}

	show_update_available() {
		if (!mrinimitable.boot.has_app_updates) return;
		mrinimitable.xcall("mrinimitable.utils.change_log.show_update_popup");
	}

	add_browser_class() {
		$("html").addClass(mrinimitable.utils.get_browser().name.toLowerCase());
	}

	set_fullwidth_if_enabled() {
		mrinimitable.ui.toolbar.set_fullwidth_if_enabled();
	}

	show_notes() {
		var me = this;
		if (mrinimitable.boot.notes.length) {
			mrinimitable.boot.notes.forEach(function (note) {
				if (!note.seen || note.notify_on_every_login) {
					var d = new mrinimitable.ui.Dialog({ content: note.content, title: note.title });
					d.keep_open = true;
					d.msg_area = $('<div class="msgprint">').appendTo(d.body);
					d.msg_area.append(note.content);
					d.onhide = function () {
						note.seen = true;
						// Mark note as read if the Notify On Every Login flag is not set
						if (!note.notify_on_every_login) {
							mrinimitable.call({
								method: "mrinimitable.desk.doctype.note.note.mark_as_seen",
								args: {
									note: note.name,
								},
							});
						} else {
							mrinimitable.call({
								method: "mrinimitable.desk.doctype.note.note.reset_notes",
							});
						}
					};
					d.show();
				}
			});
		}
	}

	setup_build_events() {
		if (mrinimitable.boot.developer_mode) {
			mrinimitable.require("build_events.bundle.js");
		}
	}

	setup_copy_doc_listener() {
		$("body").on("paste", (e) => {
			try {
				let pasted_data = mrinimitable.utils.get_clipboard_data(e);
				let doc = JSON.parse(pasted_data);
				if (doc.doctype) {
					e.preventDefault();
					const sleep = mrinimitable.utils.sleep;

					mrinimitable.dom.freeze(__("Creating {0}", [doc.doctype]) + "...");
					// to avoid abrupt UX
					// wait for activity feedback
					sleep(500).then(() => {
						let res = mrinimitable.model.with_doctype(doc.doctype, () => {
							let newdoc = mrinimitable.model.copy_doc(doc);
							newdoc.__newname = doc.name;
							delete doc.name;
							newdoc.idx = null;
							newdoc.__run_link_triggers = false;
							newdoc.on_paste_event = true;
							newdoc = JSON.parse(JSON.stringify(newdoc));
							mrinimitable.set_route("Form", newdoc.doctype, newdoc.name);
							mrinimitable.dom.unfreeze();
						});
						res && res.fail?.(mrinimitable.dom.unfreeze);
					});
				}
			} catch (e) {
				//
			}
		});
	}

	/// Setup event listeners for events across browser tabs / web workers.
	setup_broadcast_listeners() {
		// booted in another tab -> refresh csrf to avoid invalid requests.
		mrinimitable.broadcast.on("boot", ({ csrf_token, user }) => {
			if (user && user != mrinimitable.session.user) {
				mrinimitable.msgprint({
					message: __(
						"You've logged in as another user from another tab. Refresh this page to continue using system."
					),
					title: __("User Changed"),
					primary_action: {
						label: __("Refresh"),
						action: () => {
							window.location.reload();
						},
					},
				});
				return;
			}

			if (csrf_token) {
				// If user re-logged in then their other tabs won't be usable without this update.
				mrinimitable.csrf_token = csrf_token;
			}
		});
	}

	setup_moment() {
		moment.updateLocale("en", {
			week: {
				dow: mrinimitable.datetime.get_first_day_of_the_week_index(),
			},
		});
		moment.locale("en");
		moment.user_utc_offset = moment().utcOffset();
		if (mrinimitable.boot.timezone_info) {
			moment.tz.add(mrinimitable.boot.timezone_info);
		}
	}
};

mrinimitable.get_module = function (m, default_module) {
	var module = mrinimitable.modules[m] || default_module;
	if (!module) {
		return;
	}

	if (module._setup) {
		return module;
	}

	if (!module.label) {
		module.label = m;
	}

	if (!module._label) {
		module._label = __(module.label);
	}

	module._setup = true;

	return module;
};
