import pathlib
import typing

import click

from cli.new import new
from cli.search import search
from gira import ticket


@click.group()
@click.option(
    "-d",
    "--tickets-dir",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    default=None,
    show_default=False,
    help="The directory in which ticket files should be, or are, stored. If not specified, the default, repo-specific location will be used.",
)
@click.pass_context
def cli(context: click.Context, tickets_dir: typing.Optional[pathlib.Path]):
    """A barebones ticketing system for `git`"""
    context.obj = ticket.TicketStore(tickets_dir)


cli.add_command(new)
cli.add_command(search)
