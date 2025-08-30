// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.provide("mrinimitable.datetime");

mrinimitable.defaultDateFormat = "YYYY-MM-DD";
mrinimitable.defaultTimeFormat = "HH:mm:ss";
mrinimitable.defaultDatetimeFormat = mrinimitable.defaultDateFormat + " " + mrinimitable.defaultTimeFormat;
moment.defaultFormat = mrinimitable.defaultDateFormat;

mrinimitable.provide("mrinimitable.datetime");

$.extend(mrinimitable.datetime, {
	convert_to_user_tz: function (date, format) {
		// format defaults to true
		// Converts the datetime string to system time zone first since the database only stores datetime in
		// system time zone and then convert the string to user time zone(from User doctype).
		let date_obj = null;
		if (mrinimitable.boot.time_zone && mrinimitable.boot.time_zone.system && mrinimitable.boot.time_zone.user) {
			date_obj = moment
				.tz(date, mrinimitable.boot.time_zone.system)
				.clone()
				.tz(mrinimitable.boot.time_zone.user);
		} else {
			date_obj = moment(date);
		}

		return format === false ? date_obj : date_obj.format(mrinimitable.defaultDatetimeFormat);
	},

	convert_to_system_tz: function (date, format) {
		// format defaults to true
		// Converts the datetime string to user time zone (from User doctype) first since this fn is called in datetime which accepts datetime
		// in user time zone then convert the string to user time zone.
		// This is done so that only one timezone is present in database and we do not end up storing local timezone since it changes
		// as per the location of user.
		let date_obj = null;
		if (mrinimitable.boot.time_zone && mrinimitable.boot.time_zone.system && mrinimitable.boot.time_zone.user) {
			date_obj = moment
				.tz(date, mrinimitable.boot.time_zone.user)
				.clone()
				.tz(mrinimitable.boot.time_zone.system);
		} else {
			date_obj = moment(date);
		}

		return format === false ? date_obj : date_obj.format(mrinimitable.defaultDatetimeFormat);
	},

	is_system_time_zone: function () {
		if (mrinimitable.boot.time_zone && mrinimitable.boot.time_zone.system && mrinimitable.boot.time_zone.user) {
			return (
				moment().tz(mrinimitable.boot.time_zone.system).utcOffset() ===
				moment().tz(mrinimitable.boot.time_zone.user).utcOffset()
			);
		}

		return true;
	},

	is_timezone_same: function () {
		return mrinimitable.datetime.is_system_time_zone();
	},

	str_to_obj: function (d) {
		return moment(d, mrinimitable.defaultDatetimeFormat)._d;
	},

	obj_to_str: function (d) {
		return moment(d).locale("en").format();
	},

	obj_to_user: function (d) {
		return moment(d).format(mrinimitable.datetime.get_user_date_fmt().toUpperCase());
	},

	get_diff: function (d1, d2) {
		return moment(d1).diff(d2, "days");
	},

	get_hour_diff: function (d1, d2) {
		return moment(d1).diff(d2, "hours");
	},

	get_minute_diff: function (d1, d2) {
		return moment(d1).diff(d2, "minutes");
	},

	get_day_diff: function (d1, d2) {
		return moment(d1).diff(d2, "days");
	},

	add_days: function (d, days) {
		return moment(d).add(days, "days").format();
	},

	add_months: function (d, months) {
		return moment(d).add(months, "months").format();
	},

	week_start: function () {
		return moment().startOf("week").format();
	},

	week_end: function () {
		return moment().endOf("week").format();
	},

	month_start: function () {
		return moment().startOf("month").format();
	},

	month_end: function () {
		return moment().endOf("month").format();
	},

	quarter_start: function () {
		return moment().startOf("quarter").format();
	},

	quarter_end: function () {
		return moment().endOf("quarter").format();
	},

	year_start: function () {
		return moment().startOf("year").format();
	},

	year_end: function () {
		return moment().endOf("year").format();
	},

	get_user_time_fmt: function () {
		return (mrinimitable.sys_defaults && mrinimitable.sys_defaults.time_format) || "HH:mm:ss";
	},

	get_user_date_fmt: function () {
		return (mrinimitable.sys_defaults && mrinimitable.sys_defaults.date_format) || "yyyy-mm-dd";
	},

	get_user_fmt: function () {
		// For backwards compatibility only
		return (mrinimitable.sys_defaults && mrinimitable.sys_defaults.date_format) || "yyyy-mm-dd";
	},

	/**
	 * Converts a datetime string from system format to user format.
	 *
	 * If a full datetime string is provided, it is assumed to be in the system
	 * timezone and converted to the user's timezone.
	 *
	 * @param {string} val - The datetime string to convert
	 * @param {boolean} only_time - If true, parses and returns a time string only
	 * @param {boolean} only_date - If true, parses and returns a date string only
	 * @returns {string} The datetime string in user format
	 */
	str_to_user: function (val, only_time = false, only_date = false) {
		if (!val) {
			return "";
		}

		const user_date_fmt = mrinimitable.datetime.get_user_date_fmt().toUpperCase();
		const user_time_fmt = mrinimitable.datetime.get_user_time_fmt();

		if (only_time) {
			let date_obj = moment(val, mrinimitable.defaultTimeFormat);
			return date_obj.format(user_time_fmt);
		} else if (only_date || (typeof val === "string" && val.indexOf(" ") === -1)) {
			let date_obj = moment(val, mrinimitable.defaultDateFormat);
			return date_obj.format(user_date_fmt);
		} else {
			const system_datetime = moment.tz(
				val,
				mrinimitable.defaultDatetimeFormat,
				mrinimitable.boot.time_zone.system
			);
			const user_datetime = system_datetime.clone().tz(mrinimitable.boot.time_zone.user);

			return user_datetime.format(user_date_fmt + " " + user_time_fmt);
		}
	},

	get_datetime_as_string: function (d) {
		let time_format = mrinimitable?.boot?.sysdefaults?.time_format || mrinimitable.defaultTimeFormat;
		let datetime_format = mrinimitable.defaultDateFormat + " " + time_format;
		return moment(d).format(datetime_format);
	},

	user_to_str: function (val, only_time = false) {
		var user_time_fmt = mrinimitable.datetime.get_user_time_fmt();
		if (only_time) {
			return moment(val, user_time_fmt).format(mrinimitable.defaultTimeFormat);
		}

		var user_fmt = mrinimitable.datetime.get_user_date_fmt().toUpperCase();
		var system_fmt = "YYYY-MM-DD";

		if (val.indexOf(" ") !== -1) {
			user_fmt += " " + user_time_fmt;
			system_fmt += " HH:mm:ss";
		}

		// user_fmt.replace("YYYY", "YY")? user might only input 2 digits of the year, which should also be parsed
		return moment(val, [user_fmt.replace("YYYY", "YY"), user_fmt])
			.locale("en")
			.format(system_fmt);
	},

	user_to_obj: function (d) {
		return mrinimitable.datetime.str_to_obj(mrinimitable.datetime.user_to_str(d));
	},

	global_date_format: function (d) {
		var m = moment(d);
		if (m._f && m._f.indexOf("HH") !== -1) {
			return m.format("Do MMMM YYYY, hh:mm A");
		} else {
			return m.format("Do MMMM YYYY");
		}
	},

	now_date: function (as_obj = false) {
		return mrinimitable.datetime._date(mrinimitable.defaultDateFormat, as_obj);
	},

	now_time: function (as_obj = false) {
		return mrinimitable.datetime._date(mrinimitable.defaultTimeFormat, as_obj);
	},

	now_datetime: function (as_obj = false) {
		return mrinimitable.datetime._date(mrinimitable.defaultDatetimeFormat, as_obj);
	},

	system_datetime: function (as_obj = false) {
		return mrinimitable.datetime._date(mrinimitable.defaultDatetimeFormat, as_obj, true);
	},

	_date: function (format, as_obj = false, system_time = false) {
		let time_zone = mrinimitable.boot.time_zone?.system || mrinimitable.sys_defaults.time_zone;

		// Whenever we are getting now_date/datetime, always make sure dates are fetched using user time zone.
		// This is to make sure that time is as per user time zone set in User doctype, If a user had to change the timezone,
		// we will end up having multiple timezone by not honouring timezone in User doctype.
		// This will make sure that at any point we know which timezone the user if following and not have random timezone
		// when the timezone of the local machine changes.
		if (!system_time) {
			time_zone = mrinimitable.boot.time_zone?.user || time_zone;
		}
		let date = moment.tz(time_zone);

		return as_obj ? mrinimitable.datetime.moment_to_date_obj(date) : date.format(format);
	},

	moment_to_date_obj: function (moment_obj) {
		const date_obj = new Date();
		const date_array = moment_obj.toArray();
		date_obj.setFullYear(date_array[0]);
		date_obj.setMonth(date_array[1]);
		date_obj.setDate(date_array[2]);
		date_obj.setHours(date_array[3]);
		date_obj.setMinutes(date_array[4]);
		date_obj.setSeconds(date_array[5]);
		date_obj.setMilliseconds(date_array[6]);
		return date_obj;
	},

	nowdate: function () {
		return mrinimitable.datetime.now_date();
	},

	get_today: function () {
		return mrinimitable.datetime.now_date();
	},

	get_time: (timestamp) => {
		// return time with AM/PM
		return moment(timestamp).format("hh:mm A");
	},

	validate: function (d) {
		return moment(
			d,
			[mrinimitable.defaultDateFormat, mrinimitable.defaultDatetimeFormat, mrinimitable.defaultTimeFormat],
			true
		).isValid();
	},

	get_first_day_of_the_week_index() {
		const first_day_of_the_week = mrinimitable.sys_defaults.first_day_of_the_week || "Sunday";
		return moment.weekdays().indexOf(first_day_of_the_week);
	},
});
