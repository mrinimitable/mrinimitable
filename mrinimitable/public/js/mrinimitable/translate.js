// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for translation
mrinimitable._ = function (txt, replace, context = null) {
	if (!txt) return txt;
	if (typeof txt != "string") return txt;

	let translated_text = "";

	let key = txt; // txt.replace(/\n/g, "");
	if (context) {
		translated_text = mrinimitable._messages[`${key}:${context}`];
	}

	if (!translated_text) {
		translated_text = mrinimitable._messages[key] || txt;
	}

	if (replace && typeof replace === "object") {
		translated_text = $.format(translated_text, replace);
	}
	return translated_text;
};

window.__ = mrinimitable._;

mrinimitable.get_languages = function () {
	if (!mrinimitable.languages) {
		mrinimitable.languages = [];
		$.each(mrinimitable.boot.lang_dict, function (lang, value) {
			mrinimitable.languages.push({ label: lang, value: value });
		});
		mrinimitable.languages = mrinimitable.languages.sort(function (a, b) {
			return a.value < b.value ? -1 : 1;
		});
	}
	return mrinimitable.languages;
};
