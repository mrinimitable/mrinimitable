// Copyright (c) 2024, Mrinimitable Technologies and contributors
// For license information, please see license.txt

mrinimitable.ui.form.on("Role Replication", {
	refresh(frm) {
		frm.disable_save();
		frm.page.set_primary_action(__("Replicate"), ($btn) => {
			$btn.text(__("Replicating..."));
			mrinimitable.run_serially([
				() => mrinimitable.dom.freeze("Replicating..."),
				() => frm.call("replicate_role"),
				() => mrinimitable.dom.unfreeze(),
				() => mrinimitable.msgprint(__("Replication completed.")),
				() => $btn.text(__("Replicate")),
			]);
		});
	},
});
