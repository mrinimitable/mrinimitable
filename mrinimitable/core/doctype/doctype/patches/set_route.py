import mrinimitable
from mrinimitable.desk.utils import slug


def execute():
	for doctype in mrinimitable.get_all("DocType", ["name", "route"], dict(istable=0)):
		if not doctype.route:
			mrinimitable.db.set_value("DocType", doctype.name, "route", slug(doctype.name), update_modified=False)
