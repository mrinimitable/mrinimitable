import mrinimitable


def execute():
	mrinimitable.reload_doc("website", "doctype", "web_page_view", force=True)
	mrinimitable.db.sql("""UPDATE `tabWeb Page View` set path='/' where path=''""")
