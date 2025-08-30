import mrinimitable

base_template_path = "www/robots.txt"


def get_context(context):
	robots_txt = (
		mrinimitable.db.get_single_value("Website Settings", "robots_txt")
		or (mrinimitable.local.conf.robots_txt and mrinimitable.read_file(mrinimitable.local.conf.robots_txt))
		or ""
	)

	return {"robots_txt": robots_txt}
