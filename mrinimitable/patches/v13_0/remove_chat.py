import click

import mrinimitable


def execute():
	mrinimitable.delete_doc_if_exists("DocType", "Chat Message")
	mrinimitable.delete_doc_if_exists("DocType", "Chat Message Attachment")
	mrinimitable.delete_doc_if_exists("DocType", "Chat Profile")
	mrinimitable.delete_doc_if_exists("DocType", "Chat Token")
	mrinimitable.delete_doc_if_exists("DocType", "Chat Room User")
	mrinimitable.delete_doc_if_exists("DocType", "Chat Room")
	mrinimitable.delete_doc_if_exists("Module Def", "Chat")

	click.secho(
		"Chat Module is moved to a separate app and is removed from Mrinimitable in version-13.\n"
		"Please install the app to continue using the chat feature: https://github.com/mrinimitable/chat",
		fg="yellow",
	)
