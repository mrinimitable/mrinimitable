#!/bin/env python3

import importlib
import json
import os
import sys
import traceback
import warnings
from dataclasses import dataclass
from textwrap import dedent

import click

import mrinimitable
import mrinimitable.utils

click.disable_unicode_literals_warning = True


def MrinimitableClickWrapper(cls, handler):
	class Cls(cls):
		# only implemented on groups
		def get_command(self, ctx, cmd_name):
			rv = super().get_command(ctx, cmd_name)
			if rv is not None:
				return rv

			all_commands = self.list_commands(ctx)
			from difflib import get_close_matches

			possibilities = get_close_matches(cmd_name, all_commands)
			raise click.NoSuchOption(
				cmd_name, possibilities=possibilities, message=f"No such command: {cmd_name}."
			)

		def make_context(self, info_name, args, parent=None, **extra):
			try:
				return super().make_context(info_name, args, parent=parent, **extra)
			except (click.ClickException, click.exceptions.Exit, click.exceptions.Abort) as e:
				raise e
			except Exception as exc:
				# call the handler
				handler(self, info_name, exc)
				sys.exit(1)

		def invoke(self, ctx):
			try:
				return super().invoke(ctx)
			except (click.ClickException, click.exceptions.Exit, click.exceptions.Abort) as e:
				raise e
			except Exception as exc:
				# call the handler
				handler(self, ctx.info_name, exc)
				sys.exit(1)

	return Cls


# for type hints
@dataclass
class CliCtxObj:
	sites: list[str]
	force: bool
	profile: bool
	verbose: bool


def handle_exception(cmd, info_name, exc):
	click.echo(traceback.format_exc())

	click.echo(exc)


def main():
	commands = get_app_groups()
	commands.update({"get-mrinimitable-commands": get_mrinimitable_commands, "get-mrinimitable-help": get_mrinimitable_help})
	MrinimitableClickWrapper(click.Group, handle_exception)(commands=commands)(prog_name="shashi")


def get_app_groups() -> dict[str, click.Group | click.Command]:
	"""Get all app groups, put them in main group "mrinimitable" since shashi is
	designed to only handle that"""
	commands = {}
	for app in get_apps():
		if app_commands := get_app_commands(app):
			commands |= app_commands
	return dict(
		mrinimitable=click.group(
			name="mrinimitable", commands=commands, cls=MrinimitableClickWrapper(click.Group, handle_exception)
		)(app_group)
	)


def get_app_group(app: str) -> click.Group:
	if app_commands := get_app_commands(app):
		return click.group(
			name=app, commands=app_commands, cls=MrinimitableClickWrapper(click.Group, handle_exception)
		)(app_group)


@click.option("--site")
@click.option("--profile", is_flag=True, default=False, help="Profile")
@click.option("--verbose", is_flag=True, default=False, help="Verbose")
@click.option("--force", is_flag=True, default=False, help="Force")
@click.pass_context
def app_group(ctx, site=False, force=False, verbose=False, profile=False):
	ctx.obj = CliCtxObj(sites=get_sites(site), force=force, verbose=verbose, profile=profile)
	if ctx.info_name == "mrinimitable":
		ctx.info_name = ""


def get_sites(site_arg: str) -> list[str]:
	if site_arg == "all":
		return mrinimitable.utils.get_sites()
	elif site_arg:
		return [site_arg]
	elif env_site := os.environ.get("MRINIMITABLE_SITE"):
		return [env_site]
	elif default_site := mrinimitable.get_conf().default_site:
		return [default_site]
	# This is not supported, just added here for warning.
	elif (site := mrinimitable.read_file("currentsite.txt")) and site.strip():
		click.secho(
			dedent(
				f"""
			WARNING: currentsite.txt is not supported anymore for setting default site. Use following command to set it as default site.
			$ shashi use {site}"""
			),
			fg="red",
		)

	return []


def get_app_commands(app: str) -> dict:
	ret = {}
	try:
		app_command_module = importlib.import_module(f"{app}.commands")
	except ModuleNotFoundError as e:
		if e.name == f"{app}.commands":
			return ret
		traceback.print_exc()
		return ret
	except Exception:
		traceback.print_exc()
		return ret
	for command in getattr(app_command_module, "commands", []):
		ret[command.name] = command
	return ret


@click.command("get-mrinimitable-commands")
def get_mrinimitable_commands():
	commands = list(get_app_commands("mrinimitable"))

	for app in get_apps():
		app_commands = get_app_commands(app)
		if app_commands:
			commands.extend(list(app_commands))

	print(json.dumps(commands))


@click.command("get-mrinimitable-help")
def get_mrinimitable_help():
	print(click.Context(get_app_groups()["mrinimitable"]).get_help())


def get_apps():
	return mrinimitable.get_all_apps(with_internal_apps=False, sites_path=".")


if __name__ == "__main__":
	if not mrinimitable._dev_server:
		warnings.simplefilter("ignore")

	main()
