# Copyright (c) 2021, Mrinimitable Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt


import functools

import mrinimitable


@mrinimitable.whitelist()
def get_google_fonts():
	return _get_google_fonts()


@functools.lru_cache
def _get_google_fonts():
	file_path = mrinimitable.get_app_path("mrinimitable", "data", "google_fonts.json")
	return mrinimitable.parse_json(mrinimitable.read_file(file_path))
