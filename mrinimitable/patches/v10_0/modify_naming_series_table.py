"""
Modify the Integer 10 Digits Value to BigInt 20 Digit value
to generate long Naming Series

"""

import mrinimitable


def execute():
	mrinimitable.db.sql(""" ALTER TABLE `tabSeries` MODIFY current BIGINT """)
