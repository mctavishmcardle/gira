import collections
import pathlib
import typing

import click

from cli.callbacks import compose_callbacks, mapped_callback, plain_callback
from cli.validation import (
    add_terminal_newline_to_description,
    parse_ticket_status,
    parse_ticket_work_type,
    relativize_group,
    ticket_relationship_choice,
    ticket_status_choice,
    ticket_work_type_choice,
    validate_ticket_relationship_creation,
)
from gira import ticket, ticket_properties, ticket_store


def validate_new_ticket_number(
    context: click.Context, parameter: click.Parameter, value: typing.Optional[int]
) -> int:
    """Validate a user-input ticket number, for ticket creation

    Raises:
        click.BadParameter: If a ticket with that number already exists
    """
    store = context.obj

    # If no ticket number is specified, assign the next available one
    if value is None:
        return store.next_ticket_number

    try:
        ticket_path = store.ticket_path_components_by_number[value]
        raise click.BadParameter(
            message=f"Ticket #{value} already exists: {ticket_path}.",
        )
    # A `KeyError` indicates that the ticket isn't in the ticket store, so it's
    # OK to use
    except KeyError:
        return value


new_ticket_relationships = click.option(
    "-r",
    "--relationship",
    "relationships",
    multiple=True,
    type=(int, ticket_relationship_choice, str),
    callback=validate_ticket_relationship_creation,
    help="A relationship to give the ticket.",
)


@click.command(name="new")
@click.option("-t", "--title", help="A title to assign the ticket.")
@click.option(
    "-d",
    "--description",
    prompt=True,
    prompt_required=False,
    callback=add_terminal_newline_to_description,
    help="A description to assign to the ticket.",
)
@click.option(
    "-s",
    "--status",
    type=ticket_status_choice,
    default=ticket_properties.TicketStatus.TODO.name,
    show_default=True,
    callback=parse_ticket_status,
    help="The status to assign to the ticket.",
)
@click.option(
    "-w",
    "--work-type",
    type=ticket_work_type_choice,
    default=ticket_properties.TicketWorkType.FEATURE.name,
    show_default=True,
    callback=parse_ticket_work_type,
    help="The work type to assign to the ticket.",
)
@click.option(
    "-g",
    "--group",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    callback=relativize_group,
    help="The group in which to place the ticket.",
)
@click.option(
    "-l",
    "--slug",
    help="A slugifiable string to label the ticket file with. If a title is specified but a slug is not, the slug will be generated from by title.",
)
@click.option(
    "-n",
    "--number",
    type=int,
    callback=validate_new_ticket_number,
    help="A ticket number to assign. If not specified, one will be chosen automatically.",
)
@new_ticket_relationships
@click.option(
    "-e/-E",
    "--edit/--no-edit",
    default=False,
    show_default=True,
    help="Edit the ticket file after creation?",
)
@click.option(
    "-p/-P",
    "--echo-path/--no-echo-path",
    default=False,
    show_default=True,
    help="Echo the path to the newly-created ticket?",
)
@click.pass_obj
def new_ticket(
    store: ticket_store.TicketStore,
    title: typing.Optional[str],
    description: typing.Optional[str],
    status: ticket_properties.TicketStatus,
    work_type: ticket_properties.TicketWorkType,
    group: typing.Optional[pathlib.Path],
    slug: typing.Optional[str],
    number: int,
    relationships: ticket.RelationshipMap,
    edit: bool,
    echo_path: bool,
):
    """Create a new ticket."""

    new_ticket = ticket.Ticket(
        number=number,
        to_slug=slug or title,
        group=group,
        status=status,
        work_type=work_type,
        title=title,
        description=description,
        relationships=relationships,
    )

    relative_ticket_path = store.relative_ticket_path(new_ticket)

    # Create the ticket storage directory; noop if it already exists
    relative_ticket_path.parent.mkdir(parents=True, exist_ok=True)

    # Error out if the file already exists
    with relative_ticket_path.open(mode="x") as new_ticket_file:
        new_ticket_file.write(new_ticket.document)

    # Optionally echo the path to the ticket
    if echo_path:
        click.echo(relative_ticket_path)

    # Optionally open the file
    if edit:
        click.edit(filename=str(relative_ticket_path))
