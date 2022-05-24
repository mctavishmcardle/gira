import pathlib
import typing

import click

from cli.git import checkout_ticket
from cli.new import new_ticket
from cli.search import search_tickets
from gira import ticket_store


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
    context.obj = ticket_store.TicketStore(tickets_dir)


cli.add_command(new_ticket)
cli.add_command(search_tickets)
cli.add_command(checkout_ticket)
