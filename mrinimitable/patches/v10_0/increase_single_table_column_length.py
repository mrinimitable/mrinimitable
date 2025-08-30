"""
Run this after updating country_info.json and or
"""

import mrinimitable


def execute():
	for col in ("field", "doctype"):
		mrinimitable.db.sql_ddl(f"alter table `tabSingles` modify column `{col}` varchar(255)")
