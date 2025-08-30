mrinimitable.provide("mrinimitable.setup");
mrinimitable.provide("mrinimitable.setup.events");
mrinimitable.provide("mrinimitable.ui");

mrinimitable.setup = {
	slides: [],
	events: {},
	data: {},
	utils: {},
	domains: [],

	on: function (event, fn) {
		if (!mrinimitable.setup.events[event]) {
			mrinimitable.setup.events[event] = [];
		}
		mrinimitable.setup.events[event].push(fn);
	},
	add_slide: function (slide) {
		mrinimitable.setup.slides.push(slide);
	},

	remove_slide: function (slide_name) {
		mrinimitable.setup.slides = mrinimitable.setup.slides.filter((slide) => slide.name !== slide_name);
	},

	run_event: function (event) {
		$.each(mrinimitable.setup.events[event] || [], function (i, fn) {
			fn();
		});
	},
};

mrinimitable.pages["setup-wizard"].on_page_load = function (wrapper) {
	if (mrinimitable.boot.setup_complete) {
		window.location.href = mrinimitable.boot.apps_data.default_path || "/app";
	}
	let requires = mrinimitable.boot.setup_wizard_requires || [];
	mrinimitable.require(requires, function () {
		mrinimitable.call({
			method: "mrinimitable.desk.page.setup_wizard.setup_wizard.load_languages",
			freeze: true,
			callback: function (r) {
				mrinimitable.setup.data.lang = r.message;

				mrinimitable.setup.run_event("before_load");
				var wizard_settings = {
					parent: wrapper,
					slides: mrinimitable.setup.slides,
					slide_class: mrinimitable.setup.SetupWizardSlide,
					unidirectional: 1,
					done_state: 1,
				};
				mrinimitable.wizard = new mrinimitable.setup.SetupWizard(wizard_settings);
				mrinimitable.setup.run_event("after_load");
				mrinimitable.wizard.show_slide(cint(mrinimitable.get_route()[1]));
			},
		});
	});
};

mrinimitable.pages["setup-wizard"].on_page_show = function () {
	mrinimitable.wizard && mrinimitable.wizard.show_slide(cint(mrinimitable.get_route()[1]));
};

mrinimitable.setup.on("before_load", function () {
	if (
		mrinimitable.boot.setup_wizard_completed_apps?.length &&
		mrinimitable.boot.setup_wizard_completed_apps.includes("mrinimitable")
	) {
		return;
	}

	// load slides
	mrinimitable.setup.slides_settings.forEach((s) => {
		if (!(s.name === "user" && mrinimitable.boot.developer_mode)) {
			// if not user slide with developer mode
			mrinimitable.setup.add_slide(s);
		}
	});
});

mrinimitable.setup.SetupWizard = class SetupWizard extends mrinimitable.ui.Slides {
	constructor(args = {}) {
		super(args);
		$.extend(this, args);

		this.page_name = "setup-wizard";
		this.welcomed = true;
		mrinimitable.set_route("setup-wizard/0");
	}

	make() {
		super.make();
		this.container.addClass("container setup-wizard-slide with-form");
		this.$next_btn.addClass("action");
		this.$complete_btn.addClass("action");
		this.setup_keyboard_nav();
	}

	setup_keyboard_nav() {
		$("body").on("keydown", this.handle_enter_press.bind(this));
	}

	disable_keyboard_nav() {
		$("body").off("keydown", this.handle_enter_press.bind(this));
	}

	handle_enter_press(e) {
		if (e.which === mrinimitable.ui.keyCode.ENTER) {
			let $target = $(e.target);
			if ($target.hasClass("prev-btn") || $target.hasClass("next-btn")) {
				$target.trigger("click");
			} else {
				// hitting enter on autocomplete field shouldn't trigger next slide.
				if ($target.data().fieldtype == "Autocomplete") return;

				this.container.find(".next-btn").trigger("click");
				e.preventDefault();
			}
		}
	}

	before_show_slide() {
		if (!this.welcomed) {
			mrinimitable.set_route(this.page_name);
			return false;
		}
		return true;
	}

	show_slide(id) {
		if (id === this.slides.length) {
			return;
		}
		super.show_slide(id);
		mrinimitable.set_route(this.page_name, cstr(id));
	}

	show_hide_prev_next(id) {
		super.show_hide_prev_next(id);
		if (id + 1 === this.slides.length) {
			this.$next_btn.removeClass("btn-primary").hide();
			this.$complete_btn
				.addClass("btn-primary")
				.show()
				.on("click", () => this.action_on_complete());
		} else {
			this.$next_btn.addClass("btn-primary").show();
			this.$complete_btn.removeClass("btn-primary").hide();
		}
	}

	refresh_slides() {
		// For Translations, etc.
		if (this.in_refresh_slides || !this.current_slide.set_values(true)) {
			return;
		}
		this.in_refresh_slides = true;

		this.update_values();
		mrinimitable.setup.slides = [];
		mrinimitable.setup.run_event("before_load");

		mrinimitable.setup.slides = this.get_setup_slides_filtered_by_domain();

		this.slides = mrinimitable.setup.slides;
		mrinimitable.setup.run_event("after_load");

		// re-render all slide, only remake made slides
		$.each(this.slide_dict, (id, slide) => {
			if (slide.made) {
				this.made_slide_ids.push(id);
			}
		});
		this.made_slide_ids.push(this.current_id);
		this.setup();

		this.show_slide(this.current_id);
		this.refresh(this.current_id);
		setTimeout(() => {
			this.container.find(".form-control").first().focus();
		}, 200);
		this.in_refresh_slides = false;
	}

	action_on_complete() {
		mrinimitable.telemetry.capture("initated_client_side", "setup");
		if (!this.current_slide.set_values()) return;
		this.update_values();
		this.show_working_state();
		this.disable_keyboard_nav();
		this.listen_for_setup_stages();

		return mrinimitable.call({
			method: "mrinimitable.desk.page.setup_wizard.setup_wizard.setup_complete",
			args: { args: this.values },
			callback: (r) => {
				if (r.message.status === "ok") {
					this.post_setup_success();
				} else if (r.message.status === "registered") {
					this.update_setup_message(__("starting the setup..."));
				} else if (r.message.fail !== undefined) {
					this.abort_setup(r.message.fail);
				}
			},
			error: () => this.abort_setup(),
		});
	}

	post_setup_success() {
		this.set_setup_complete_message(__("Setup Complete"), __("Refreshing..."));
		if (mrinimitable.setup.welcome_page) {
			localStorage.setItem("session_last_route", mrinimitable.setup.welcome_page);
		}
		setTimeout(function () {
			// Reload
			let current_route = localStorage.current_route;

			localStorage.current_route = "";
			localStorage.current_app = "";

			window.location.href = current_route || mrinimitable.boot.apps_data.default_path || "/app";
		}, 2000);
	}

	abort_setup(fail_msg) {
		this.$working_state.find(".state-icon-container").html("");
		fail_msg = fail_msg
			? fail_msg
			: mrinimitable.last_response.setup_wizard_failure_message
			? mrinimitable.last_response.setup_wizard_failure_message
			: __("Failed to complete setup");

		this.update_setup_message(__("Could not start up:") + " " + fail_msg);

		this.$working_state.find(".title").html(__("Setup failed"));

		this.$abort_btn.show();
	}

	listen_for_setup_stages() {
		mrinimitable.realtime.on("setup_task", (data) => {
			// console.log('data', data);
			if (data.stage_status) {
				// .html('Process '+ data.progress[0] + ' of ' + data.progress[1] + ': ' + data.stage_status);
				this.update_setup_message(data.stage_status);
				this.set_setup_load_percent(((data.progress[0] + 1) / data.progress[1]) * 100);
			}
			if (data.fail_msg) {
				this.abort_setup(data.fail_msg);
			}
			if (data.status === "ok") {
				this.post_setup_success();
			}
		});
	}

	update_setup_message(message) {
		this.$working_state.find(".setup-message").html(message);
	}

	get_setup_slides_filtered_by_domain() {
		let filtered_slides = [];
		mrinimitable.setup.slides.forEach(function (slide) {
			if (mrinimitable.setup.domains) {
				let active_domains = mrinimitable.setup.domains;
				if (
					!slide.domains ||
					slide.domains.filter((d) => active_domains.includes(d)).length > 0
				) {
					filtered_slides.push(slide);
				}
			} else {
				filtered_slides.push(slide);
			}
		});
		return filtered_slides;
	}

	show_working_state() {
		this.container.hide();
		mrinimitable.set_route(this.page_name);

		this.$working_state = this.get_message(
			__("Setting up your system"),
			__("Starting Mrinimitable ...")
		).appendTo(this.parent);

		this.attach_abort_button();

		this.current_id = this.slides.length;
		this.current_slide = null;
	}

	attach_abort_button() {
		this.$abort_btn = $(
			`<button class='btn btn-secondary btn-xs btn-abort text-muted'>${__("Retry")}</button>`
		);
		this.$working_state.find(".content").append(this.$abort_btn);

		this.$abort_btn.on("click", () => {
			$(this.parent).find(".setup-in-progress").remove();
			this.container.show();
			mrinimitable.set_route(this.page_name, this.slides.length - 1);
		});

		this.$abort_btn.hide();
	}

	get_message(title, message = "") {
		const loading_html = `<div class="progress-chart">
			<div class="progress">
				<div class="progress-bar"></div>
			</div>
		</div>`;

		return $(`<div class="slides-wrapper container setup-wizard-slide setup-in-progress">
			<div class="content text-center">
				<h1 class="slide-title title">${title}</h1>
				<div class="state-icon-container">${loading_html}</div>
				<p class="setup-message text-muted">${message}</p>
			</div>
		</div>`);
	}

	set_setup_complete_message(title, message) {
		this.$working_state.find(".title").html(title);
		this.$working_state.find(".setup-message").html(message);
	}

	set_setup_load_percent(percent) {
		this.$working_state.find(".progress-bar").css({ width: percent + "%" });
	}
};

mrinimitable.setup.SetupWizardSlide = class SetupWizardSlide extends mrinimitable.ui.Slide {
	constructor(slide = null) {
		super(slide);
	}

	make() {
		super.make();
		this.set_init_values();
		this.setup_telemetry_events();
		this.reset_action_button_state();
	}

	set_init_values() {
		let me = this;
		// set values from mrinimitable.setup.values
		if (mrinimitable.wizard.values && this.fields) {
			this.fields.forEach(function (f) {
				var value = mrinimitable.wizard.values[f.fieldname];
				if (value) {
					me.get_field(f.fieldname).set_input(value);
				}
			});
		}
	}

	setup_telemetry_events() {
		let me = this;
		this.fields.filter(mrinimitable.model.is_value_type).forEach((field) => {
			field.fieldname &&
				me.get_input(field.fieldname)?.on?.("change", function () {
					mrinimitable.telemetry.capture(`${field.fieldname}_set`, "setup");
					if (
						field.fieldname == "enable_telemetry" &&
						!me.get_value("enable_telemetry")
					) {
						mrinimitable.telemetry.disable();
					}
				});
		});
	}
};

// Mrinimitable slides settings
// ======================================================
mrinimitable.setup.slides_settings = [
	{
		// Welcome (language) slide
		name: "welcome",
		title: __("Welcome"),

		fields: [
			{
				fieldname: "language",
				label: __("Your Language"),
				fieldtype: "Autocomplete",
				placeholder: __("Select Language"),
				default: "English",
				reqd: 1,
			},
			{
				fieldname: "country",
				label: __("Your Country"),
				fieldtype: "Autocomplete",
				placeholder: __("Select Country"),
				reqd: 1,
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "timezone",
				label: __("Time Zone"),
				placeholder: __("Select Time Zone"),
				fieldtype: "Select",
				reqd: 1,
			},
			{
				fieldname: "currency",
				label: __("Currency"),
				placeholder: __("Select Currency"),
				fieldtype: "Select",
				reqd: 1,
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "enable_telemetry",
				label: __("Allow sending usage data for improving applications"),
				fieldtype: "Check",
				default: cint(mrinimitable.telemetry.can_enable()),
				depends_on: "eval:mrinimitable.telemetry.can_enable()",
			},
			{
				fieldname: "allow_recording_first_session",
				label: __("Allow recording my first session to improve user experience"),
				fieldtype: "Check",
				default: 0,
				depends_on: "eval:mrinimitable.telemetry.can_enable()",
			},
		],

		onload: function (slide) {
			mrinimitable.setup.utils.load_prefilled_data(slide, this.initialize_fields);
		},

		initialize_fields: function (slide) {
			const setup_fields = function (slide) {
				mrinimitable.setup.utils.setup_region_fields(slide);
				mrinimitable.setup.utils.setup_language_field(slide);
			};

			if (mrinimitable.setup.data.regional_data) {
				setup_fields(slide);
			} else {
				mrinimitable.setup.utils.load_regional_data(slide, setup_fields);
			}
			if (!slide.get_value("language")) {
				let session_language =
					mrinimitable.setup.utils.get_language_name_from_code(
						mrinimitable.boot.lang || navigator.language
					) || "English";
				let language_field = slide.get_field("language");

				language_field.set_input(session_language);
				if (!mrinimitable.setup._from_load_messages) {
					language_field.$input.trigger("change");
				}
				delete mrinimitable.setup._from_load_messages;
				moment.locale("en");
			}
			mrinimitable.setup.utils.bind_region_events(slide);
			mrinimitable.setup.utils.bind_language_events(slide);
		},
	},
	{
		// Profile slide
		name: "user",
		title: __("Let's set up your account"),
		icon: "fa fa-user",
		fields: [
			{
				fieldname: "full_name",
				label: __("Full Name"),
				fieldtype: "Data",
				reqd: 1,
			},
			{
				fieldname: "email",
				label: __("Email Address") + " (" + __("Will be your login ID") + ")",
				fieldtype: "Data",
				options: "Email",
			},
			{
				fieldname: "password",
				label:
					mrinimitable.session.user === "Administrator"
						? __("Password")
						: __("Update Password"),
				fieldtype: "Password",
				length: 512,
				depends_on: "eval:!mrinimitable.boot.is_fc_site",
			},
		],

		onload: function (slide) {
			if (mrinimitable.session.user !== "Administrator") {
				const { first_name, last_name, email } = mrinimitable.boot.user;
				if (first_name || last_name) {
					slide.form.fields_dict.full_name.set_input(
						[first_name, last_name].join(" ").trim()
					);
				}
				slide.form.fields_dict.email.set_input(email);
				slide.form.fields_dict.email.df.read_only = 1;
				slide.form.fields_dict.email.refresh();
			} else {
				slide.form.fields_dict.email.df.reqd = 1;
				slide.form.fields_dict.email.refresh();
				if (!mrinimitable.boot.is_fc_site) slide.form.fields_dict.password.df.reqd = 1;
				slide.form.fields_dict.password.refresh();

				mrinimitable.setup.utils.load_user_details(slide, this.setup_fields);
			}
		},

		setup_fields: function (slide) {
			if (mrinimitable.setup.data.full_name) {
				slide.form.fields_dict.full_name.set_input(mrinimitable.setup.data.full_name);
			}
			if (mrinimitable.setup.data.email) {
				let email = mrinimitable.setup.data.email;
				slide.form.fields_dict.email.set_input(email);
			}
		},
	},
];

mrinimitable.setup.utils = {
	load_prefilled_data: function (slide, callback) {
		mrinimitable.db
			.get_value("System Settings", "System Settings", [
				"country",
				"timezone",
				"currency",
				"language",
			])
			.then((r) => {
				if (r.message) {
					mrinimitable.wizard.values.currency = r.message.currency;
					mrinimitable.wizard.values.country = r.message.country;
					mrinimitable.wizard.values.timezone = r.message.time_zone;
					mrinimitable.wizard.values.language = r.message.language;

					mrinimitable.db.get_value(
						"User",
						{ name: ["not in", ["Administrator", "Guest"]] },
						["full_name", "email"],
						(r) => {
							if (r) {
								mrinimitable.wizard.values.full_name = r.full_name;
								mrinimitable.wizard.values.email = r.email;
							}
						}
					);
				}
				callback(slide);
			});
	},

	load_regional_data: function (slide, callback) {
		mrinimitable.call({
			method: "mrinimitable.geo.country_info.get_country_timezone_info",
			callback: function (data) {
				mrinimitable.setup.data.regional_data = data.message;
				callback(slide);
			},
		});
	},

	load_user_details: function (slide, callback) {
		mrinimitable.call({
			method: "mrinimitable.desk.page.setup_wizard.setup_wizard.load_user_details",
			freeze: true,
			callback: function (r) {
				mrinimitable.setup.data.full_name = r.message.full_name;
				mrinimitable.setup.data.email = r.message.email;
				callback(slide);
			},
		});
	},

	setup_language_field: function (slide) {
		var language_field = slide.get_field("language");
		language_field.df.options = mrinimitable.setup.data.lang.languages;
		language_field.set_options();
	},

	setup_region_fields: function (slide) {
		/*
			Set a slide's country, timezone and currency fields
		*/
		let data = mrinimitable.setup.data.regional_data;
		let country_field = slide.get_field("country");
		let translated_countries = [];

		Object.keys(data.country_info)
			.sort()
			.forEach((country) => {
				translated_countries.push({
					label: __(country),
					value: country,
				});
			});

		country_field.set_data(translated_countries);

		slide
			.get_input("currency")
			.empty()
			.add_options(
				mrinimitable.utils.unique($.map(data.country_info, (opts) => opts.currency).sort())
			);

		slide.get_input("timezone").empty().add_options(data.all_timezones);

		slide.get_field("currency").set_input(mrinimitable.wizard.values.currency);
		slide.get_field("timezone").set_input(mrinimitable.wizard.values.timezone);

		// set values if present
		let country =
			mrinimitable.wizard.values.country ||
			data.default_country ||
			guess_country(mrinimitable.setup.data.regional_data.country_info);

		if (country) {
			country_field.set_input(country);
			$(country_field.input).change();
		}
	},

	bind_language_events: function (slide) {
		slide
			.get_input("language")
			.unbind("change")
			.on("change", function () {
				const selected_language = $(this).val();
				if (slide.get_field("language").value === selected_language) return;

				clearTimeout(slide.language_call_timeout);
				slide.language_call_timeout = setTimeout(() => {
					let lang = selected_language || "English";
					mrinimitable._messages = {};
					mrinimitable.call({
						method: "mrinimitable.desk.page.setup_wizard.setup_wizard.load_messages",
						freeze: true,
						args: {
							language: lang,
						},
						callback: function () {
							mrinimitable.setup._from_load_messages = true;
							mrinimitable.wizard.refresh_slides();
						},
					});
				}, 500);
			});
	},

	get_language_name_from_code: function (language_code) {
		return mrinimitable.setup.data.lang.codes_to_names[language_code] || "English";
	},

	bind_region_events: function (slide) {
		/*
			Bind a slide's country, timezone and currency fields
		*/
		slide.get_input("country").on("change", function () {
			let data = mrinimitable.setup.data.regional_data;
			let country = slide.get_input("country").val();
			if (!(country in data.country_info)) return;

			let $timezone = slide.get_input("timezone");

			$timezone.empty();

			if (!country) return;
			// add country specific timezones first
			const timezone_list = data.country_info[country].timezones || [];
			$timezone.add_options(timezone_list.sort());
			slide.get_field("currency").set_input(data.country_info[country].currency);
			slide.get_field("currency").$input.trigger("change");

			// add all timezones at the end, so that user has the option to change it to any timezone
			$timezone.add_options(data.all_timezones);
			slide.get_field("timezone").set_input($timezone.val());

			// temporarily set date format
			mrinimitable.boot.sysdefaults.date_format =
				data.country_info[country].date_format || "dd-mm-yyyy";
		});

		slide.get_input("currency").on("change", function () {
			let currency = slide.get_input("currency").val();
			if (!currency) return;
			mrinimitable.model.with_doc("Currency", currency, function () {
				mrinimitable.provide("locals.:Currency." + currency);
				let currency_doc = mrinimitable.model.get_doc("Currency", currency);
				let number_format = currency_doc.number_format;
				if (number_format === "#.###") {
					number_format = "#.###,##";
				} else if (number_format === "#,###") {
					number_format = "#,###.##";
				}

				mrinimitable.boot.sysdefaults.number_format = number_format;
				locals[":Currency"][currency] = $.extend({}, currency_doc);
			});
		});
	},
};

// https://github.com/eggert/tz/blob/main/backward add more if required.
const TZ_BACKWARD_COMPATBILITY_MAP = {
	"Asia/Calcutta": "Asia/Kolkata",
};

function guess_country(country_info) {
	try {
		let system_timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
		system_timezone = TZ_BACKWARD_COMPATBILITY_MAP[system_timezone] || system_timezone;

		for (let [country, info] of Object.entries(country_info)) {
			let possible_timezones = (info.timezones || []).filter((t) => t == system_timezone);
			if (possible_timezones.length) return country;
		}
	} catch (e) {
		console.log("Could not guess country", e);
	}
}
