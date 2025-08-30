import mrinimitable
from mrinimitable.query_builder import DocType


def execute():
	RATING_FIELD_TYPE = "decimal(3,2)"
	rating_fields = mrinimitable.get_all(
		"DocField", fields=["parent", "fieldname"], filters={"fieldtype": "Rating"}
	)

	custom_rating_fields = mrinimitable.get_all(
		"Custom Field", fields=["dt", "fieldname"], filters={"fieldtype": "Rating"}
	)

	for _field in rating_fields + custom_rating_fields:
		doctype_name = _field.get("parent") or _field.get("dt")
		doctype = DocType(doctype_name)
		field = _field.fieldname

		# TODO: Add postgres support (for the check)
		if (
			mrinimitable.conf.db_type == "mariadb"
			and mrinimitable.db.get_column_type(doctype_name, field) == RATING_FIELD_TYPE
		):
			continue

		# commit any changes so far for upcoming DDL
		mrinimitable.db.commit()

		# alter column types for rating fieldtype
		mrinimitable.db.change_column_type(doctype_name, column=field, type=RATING_FIELD_TYPE, nullable=True)

		# update data: int => decimal
		mrinimitable.qb.update(doctype).set(doctype[field], doctype[field] / 5).run()

		# commit to flush updated rows
		mrinimitable.db.commit()
