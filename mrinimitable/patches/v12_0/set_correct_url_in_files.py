import os

import mrinimitable


def execute():
	files = mrinimitable.get_all(
		"File",
		fields=["name", "file_name", "file_url"],
		filters={
			"is_folder": 0,
			"file_url": ["!=", ""],
		},
	)

	private_file_path = mrinimitable.get_site_path("private", "files")
	public_file_path = mrinimitable.get_site_path("public", "files")

	for file in files:
		file_path = file.file_url
		file_name = file_path.split("/")[-1]

		if not file_path.startswith(("/private/", "/files/")):
			continue

		file_is_private = file_path.startswith("/private/files/")
		full_path = mrinimitable.utils.get_files_path(file_name, is_private=file_is_private)

		if not os.path.exists(full_path):
			if file_is_private:
				public_file_url = os.path.join(public_file_path, file_name)
				if os.path.exists(public_file_url):
					mrinimitable.db.set_value(
						"File", file.name, {"file_url": f"/files/{file_name}", "is_private": 0}
					)
			else:
				private_file_url = os.path.join(private_file_path, file_name)
				if os.path.exists(private_file_url):
					mrinimitable.db.set_value(
						"File", file.name, {"file_url": f"/private/files/{file_name}", "is_private": 1}
					)
