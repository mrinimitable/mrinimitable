// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.provide("mrinimitable.views.pageview");
mrinimitable.provide("mrinimitable.standard_pages");

mrinimitable.views.pageview = {
	with_page: function (name, callback) {
		if (mrinimitable.standard_pages[name]) {
			if (!mrinimitable.pages[name]) {
				mrinimitable.standard_pages[name]();
			}
			callback();
			return;
		}

		if (
			(locals.Page && locals.Page[name] && locals.Page[name].script) ||
			name == window.page_name
		) {
			// already loaded
			callback();
		} else if (localStorage["_page:" + name] && mrinimitable.boot.developer_mode != 1) {
			// cached in local storage
			mrinimitable.model.sync(JSON.parse(localStorage["_page:" + name]));
			callback();
		} else if (name) {
			// get fresh
			return mrinimitable.call({
				method: "mrinimitable.desk.desk_page.getpage",
				args: { name: name },
				callback: function (r) {
					if (!r.docs._dynamic_page) {
						try {
							localStorage["_page:" + name] = JSON.stringify(r.docs);
						} catch (e) {
							console.warn(e);
						}
					}
					callback();
				},
				error: function () {
					mrinimitable.search.utils.results_to_hide.push(name);
				},
				freeze: true,
			});
		}
	},

	show: function (name) {
		if (!name) {
			name = mrinimitable.boot ? mrinimitable.boot.home_page : window.page_name;
		}
		mrinimitable.model.with_doctype("Page", function () {
			mrinimitable.views.pageview.with_page(name, function (r) {
				if (r && r.exc) {
					if (!r["403"]) mrinimitable.show_not_found(name);
				} else if (!mrinimitable.pages[name]) {
					new mrinimitable.views.Page(name);
				}
				mrinimitable.container.change_to(name);
			});
		});
	},
};

mrinimitable.views.Page = class Page {
	constructor(name) {
		this.name = name;
		var me = this;

		// web home page
		if (name == window.page_name) {
			this.wrapper = document.getElementById("page-" + name);
			this.wrapper.label = document.title || window.page_name;
			this.wrapper.page_name = window.page_name;
			mrinimitable.pages[window.page_name] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.name];
			if (!this.pagedoc) {
				mrinimitable.show_not_found(name);
				return;
			}
			this.wrapper = mrinimitable.container.add_page(this.name);
			this.wrapper.page_name = this.pagedoc.name;

			// set content, script and style
			if (this.pagedoc.content) this.wrapper.innerHTML = this.pagedoc.content;
			mrinimitable.dom.eval(this.pagedoc.__script || this.pagedoc.script || "");
			mrinimitable.dom.set_style(this.pagedoc.style || "");

			// set breadcrumbs
			mrinimitable.breadcrumbs.add(this.pagedoc.module || null);
		}

		this.trigger_page_event("on_page_load");

		// set events
		$(this.wrapper).on("show", function () {
			window.cur_frm = null;
			me.trigger_page_event("on_page_show");
			me.trigger_page_event("refresh");
		});
	}

	trigger_page_event(eventname) {
		var me = this;
		if (me.wrapper[eventname]) {
			me.wrapper[eventname](me.wrapper);
		}
	}
};

mrinimitable.show_not_found = function (page_name) {
	mrinimitable.show_message_page({
		page_name: page_name,
		message: __("Sorry! I could not find what you were looking for."),
		img: "/assets/mrinimitable/images/ui/bubble-tea-sorry.svg",
	});
};

mrinimitable.show_not_permitted = function (page_name) {
	mrinimitable.show_message_page({
		page_name: page_name,
		message: __("Sorry! You are not permitted to view this page."),
		img: "/assets/mrinimitable/images/ui/bubble-tea-sorry.svg",
		// icon: "octicon octicon-circle-slash"
	});
};

mrinimitable.show_message_page = function (opts) {
	// opts can include `page_name`, `message`, `icon` or `img`
	if (!opts.page_name) {
		opts.page_name = mrinimitable.get_route_str();
	}

	if (opts.icon) {
		opts.img = repl('<span class="%(icon)s message-page-icon"></span> ', opts);
	} else if (opts.img) {
		opts.img = repl('<img src="%(img)s" class="message-page-image">', opts);
	}

	var page = mrinimitable.pages[opts.page_name] || mrinimitable.container.add_page(opts.page_name);
	$(page).html(
		repl(
			'<div class="page message-page">\
			<div class="text-center message-page-content">\
				%(img)s\
				<p class="lead">%(message)s</p>\
				<a class="btn btn-default btn-sm btn-home" href="/app">%(home)s</a>\
			</div>\
		</div>',
			{
				img: opts.img || "",
				message: opts.message || "",
				home: __("Home"),
			}
		)
	);

	mrinimitable.container.change_to(opts.page_name);
};
