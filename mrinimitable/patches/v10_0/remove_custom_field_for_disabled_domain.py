import mrinimitable


def execute():
	mrinimitable.reload_doc("core", "doctype", "domain")
	mrinimitable.reload_doc("core", "doctype", "has_domain")
	active_domains = mrinimitable.get_active_domains()
	all_domains = mrinimitable.get_all("Domain")

	for d in all_domains:
		if d.name not in active_domains:
			inactive_domain = mrinimitable.get_doc("Domain", d.name)
			inactive_domain.setup_data()
			inactive_domain.remove_custom_field()
