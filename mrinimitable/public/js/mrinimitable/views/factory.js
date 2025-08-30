// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.provide("mrinimitable.pages");
mrinimitable.provide("mrinimitable.views");

mrinimitable.views.Factory = class Factory {
	constructor(opts) {
		$.extend(this, opts);
	}

	show() {
		this.route = mrinimitable.get_route();
		this.page_name = mrinimitable.get_route_str();

		if (this.before_show && this.before_show() === false) return;

		if (mrinimitable.pages[this.page_name]) {
			mrinimitable.container.change_to(this.page_name);
			if (this.on_show) {
				this.on_show();
			}
		} else {
			if (this.route[1]) {
				this.make(this.route);
			} else {
				mrinimitable.show_not_found(this.route);
			}
		}
	}

	make_page(double_column, page_name, sidebar_postition) {
		return mrinimitable.make_page(double_column, page_name, sidebar_postition);
	}
};

mrinimitable.make_page = function (double_column, page_name, sidebar_position) {
	if (!page_name) {
		page_name = mrinimitable.get_route_str();
	}

	const page = mrinimitable.container.add_page(page_name);

	mrinimitable.ui.make_app_page({
		parent: page,
		single_column: !double_column,
		sidebar_position: sidebar_position,
		disable_sidebar_toggle: !sidebar_position,
	});

	mrinimitable.container.change_to(page_name);
	return page;
};
