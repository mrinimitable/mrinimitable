# Copyright (c) 2020, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable
from mrinimitable.search.full_text_search import FullTextSearch
from mrinimitable.search.sqlite_search import SQLiteSearch
from mrinimitable.search.website_search import WebsiteSearch
from mrinimitable.utils import cint


@mrinimitable.whitelist(allow_guest=True)
def web_search(query, scope=None, limit=20):
	limit = cint(limit)
	ws = WebsiteSearch(index_name="web_routes")
	return ws.search(query, scope, limit)
