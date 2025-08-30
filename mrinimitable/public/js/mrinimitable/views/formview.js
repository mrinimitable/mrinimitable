// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.provide("mrinimitable.views.formview");

mrinimitable.views.FormFactory = class FormFactory extends mrinimitable.views.Factory {
	make(route) {
		var doctype = route[1],
			doctype_layout = mrinimitable.router.doctype_layout || doctype;

		if (!mrinimitable.views.formview[doctype_layout]) {
			mrinimitable.model.with_doctype(doctype, () => {
				this.page = mrinimitable.container.add_page(doctype_layout);
				mrinimitable.views.formview[doctype_layout] = this.page;
				this.make_and_show(doctype, route);
			});
		} else {
			this.show_doc(route);
		}

		this.setup_events();
	}

	make_and_show(doctype, route) {
		if (mrinimitable.router.doctype_layout) {
			mrinimitable.model.with_doc("DocType Layout", mrinimitable.router.doctype_layout, () => {
				this.make_form(doctype);
				this.show_doc(route);
			});
		} else {
			this.make_form(doctype);
			this.show_doc(route);
		}
	}

	make_form(doctype) {
		this.page.frm = new mrinimitable.ui.form.Form(
			doctype,
			this.page,
			true,
			mrinimitable.router.doctype_layout
		);
	}

	setup_events() {
		if (!this.initialized) {
			$(document).on("page-change", function () {
				mrinimitable.ui.form.close_grid_form();
			});
		}
		this.initialized = true;
	}

	show_doc(route) {
		var doctype = route[1],
			doctype_layout = mrinimitable.router.doctype_layout || doctype,
			name = route.slice(2).join("/");

		if (mrinimitable.model.new_names[name]) {
			// document has been renamed, reroute
			name = mrinimitable.model.new_names[name];
			mrinimitable.set_route("Form", doctype_layout, name);
			return;
		}

		const doc = mrinimitable.get_doc(doctype, name);
		if (
			doc &&
			mrinimitable.model.get_docinfo(doctype, name) &&
			(doc.__islocal || mrinimitable.model.is_fresh(doc))
		) {
			// is document available and recent?
			this.render(doctype_layout, name);
		} else {
			this.fetch_and_render(doctype, name, doctype_layout);
		}
	}

	fetch_and_render(doctype, name, doctype_layout) {
		mrinimitable.model.with_doc(doctype, name, (name, r) => {
			if (r && r["403"]) return; // not permitted

			if (!(locals[doctype] && locals[doctype][name])) {
				if (name && name.substr(0, 3) === "new") {
					this.render_new_doc(doctype, name, doctype_layout);
				} else {
					mrinimitable.show_not_found();
				}
				return;
			}
			this.render(doctype_layout, name);
		});
	}

	render_new_doc(doctype, name, doctype_layout) {
		const new_name = mrinimitable.model.make_new_doc_and_get_name(doctype, true);
		if (new_name === name) {
			this.render(doctype_layout, name);
		} else {
			mrinimitable.route_flags.replace_route = true;
			mrinimitable.set_route("Form", doctype_layout, new_name);
		}
	}

	render(doctype_layout, name) {
		mrinimitable.container.change_to(doctype_layout);
		mrinimitable.views.formview[doctype_layout].frm.refresh(name);
	}
};
