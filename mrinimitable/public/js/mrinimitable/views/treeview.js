// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
mrinimitable.provide("mrinimitable.treeview_settings");
mrinimitable.provide("mrinimitable.views.trees");
window.cur_tree = null;

mrinimitable.views.TreeFactory = class TreeFactory extends mrinimitable.views.Factory {
	make(route) {
		mrinimitable.model.with_doctype(route[1], function () {
			var options = {
				doctype: route[1],
				meta: mrinimitable.get_meta(route[1]),
			};

			if (
				!mrinimitable.treeview_settings[route[1]] &&
				!mrinimitable.meta.get_docfield(route[1], "is_group")
			) {
				mrinimitable.msgprint(__("Tree view is not available for {0}", [route[1]]));
				return false;
			}
			$.extend(options, mrinimitable.treeview_settings[route[1]] || {});
			mrinimitable.views.trees[options.doctype] = new mrinimitable.views.TreeView(options);
		});
	}

	on_show() {
		/**
		 * When the the treeview is visited using the previous button,
		 * the framework just show the treeview element that is hidden.
		 * Due to this, the data of the tree can be old.
		 * To deal with this, the tree will be refreshed whenever the
		 * treeview is visible.
		 */
		let route = mrinimitable.get_route();
		let treeview = mrinimitable.views.trees[route[1]];
		treeview && treeview.make_tree();
	}

	get view_name() {
		return "Tree";
	}
};

mrinimitable.views.TreeView = class TreeView {
	constructor(opts) {
		var me = this;

		this.opts = {};
		this.opts.get_tree_root = true;
		this.opts.show_expand_all = true;
		$.extend(this.opts, opts);
		this.doctype = opts.doctype;
		this.args = { doctype: me.doctype };
		this.page_name = mrinimitable.get_route_str();
		this.get_tree_nodes = me.opts.get_tree_nodes || "mrinimitable.desk.treeview.get_children";

		this.get_permissions();

		this.make_page();
		this.make_filters();
		this.root_value = null;
		if (me.opts.get_tree_root) {
			this.get_root();
		}

		this.onload();

		if (!this.opts.do_not_setup_menu) {
			this.set_menu_item();
		}

		this.set_primary_action();
	}
	get_permissions() {
		this.can_read = mrinimitable.model.can_read(this.doctype);
		this.can_create =
			mrinimitable.boot.user.can_create.indexOf(this.doctype) !== -1 ||
			mrinimitable.boot.user.in_create.indexOf(this.doctype) !== -1;
		this.can_write = mrinimitable.model.can_write(this.doctype);
		this.can_delete = mrinimitable.model.can_delete(this.doctype);
	}
	make_page() {
		var me = this;
		if (!this.opts || !this.opts.do_not_make_page) {
			this.parent = mrinimitable.container.add_page(this.page_name);
			$(this.parent).addClass("treeview");
			mrinimitable.ui.make_app_page({ parent: this.parent, single_column: true });
			this.page = this.parent.page;
			mrinimitable.container.change_to(this.page_name);
			mrinimitable.breadcrumbs.add(
				me.opts.breadcrumb || locals.DocType[me.doctype].module,
				me.doctype
			);

			this.set_title();

			this.page.main.css({
				"min-height": "300px",
			});

			this.page.main.addClass("mrinimitable-card");
		} else {
			this.page = this.opts.page;
			$(this.page[0]).addClass("mrinimitable-card");
		}

		if (mrinimitable.meta.has_field(me.doctype, "disabled")) {
			this.page.add_inner_button(
				__("Include Disabled"),
				function () {
					me.toggle_disable(event.target);
					me.make_tree();
				},
				__("Expand"),
				"default",
				true
			);
		}

		if (this.opts.show_expand_all) {
			this.page.add_inner_button(
				__("Collapse All"),
				function () {
					me.tree.load_children(me.tree.root_node, false);
				},
				__("Expand"),
				"default",
				true
			);

			this.page.add_inner_button(
				__("Expand All"),
				function () {
					me.tree.load_children(me.tree.root_node, true);
				},
				__("Expand"),
				"default",
				true
			);
		}

		if (this.opts.view_template) {
			var row = $('<div class="row"><div>').appendTo(this.page.main);
			this.body = $('<div class="col-sm-6 col-xs-12"></div>').appendTo(row);
			this.node_view = $('<div class="col-sm-6 hidden-xs"></div>').appendTo(row);
		} else {
			this.body = this.page.main;
		}
	}
	set_title() {
		this.page.set_title(this.opts.title || __("{0} Tree", [__(this.doctype)]));
	}
	onload() {
		var me = this;
		this.opts.onload && this.opts.onload(me);
	}
	make_filters() {
		var me = this;
		mrinimitable.treeview_settings.filters = [];
		$.each(this.opts.filters || [], function (i, filter) {
			if (mrinimitable.route_options && mrinimitable.route_options[filter.fieldname]) {
				filter.default = mrinimitable.route_options[filter.fieldname];
			}

			if (!filter.disable_onchange) {
				filter.change = function () {
					filter.onchange && filter.onchange();
					var val = this.get_value();
					me.args[filter.fieldname] = val;
					if (val) {
						me.root_label = val;
					} else {
						me.root_label = me.opts.root_label;
					}
					me.set_title();
					me.make_tree();
				};
			}

			if (filter.render_on_toolbar) {
				me.page.add_field(filter, me.page.filters);
			} else {
				me.page.add_field(filter);
			}

			if (filter.default) {
				$("[data-fieldname='" + filter.fieldname + "']").trigger("change");
			}
		});
	}
	get_root() {
		var me = this;
		mrinimitable.call({
			method: me.get_tree_nodes,
			args: me.args,
			callback: function (r) {
				if (r.message) {
					me.root_label = me.doctype;
					me.root_value = "";
					me.make_tree();
				}
			},
		});
	}
	toggle_disable(el) {
		if (this.args["include_disabled"]) {
			this.args["include_disabled"] = false;
			el.innerText = el.innerText.replace("Exclude", "Include");
		} else {
			this.args["include_disabled"] = true;
			console.log(el);
			el.innerText = el.innerText.replace("Include", "Exclude");
		}
	}
	make_tree() {
		$(this.parent).find(".tree").remove();

		var use_label = this.args[this.opts.root_label] || this.root_label || this.opts.root_label;
		var use_value = this.root_value;
		if (use_value == null) {
			use_value = use_label;
		}

		this.tree = new mrinimitable.ui.Tree({
			parent: this.body,
			label: use_label,
			root_value: use_value,
			expandable: true,

			args: this.args,
			method: this.get_tree_nodes,

			// array of button props: {label, condition, click, btnClass}
			toolbar: this.get_toolbar(),

			get_label: this.opts.get_label,
			on_render: this.opts.onrender,
			on_get_node: this.opts.on_get_node,
			on_click: (node) => {
				this.select_node(node);
			},
		});

		cur_tree = this.tree;
		cur_tree.view_name = "Tree";
		this.post_render();
	}
	toggle_label() {
		console.log("hello");
	}
	rebuild_tree() {
		let me = this;
		mrinimitable.call({
			method: "mrinimitable.utils.nestedset.rebuild_tree",
			args: {
				doctype: me.doctype,
			},
			callback: function (r) {
				if (!r.exc) {
					me.make_tree();
				}
			},
		});
	}

	post_render() {
		var me = this;
		me.opts.post_render && me.opts.post_render(me);
	}

	select_node(node) {
		var me = this;
		if (this.opts.click) {
			this.opts.click(node);
		}
		if (this.opts.view_template) {
			this.node_view.empty();
			$(
				mrinimitable.render_template(me.opts.view_template, {
					data: node.data,
					doctype: me.doctype,
				})
			).appendTo(this.node_view);
		}
	}
	get_toolbar() {
		var me = this;

		var toolbar = [
			{
				label: __(me.can_write ? "Edit" : "Details"),
				condition: function (node) {
					return !node.is_root && me.can_read;
				},
				click: function (node) {
					mrinimitable.set_route("Form", me.doctype, node.label);
				},
			},
			{
				label: __("Add Child"),
				condition: function (node) {
					return me.can_create && node.expandable && !node.hide_add;
				},
				click: function (node) {
					me.new_node();
				},
				btnClass: "hidden-xs",
			},
			{
				label: __("Rename"),
				condition: function (node) {
					let allow_rename = true;
					if (me.doctype && mrinimitable.get_meta(me.doctype)) {
						if (!mrinimitable.get_meta(me.doctype).allow_rename) allow_rename = false;
					}
					return !node.is_root && me.can_write && allow_rename;
				},
				click: function (node) {
					mrinimitable.model.rename_doc(me.doctype, node.label, function (new_name) {
						node.$tree_link.find("a").text(new_name);
						node.label = new_name;
						me.tree.refresh();
					});
				},
				btnClass: "hidden-xs",
			},
			{
				label: __("Delete"),
				condition: function (node) {
					return !node.is_root && me.can_delete;
				},
				click: function (node) {
					mrinimitable.model.delete_doc(me.doctype, node.label, function () {
						node.parent.remove();
					});
				},
				btnClass: "hidden-xs",
			},
		];

		if (this.opts.toolbar && this.opts.extend_toolbar) {
			toolbar = toolbar.filter((btn) => {
				return !me.opts.toolbar.find((d) => d["label"] == btn["label"]);
			});
			return toolbar.concat(this.opts.toolbar);
		} else if (this.opts.toolbar && !this.opts.extend_toolbar) {
			return this.opts.toolbar;
		} else {
			return toolbar;
		}
	}
	new_node() {
		var me = this;
		var node = me.tree.get_selected_node();

		if (!(node && node.expandable)) {
			mrinimitable.msgprint(__("Select a group node first."));
			return;
		}

		this.prepare_fields();

		// the dialog
		var d = new mrinimitable.ui.Dialog({
			title: __("New {0}", [__(me.doctype)]),
			fields: me.fields,
		});

		var args = $.extend({}, me.args);
		args["parent_" + me.doctype.toLowerCase().replace(/ /g, "_").replace(/-/g, "_")] =
			me.args["parent"];

		d.set_value("is_group", 0);
		d.set_values(args);

		// create
		d.set_primary_action(__("Create New"), function () {
			var btn = this;
			var v = d.get_values();
			if (!v) return;

			v.parent = node.label;
			v.doctype = me.doctype;

			if (node.is_root) {
				v["is_root"] = node.is_root;
			} else {
				v["is_root"] = false;
			}

			d.hide();
			mrinimitable.dom.freeze(__("Creating {0}", [me.doctype]));

			$.extend(args, v);
			return mrinimitable.call({
				method: me.opts.add_tree_node || "mrinimitable.desk.treeview.add_node",
				args: args,
				callback: function (r) {
					if (!r.exc) {
						me.tree.load_children(node);
					}
				},
				always: function () {
					mrinimitable.dom.unfreeze();
				},
			});
		});
		d.show();
	}
	prepare_fields() {
		var me = this;

		this.fields = [
			{
				fieldtype: "Check",
				fieldname: "is_group",
				label: __("Group Node"),
				description: __("Further nodes can be only created under 'Group' type nodes"),
			},
		];

		if (this.opts.fields) {
			this.fields = this.opts.fields;
		}

		this.ignore_fields = this.opts.ignore_fields || [];

		var mandatory_fields = $.map(me.opts.meta.fields, function (d) {
			return d.reqd || (d.bold && !d.read_only && !!d.is_virtual) ? d : null;
		});

		var opts_field_names = this.fields.map(function (d) {
			return d.fieldname;
		});

		mandatory_fields.map(function (d) {
			if (
				$.inArray(d.fieldname, me.ignore_fields) === -1 &&
				$.inArray(d.fieldname, opts_field_names) === -1
			) {
				me.fields.push(d);
			}
		});
	}
	print_tree() {
		if (!mrinimitable.model.can_print(this.doctype)) {
			mrinimitable.msgprint(__("You are not allowed to print this report"));
			return false;
		}
		var tree = $(".tree:visible").html();
		var me = this;
		mrinimitable.ui.get_print_settings(false, function (print_settings) {
			var title = __(me.docname || me.doctype);
			mrinimitable.render_tree({ title: title, tree: tree, print_settings: print_settings });
			mrinimitable.call({
				method: "mrinimitable.core.doctype.access_log.access_log.make_access_log",
				args: {
					doctype: me.doctype,
					report_name: me.page_name,
					page: tree,
					method: "Print",
				},
			});
		});
	}
	set_primary_action() {
		var me = this;
		if (!this.opts.disable_add_node && this.can_create) {
			me.page.set_primary_action(
				__("New"),
				function () {
					me.new_node();
				},
				"add"
			);
		}
	}
	set_menu_item() {
		var me = this;

		this.menu_items = [
			{
				label: __("View List"),
				action: function () {
					mrinimitable.set_route("List", me.doctype);
				},
			},
			{
				label: __("Print"),
				action: function () {
					me.print_tree();
				},
			},
			{
				label: __("Refresh"),
				action: function () {
					me.make_tree();
				},
			},
		];

		if (
			mrinimitable.user.has_role("System Manager") &&
			mrinimitable.meta.has_field(me.doctype, "lft") &&
			mrinimitable.meta.has_field(me.doctype, "rgt")
		) {
			this.menu_items.push({
				label: __("Rebuild Tree"),
				action: function () {
					me.rebuild_tree();
				},
			});
		}

		if (me.opts.menu_items) {
			me.menu_items.push.apply(me.menu_items, me.opts.menu_items);
		}

		$.each(me.menu_items, function (i, menu_item) {
			var has_perm = true;
			if (menu_item["condition"]) {
				has_perm = eval(menu_item["condition"]);
			}

			if (has_perm) {
				me.page.add_menu_item(menu_item["label"], menu_item["action"]);
			}
		});
	}
};
