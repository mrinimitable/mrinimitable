mrinimitable.provide("mrinimitable.model");
mrinimitable.provide("mrinimitable.utils");

/**
 * Opens the Website Meta Tag form if it exists for {route}
 * or creates a new doc and opens the form
 */
mrinimitable.utils.set_meta_tag = function (route) {
	mrinimitable.db.exists("Website Route Meta", route).then((exists) => {
		if (exists) {
			mrinimitable.set_route("Form", "Website Route Meta", route);
		} else {
			// new doc
			const doc = mrinimitable.model.get_new_doc("Website Route Meta");
			doc.__newname = route;
			mrinimitable.set_route("Form", doc.doctype, doc.name);
		}
	});
};
