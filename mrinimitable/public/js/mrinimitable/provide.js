// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// provide a namespace
if (!window.mrinimitable) window.mrinimitable = {};

mrinimitable.provide = function (namespace) {
	// docs: create a namespace //
	var nsl = namespace.split(".");
	var parent = window;
	for (var i = 0; i < nsl.length; i++) {
		var n = nsl[i];
		if (!parent[n]) {
			parent[n] = {};
		}
		parent = parent[n];
	}
	return parent;
};

mrinimitable.provide("locals");
mrinimitable.provide("mrinimitable.flags");
mrinimitable.provide("mrinimitable.settings");
mrinimitable.provide("mrinimitable.utils");
mrinimitable.provide("mrinimitable.ui.form");
mrinimitable.provide("mrinimitable.modules");
mrinimitable.provide("mrinimitable.templates");
mrinimitable.provide("mrinimitable.test_data");
mrinimitable.provide("mrinimitable.utils");
mrinimitable.provide("mrinimitable.model");
mrinimitable.provide("mrinimitable.user");
mrinimitable.provide("mrinimitable.session");
mrinimitable.provide("mrinimitable._messages");
mrinimitable.provide("locals.DocType");

// for listviews
mrinimitable.provide("mrinimitable.listview_settings");
mrinimitable.provide("mrinimitable.tour");
mrinimitable.provide("mrinimitable.listview_parent_route");

// constants
window.NEWLINE = "\n";
window.TAB = 9;
window.UP_ARROW = 38;
window.DOWN_ARROW = 40;

// proxy for user globals defined in desk.js

// API globals
window.cur_frm = null;
