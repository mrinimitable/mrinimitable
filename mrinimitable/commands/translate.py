import click

from mrinimitable.commands import get_site, pass_context
from mrinimitable.exceptions import SiteNotSpecifiedError
from mrinimitable.utils.shashi_helper import CliCtxObj


# translation
@click.command("build-message-files")
@pass_context
def build_message_files(context: CliCtxObj):
	"Build message files for translation"
	import mrinimitable.translate

	for site in context.sites:
		try:
			mrinimitable.init(site)
			mrinimitable.connect()
			mrinimitable.translate.rebuild_all_translation_files()
		finally:
			mrinimitable.destroy()
	if not context.sites:
		raise SiteNotSpecifiedError


@click.command("new-language")  # , help="Create lang-code.csv for given app")
@click.argument("lang_code")  # , help="Language code eg. en")
@click.argument("app")  # , help="App name eg. mrinimitable")
@pass_context
def new_language(context: CliCtxObj, lang_code, app):
	"""Create lang-code.csv for given app"""
	import mrinimitable.translate

	if not context.sites:
		raise Exception("--site is required")

	# init site
	mrinimitable.init(site=context.sites[0])
	mrinimitable.connect()
	mrinimitable.translate.write_translations_file(app, lang_code)

	print(f"File created at ./apps/{app}/{app}/translations/{lang_code}.csv")
	print("You will need to add the language in mrinimitable/geo/languages.csv, if you haven't done it already.")


@click.command("get-untranslated")
@click.option("--app", default="_ALL_APPS")
@click.argument("lang")
@click.argument("untranslated_file")
@click.option("--all", default=False, is_flag=True, help="Get all message strings")
@pass_context
def get_untranslated(context: CliCtxObj, lang, untranslated_file, app="_ALL_APPS", all=None):
	"Get untranslated strings for language"
	import mrinimitable.translate

	site = get_site(context)
	try:
		mrinimitable.init(site)
		mrinimitable.connect()
		mrinimitable.translate.get_untranslated(lang, untranslated_file, get_all=all, app=app)
	finally:
		mrinimitable.destroy()


@click.command("update-translations")
@click.option("--app", default="_ALL_APPS")
@click.argument("lang")
@click.argument("untranslated_file")
@click.argument("translated-file")
@pass_context
def update_translations(context: CliCtxObj, lang, untranslated_file, translated_file, app="_ALL_APPS"):
	"Update translated strings"
	import mrinimitable.translate

	site = get_site(context)
	try:
		mrinimitable.init(site)
		mrinimitable.connect()
		mrinimitable.translate.update_translations(lang, untranslated_file, translated_file, app=app)
	finally:
		mrinimitable.destroy()


@click.command("import-translations")
@click.argument("lang")
@click.argument("path")
@pass_context
def import_translations(context: CliCtxObj, lang, path):
	"Update translated strings"
	import mrinimitable.translate

	site = get_site(context)
	try:
		mrinimitable.init(site)
		mrinimitable.connect()
		mrinimitable.translate.import_translations(lang, path)
	finally:
		mrinimitable.destroy()


@click.command("migrate-translations")
@click.argument("source-app")
@click.argument("target-app")
@pass_context
def migrate_translations(context: CliCtxObj, source_app, target_app):
	"Migrate target-app-specific translations from source-app to target-app"
	import mrinimitable.translate

	site = get_site(context)
	try:
		mrinimitable.init(site)
		mrinimitable.connect()
		mrinimitable.translate.migrate_translations(source_app, target_app)
	finally:
		mrinimitable.destroy()


commands = [
	build_message_files,
	get_untranslated,
	import_translations,
	new_language,
	update_translations,
	migrate_translations,
]
