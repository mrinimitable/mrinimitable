mrinimitable.ui.form.ControlCurrency = class ControlCurrency extends mrinimitable.ui.form.ControlFloat {
	get_precision() {
		// always round based on field precision or currency's precision
		// this method is also called in this.parse()
		if (typeof this.df.precision != "number" && !this.df.precision) {
			if (mrinimitable.boot.sysdefaults.currency_precision) {
				this.df.precision = mrinimitable.boot.sysdefaults.currency_precision;
			} else {
				this.df.precision = get_number_format_info(this.get_number_format()).precision;
			}
		}

		return this.df.precision;
	}
};
