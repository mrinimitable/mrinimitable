// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.provide("mrinimitable.help");

mrinimitable.help.youtube_id = {};

mrinimitable.help.has_help = function (doctype) {
	return mrinimitable.help.youtube_id[doctype];
};

mrinimitable.help.show = function (doctype) {
	if (mrinimitable.help.youtube_id[doctype]) {
		mrinimitable.help.show_video(mrinimitable.help.youtube_id[doctype]);
	}
};

mrinimitable.help.show_video = function (youtube_id, title) {
	if (mrinimitable.utils.is_url(youtube_id)) {
		const expression =
			'(?:youtube.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu.be/)([^"&?\\s]{11})';
		youtube_id = youtube_id.match(expression)[1];
	}

	// (mrinimitable.help_feedback_link || "")
	let dialog = new mrinimitable.ui.Dialog({
		title: title || __("Help"),
		size: "large",
	});

	let video = $(
		`<div class="video-player" data-plyr-provider="youtube" data-plyr-embed-id="${youtube_id}"></div>`
	);
	video.appendTo(dialog.body);

	dialog.show();
	dialog.$wrapper.addClass("video-modal");

	let plyr;
	mrinimitable.utils.load_video_player().then(() => {
		plyr = new mrinimitable.Plyr(video[0], {
			hideControls: true,
			resetOnEnd: true,
		});
	});

	dialog.onhide = () => {
		plyr?.destroy();
	};
};

$("body").on("click", "a.help-link", function () {
	var doctype = $(this).attr("data-doctype");
	doctype && mrinimitable.help.show(doctype);
});
