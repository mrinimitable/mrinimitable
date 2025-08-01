// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.db = {
	get_list: function (doctype, args) {
		if (!args) {
			args = {};
		}
		args.doctype = doctype;
		if (!args.fields) {
			args.fields = ["name"];
		}
		if (!("limit" in args)) {
			args.limit = 20;
		}
		return new Promise((resolve) => {
			mrinimitable.call({
				method: "mrinimitable.desk.reportview.get_list",
				args: args,
				type: "GET",
				callback: function (r) {
					resolve(r.message);
				},
			});
		});
	},
	exists: function (doctype, nameOrFilters) {
		return new Promise((resolve) => {
			let filters;
			if (typeof nameOrFilters === "string") {
				// may be cached and more effecient
				mrinimitable.db.get_value(doctype, { name: nameOrFilters }, "name").then((r) => {
					r.message && r.message.name ? resolve(true) : resolve(false);
				});
			} else if (typeof nameOrFilters === "object") {
				mrinimitable.db.count(doctype, { filters: nameOrFilters, limit: 1 }).then((count) => {
					resolve(count > 0);
				});
			}
		});
	},
	get_value: function (doctype, filters, fieldname, callback, parent_doc) {
		return mrinimitable.call({
			method: "mrinimitable.client.get_value",
			type: "GET",
			args: {
				doctype: doctype,
				fieldname: fieldname,
				filters: filters,
				parent: parent_doc,
			},
			callback: function (r) {
				callback && callback(r.message);
			},
		});
	},
	get_single_value: (doctype, field) => {
		return new Promise((resolve) => {
			mrinimitable
				.call({
					method: "mrinimitable.client.get_single_value",
					args: { doctype, field },
					type: "GET",
				})
				.then((r) => resolve(r ? r.message : null));
		});
	},
	set_value: function (doctype, docname, fieldname, value, callback) {
		return mrinimitable.call({
			method: "mrinimitable.client.set_value",
			args: {
				doctype: doctype,
				name: docname,
				fieldname: fieldname,
				value: value,
			},
			callback: function (r) {
				callback && callback(r.message);
			},
		});
	},
	get_doc: function (doctype, name, filters) {
		return new Promise((resolve, reject) => {
			mrinimitable
				.call({
					method: "mrinimitable.client.get",
					type: "GET",
					args: { doctype, name, filters },
					callback: (r) => {
						mrinimitable.model.sync(r.message);
						resolve(r.message);
					},
				})
				.fail(reject);
		});
	},
	insert: function (doc) {
		return mrinimitable.xcall("mrinimitable.client.insert", { doc });
	},
	delete_doc: function (doctype, name) {
		return new Promise((resolve) => {
			mrinimitable.call("mrinimitable.client.delete", { doctype, name }, (r) => resolve(r.message));
		});
	},
	count: function (doctype, args = {}, cache = false) {
		let filters = args.filters || {};
		let limit = args.limit;

		// has a filter with childtable?
		const distinct =
			Array.isArray(filters) &&
			filters.some((filter) => {
				return filter[0] !== doctype;
			});

		const fields = [];

		return mrinimitable.xcall(
			"mrinimitable.desk.reportview.get_count",
			{
				doctype,
				filters,
				fields,
				distinct,
				limit,
			},
			cache ? "GET" : "POST",
			{ cache }
		);
	},
	get_link_options(doctype, txt = "", filters = {}) {
		return new Promise((resolve) => {
			mrinimitable.call({
				type: "GET",
				method: "mrinimitable.desk.search.search_link",
				args: {
					doctype,
					txt,
					filters,
				},
				callback(r) {
					resolve(r.message);
				},
			});
		});
	},
};
