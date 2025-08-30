# update app in `Module Def` and `Workspace`

import mrinimitable
from mrinimitable.modules.utils import get_module_app


def execute():
	for module in mrinimitable.get_all("Module Def", ["name", "app_name"], filters=dict(custom=0)):
		if not module.app_name:
			try:
				mrinimitable.db.set_value("Module Def", module.name, "app_name", get_module_app(module.name))
			except Exception:
				# for some default modules like Home, there is no folder / app
				pass

	for workspace in mrinimitable.get_all("Workspace", ["name", "module", "app"]):
		if not workspace.app and workspace.module:
			mrinimitable.db.set_value(
				"Workspace",
				workspace.name,
				"app",
				mrinimitable.db.get_value("Module Def", workspace.module, "app_name"),
			)
