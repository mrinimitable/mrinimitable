import os

import mrinimitable


def execute():
	file_names_with_url = mrinimitable.get_all(
		"File",
		filters={"is_folder": 0, "file_name": ["like", "%/%"]},
		fields=["name", "file_name", "file_url"],
	)

	for f in file_names_with_url:
		filename = f.file_name.rsplit("/", 1)[-1]

		if not f.file_url:
			f.file_url = f.file_name

		try:
			if not file_exists(f.file_url):
				continue
			mrinimitable.db.set_value(
				"File", f.name, {"file_name": filename, "file_url": f.file_url}, update_modified=False
			)
		except Exception:
			continue


def file_exists(file_path):
	file_path = mrinimitable.utils.get_files_path(
		file_path.rsplit("/", 1)[-1], is_private=file_path.startswith("/private")
	)
	return os.path.exists(file_path)
