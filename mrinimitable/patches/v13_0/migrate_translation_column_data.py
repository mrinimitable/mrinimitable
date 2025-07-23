import mrinimitable


def execute():
	mrinimitable.reload_doctype("Translation")
	mrinimitable.db.sql(
		"UPDATE `tabTranslation` SET `translated_text`=`target_name`, `source_text`=`source_name`, `contributed`=0"
	)
