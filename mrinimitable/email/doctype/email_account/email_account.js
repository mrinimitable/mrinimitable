mrinimitable.email_defaults = {
	"Mrinimitable Mail": {
		domain: null,
		password: null,
		awaiting_password: 0,
		ascii_encode_password: 0,
		login_id_is_different: 0,
		login_id: null,
		use_imap: 0,
		use_ssl: 0,
		validate_ssl_certificate: 0,
		use_starttls: 0,
		email_server: null,
		incoming_port: 0,
		always_use_account_email_id_as_sender: 1,
		use_tls: 0,
		use_ssl_for_outgoing: 0,
		smtp_server: null,
		smtp_port: null,
		no_smtp_authentication: 0,
	},
	GMail: {
		email_server: "imap.gmail.com",
		incoming_port: 993,
		use_ssl: 1,
		enable_outgoing: 1,
		smtp_server: "smtp.gmail.com",
		smtp_port: 587,
		use_tls: 1,
		use_imap: 1,
	},
	"Outlook.com": {
		email_server: "imap-mail.outlook.com",
		use_ssl: 1,
		enable_outgoing: 1,
		smtp_server: "smtp-mail.outlook.com",
		smtp_port: 587,
		use_tls: 1,
		use_imap: 1,
	},
	Sendgrid: {
		enable_outgoing: 1,
		smtp_server: "smtp.sendgrid.net",
		smtp_port: 587,
		use_tls: 1,
	},
	SparkPost: {
		enable_incoming: 0,
		enable_outgoing: 1,
		smtp_server: "smtp.sparkpostmail.com",
		smtp_port: 587,
		use_tls: 1,
	},
	"Yahoo Mail": {
		email_server: "imap.mail.yahoo.com",
		use_ssl: 1,
		enable_outgoing: 1,
		smtp_server: "smtp.mail.yahoo.com",
		smtp_port: 587,
		use_tls: 1,
		use_imap: 1,
	},
	"Yandex.Mail": {
		email_server: "imap.yandex.com",
		use_ssl: 1,
		enable_outgoing: 1,
		smtp_server: "smtp.yandex.com",
		smtp_port: 587,
		use_tls: 1,
		use_imap: 1,
	},
};

mrinimitable.email_defaults_pop = {
	GMail: {
		email_server: "pop.gmail.com",
	},
	"Outlook.com": {
		email_server: "pop3-mail.outlook.com",
	},
	"Yahoo Mail": {
		email_server: "pop.mail.yahoo.com",
	},
	"Yandex.Mail": {
		email_server: "pop.yandex.com",
	},
};

function oauth_access(frm) {
	mrinimitable.model.with_doc("Connected App", frm.doc.connected_app, () => {
		const connected_app = mrinimitable.get_doc("Connected App", frm.doc.connected_app);
		return mrinimitable.call({
			doc: connected_app,
			method: "initiate_web_application_flow",
			args: {
				success_uri: window.location.pathname,
				user: frm.doc.connected_user,
			},
			callback: function (r) {
				window.open(r.message, "_self");
			},
		});
	});
}

function set_default_max_attachment_size(frm) {
	if (frm.doc.__islocal && !frm.doc["attachment_limit"]) {
		mrinimitable.call({
			method: "mrinimitable.core.api.file.get_max_file_size",
			callback: function (r) {
				if (!r.exc) {
					frm.set_value("attachment_limit", Number(r.message) / (1024 * 1024));
				}
			},
		});
	}
}
function add_helpful_links(frm) {
	// For better UX
	if (frm.doc.service === "GMail") {
		frm.set_df_property(
			"password",
			"description",
			__("To generate password click {0}", [
				"<a href='https://knowledge.workspace.google.com/kb/how-to-create-app-passwords-000009237' target='_blank'>" +
					__("here") +
					"</a>",
			])
		);
	} else {
		frm.set_df_property("password", "description", "");
	}

	if (frm.doc.service === "Mrinimitable Mail") {
		frm.set_df_property(
			"api_secret",
			"description",
			__("To know more click {0}", [
				"<a href='https://github.com/mrinimitable/mail' target='_blank'>" + __("here") + "</a>",
			])
		);
	} else {
		frm.set_df_property("api_secret", "description", "");
	}
}

mrinimitable.ui.form.on("Email Account", {
	service: function (frm) {
		$.each(mrinimitable.email_defaults[frm.doc.service], function (key, value) {
			frm.set_value(key, value);
		});
		if (!frm.doc.use_imap) {
			$.each(mrinimitable.email_defaults_pop[frm.doc.service], function (key, value) {
				frm.set_value(key, value);
			});
		}
		add_helpful_links(frm);
	},

	use_imap: function (frm) {
		if (!frm.doc.use_imap) {
			$.each(mrinimitable.email_defaults_pop[frm.doc.service], function (key, value) {
				frm.set_value(key, value);
			});
		} else {
			$.each(mrinimitable.email_defaults[frm.doc.service], function (key, value) {
				frm.set_value(key, value);
			});
		}
	},

	enable_incoming: function (frm) {
		frm.trigger("warn_autoreply_on_incoming");
	},

	enable_auto_reply: function (frm) {
		frm.trigger("warn_autoreply_on_incoming");
	},

	onload: function (frm) {
		frm.set_df_property("append_to", "only_select", true);
		frm.set_query(
			"append_to",
			"mrinimitable.email.doctype.email_account.email_account.get_append_to"
		);
		frm.set_query("append_to", "imap_folder", function () {
			return {
				query: "mrinimitable.email.doctype.email_account.email_account.get_append_to",
			};
		});
		if (frm.doc.__islocal) {
			frm.add_child("imap_folder", { folder_name: "INBOX" });
			frm.refresh_field("imap_folder");
		}
		set_default_max_attachment_size(frm);
	},

	refresh: function (frm) {
		frm.events.enable_incoming(frm);
		frm.events.show_oauth_authorization_message(frm);

		if (mrinimitable.route_flags.delete_user_from_locals && mrinimitable.route_flags.linked_user) {
			delete mrinimitable.route_flags.delete_user_from_locals;
			delete locals["User"][mrinimitable.route_flags.linked_user];
		}

		if (!frm.is_dirty() && frm.doc.enable_incoming) {
			frm.add_custom_button(__("Pull Emails"), () => {
				mrinimitable.dom.freeze(__("Pulling emails..."));
				frm.call({
					method: "pull_emails",
					args: { email_account: frm.doc.name },
				}).then((r) => {
					mrinimitable.dom.unfreeze();
					if (!(r._server_messages && r._server_messages.length)) {
						mrinimitable.show_alert({ message: __("Emails Pulled"), indicator: "green" });
					}
				});
			});
		}
	},

	authorize_api_access: function (frm) {
		oauth_access(frm);
	},

	validate_mrinimitable_mail_settings: function (frm) {
		if (frm.doc.service == "Mrinimitable Mail") {
			mrinimitable.call({
				doc: frm.doc,
				method: "validate_mrinimitable_mail_settings",
			});
		}
	},

	show_oauth_authorization_message(frm) {
		if (
			frm.doc.auth_method === "OAuth" &&
			frm.doc.connected_app &&
			!frm.doc.backend_app_flow
		) {
			mrinimitable.call({
				method: "mrinimitable.integrations.doctype.connected_app.connected_app.has_token",
				args: {
					connected_app: frm.doc.connected_app,
					connected_user: frm.doc.connected_user,
				},
				callback: (r) => {
					if (!r.message) {
						let msg = __(
							'OAuth has been enabled but not authorised. Please use "Authorise API Access" button to do the same.'
						);
						frm.dashboard.clear_headline();
						frm.dashboard.set_headline_alert(msg, "yellow");
					}
				},
			});
		}
	},

	domain: mrinimitable.utils.debounce((frm) => {
		if (frm.doc.domain) {
			mrinimitable.call({
				method: "get_domain_values",
				doc: frm.doc,
				args: {
					domain: frm.doc.domain,
				},
				callback: function (r) {
					if (!r.exc) {
						for (let field in r.message) {
							frm.set_value(field, r.message[field]);
						}
					}
				},
			});
		}
	}),

	email_sync_option: function (frm) {
		// confirm if the ALL sync option is selected

		if (frm.doc.email_sync_option == "ALL") {
			var msg = __(
				"You are selecting Sync Option as ALL, It will resync all read as well as unread message from server. This may also cause the duplication of Communication (emails)."
			);
			mrinimitable.confirm(msg, null, function () {
				frm.set_value("email_sync_option", "UNSEEN");
			});
		}
	},

	warn_autoreply_on_incoming: function (frm) {
		if (frm.doc.enable_incoming && frm.doc.enable_auto_reply && frm.doc.__islocal) {
			var msg = __(
				"Enabling auto reply on an incoming email account will send automated replies to all the synchronized emails. Do you wish to continue?"
			);
			mrinimitable.confirm(msg, null, function () {
				frm.set_value("enable_auto_reply", 0);
				mrinimitable.show_alert({ message: __("Disabled Auto Reply"), indicator: "blue" });
			});
		}
	},
});
