mrinimitable.ui.form.ControlFloat = class ControlFloat extends mrinimitable.ui.form.ControlInt {
	parse(value) {
		value = this.eval_expression(value);
		return isNaN(parseFloat(value)) ? null : flt(value, this.get_precision());
	}

	format_for_input(value) {
		if (value === null || value === undefined || isNaN(Number(value))) {
			return "";
		}

		return format_number(value, this.get_number_format(), this.get_precision());
	}

	get_number_format() {
		if (this.df.fieldtype === "Float" && !this.df.options?.trim()) return;

		const currency = mrinimitable.meta.get_field_currency(this.df, this.get_doc());
		return get_number_format(currency);
	}

	get_precision() {
		// round based on field precision or float precision, else don't round
		return this.df.precision || cint(mrinimitable.boot.sysdefaults.float_precision, null);
	}
};

mrinimitable.ui.form.ControlPercent = mrinimitable.ui.form.ControlFloat;
