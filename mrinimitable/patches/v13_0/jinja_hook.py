# Copyright (c) 2021, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from click import secho

import mrinimitable


def execute():
	if mrinimitable.get_hooks("jenv"):
		print()
		secho(
			'WARNING: The hook "jenv" is deprecated. Follow the migration guide to use the new "jinja" hook.',
			fg="yellow",
		)
		secho("https://github.com/mrinimitable/mrinimitable/wiki/Migrating-to-Version-13", fg="yellow")
		print()
