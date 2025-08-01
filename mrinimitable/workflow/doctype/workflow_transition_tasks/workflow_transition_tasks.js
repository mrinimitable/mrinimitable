// Copyright (c) 2025, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Workflow Transition Tasks", {
	refresh: function (frm) {
		mrinimitable
			.call({
				method: "mrinimitable.workflow.doctype.workflow.workflow.get_workflow_methods",
				type: "GET",
			})
			.then((options) => {
				frm.get_field("tasks").grid.update_docfield_property(
					"task",
					"options",
					options.message
				);
			});
	},
});
