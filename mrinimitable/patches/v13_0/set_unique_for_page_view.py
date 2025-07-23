import mrinimitable


def execute():
	mrinimitable.reload_doc("website", "doctype", "web_page_view", force=True)
	site_url = mrinimitable.utils.get_site_url(mrinimitable.local.site)
	mrinimitable.db.sql(f"""UPDATE `tabWeb Page View` set is_unique=1 where referrer LIKE '%{site_url}%'""")
