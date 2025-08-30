# Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import shutil

import mrinimitable
from mrinimitable import _, conf, get_module_path, safe_decode
from mrinimitable.build import html_to_js_template
from mrinimitable.core.doctype.custom_role.custom_role import get_custom_allowed_roles
from mrinimitable.desk.form.meta import get_code_files_via_hooks, get_js
from mrinimitable.desk.utils import validate_route_conflict
from mrinimitable.model.document import Document
from mrinimitable.model.utils import render_include


class Page(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from mrinimitable.core.doctype.has_role.has_role import HasRole
		from mrinimitable.types import DF

		icon: DF.Data | None
		module: DF.Link
		page_name: DF.Data
		restrict_to_domain: DF.Link | None
		roles: DF.Table[HasRole]
		standard: DF.Literal["Yes", "No"]
		system_page: DF.Check
		title: DF.Data | None
	# end: auto-generated types

	def autoname(self):
		"""
		Creates a url friendly name for this page.
		Will restrict the name to 30 characters, if there exists a similar name,
		it will add name-1, name-2 etc.
		"""
		from mrinimitable.utils import cint

		if (self.name and self.name.startswith("New Page")) or not self.name:
			self.name = self.page_name.lower().replace('"', "").replace("'", "").replace(" ", "-")[:20]
			if mrinimitable.db.exists("Page", self.name):
				cnt = mrinimitable.db.sql(
					"""select name from tabPage
					where name like "{}-%" order by name desc limit 1""".format(self.name)
				)
				if cnt:
					cnt = cint(cnt[0][0].split("-")[-1]) + 1
				else:
					cnt = 1
				self.name += "-" + str(cnt)

	def validate(self):
		validate_route_conflict(self.doctype, self.name)

		if self.is_new() and not getattr(conf, "developer_mode", 0):
			mrinimitable.throw(_("Not in Developer Mode"))

		# setting ignore_permissions via update_setup_wizard_access (setup_wizard.py)
		if mrinimitable.session.user != "Administrator" and not self.flags.ignore_permissions:
			mrinimitable.throw(_("Only Administrator can edit"))

	def get_permission_log_options(self, event=None):
		return {"fields": ["roles"]}

	# export
	def on_update(self):
		"""
		Writes the .json for this page and if write_content is checked,
		it will write out a .html file
		"""
		if self.flags.do_not_update_json:
			return

		from mrinimitable.core.doctype.doctype.doctype import make_module_and_roles

		make_module_and_roles(self, "roles")

		from mrinimitable.modules.utils import export_module_json

		path = export_module_json(self, self.standard == "Yes", self.module)

		if path:
			# js
			if not os.path.exists(path + ".js"):
				with open(path + ".js", "w") as f:
					f.write(
						f"""mrinimitable.pages['{self.name}'].on_page_load = function(wrapper) {{
	var page = mrinimitable.ui.make_app_page({{
		parent: wrapper,
		title: '{self.title}',
		single_column: true
	}});
}}"""
					)

	def as_dict(self, **kwargs):
		d = super().as_dict(**kwargs)
		for key in ("script", "style", "content"):
			d[key] = self.get(key)
		return d

	def on_trash(self):
		if not mrinimitable.conf.developer_mode and not mrinimitable.flags.in_migrate:
			mrinimitable.throw(_("Deletion of this document is only permitted in developer mode."))

		delete_custom_role("page", self.name)
		mrinimitable.db.after_commit(self.delete_folder_with_contents)

	def delete_folder_with_contents(self):
		module_path = get_module_path(self.module)
		dir_path = os.path.join(module_path, "page", mrinimitable.scrub(self.name))

		if os.path.exists(dir_path):
			shutil.rmtree(dir_path, ignore_errors=True)

	def is_permitted(self):
		"""Return True if `Has Role` is not set or the user is allowed."""
		from mrinimitable.utils import has_common

		allowed = [d.role for d in mrinimitable.get_all("Has Role", fields=["role"], filters={"parent": self.name})]

		custom_roles = get_custom_allowed_roles("page", self.name)
		allowed.extend(custom_roles)

		if not allowed:
			return True

		roles = mrinimitable.get_roles()

		if has_common(roles, allowed):
			return True

	def load_assets(self):
		import os

		from mrinimitable.modules import get_module_path, scrub

		self.script = ""

		page_name = scrub(self.name)

		path = os.path.join(get_module_path(self.module), "page", page_name)

		# script
		fpath = os.path.join(path, page_name + ".js")
		if os.path.exists(fpath):
			with open(fpath) as f:
				self.script = render_include(f.read())
				self.script += f"\n\n//# sourceURL={page_name}.js"

		# css
		fpath = os.path.join(path, page_name + ".css")
		if os.path.exists(fpath):
			with open(fpath) as f:
				self.style = safe_decode(f.read())

		# html as js template
		for fname in os.listdir(path):
			if fname.endswith(".html"):
				with open(os.path.join(path, fname)) as f:
					template = f.read()
					if "<!-- jinja -->" in template:
						context = mrinimitable._dict({})
						try:
							out = mrinimitable.get_attr(
								"{app}.{module}.page.{page}.{page}.get_context".format(
									app=mrinimitable.local.module_app[scrub(self.module)],
									module=scrub(self.module),
									page=page_name,
								)
							)(context)

							if out:
								context = out
						except (AttributeError, ImportError):
							pass

						template = mrinimitable.render_template(template, context)
					self.script = html_to_js_template(fname, template) + self.script

					# flag for not caching this page
					self._dynamic_page = True

		for path in get_code_files_via_hooks("page_js", self.name):
			js = get_js(path)
			if js:
				self.script += "\n\n" + js


def delete_custom_role(field, docname):
	name = mrinimitable.db.get_value("Custom Role", {field: docname}, "name")
	if name:
		mrinimitable.delete_doc("Custom Role", name)
