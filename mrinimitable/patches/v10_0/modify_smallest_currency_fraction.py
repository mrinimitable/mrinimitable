# Copyright (c) 2018, Mrinimitable Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import mrinimitable


def execute():
	mrinimitable.db.set_value("Currency", "USD", "smallest_currency_fraction_value", "0.01")
