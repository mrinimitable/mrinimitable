// Copyright (c) 2015, Mrinimitable Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

mrinimitable.ready(function() {

	if(mrinimitable.utils.get_url_arg('subject')) {
	  $('[name="subject"]').val(mrinimitable.utils.get_url_arg('subject'));
	}

	$('.btn-send').off("click").on("click", function() {
		var email = $('[name="email"]').val();
		var message = $('[name="message"]').val();

		if(!(email && message)) {
			mrinimitable.msgprint('{{ _("Please enter both your email and message so that we can get back to you. Thanks!") }}');
			return false;
		}

		if(!validate_email(email)) {
			mrinimitable.msgprint('{{ _("You seem to have written your name instead of your email. Please enter a valid email address so that we can get back.") }}');
			$('[name="email"]').focus();
			return false;
		}

		$("#contact-alert").toggle(false);
		mrinimitable.call({
			type: "POST",
			method: "mrinimitable.www.contact.send_message",
			args: {
				subject: $('[name="subject"]').val(),
				sender: email,
				message: message,
			},
			callback: function(r) {
				if (!r.exc) {
					mrinimitable.msgprint('{{ _("Thank you for your message") }}', '{{ _("Message Sent") }}');
				}
				$(':input').val('');
			},
		});
	});
});

var msgprint = function(txt) {
	if(txt) $("#contact-alert").html(txt).toggle(true);
}
