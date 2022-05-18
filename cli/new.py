import collections
import pathlib
import typing

import click

from cli.callbacks import mapped_callback, plain_callback
from cli.validation import (
    parse_ticket_status,
    parse_ticket_work_type,
    relativize_group,
    ticket_relationship_choice,
    ticket_status_choice,
    ticket_work_type_choice,
    validate_ticket_relationship,
)
from gira import ticket


def validate_new_ticket_number(
    context: click.Context, parameter: click.Parameter, value: typing.Optional[int]
) -> int:
    """Validate a user-input ticket number, for ticket creation

    Raises:
        click.BadParameter: If a ticket with that number already exists
    """
    ticket_store = context.obj

    # If no ticket number is specified, assign the next available one
    if value is None:
        return ticket_store.next_ticket_number

    try:
        ticket_path = ticket_store.ticket_path_components_by_number[value]
        raise click.BadParameter(
            message=f"Ticket #{value} already exists: {ticket_path}.",
        )
    # A `KeyError` indicates that the ticket isn't in the ticket store, so it's
    # OK to use
    except KeyError:
        return value


@plain_callback
def add_terminal_newline_to_description(
    value: typing.Optional[str],
) -> typing.Optional[str]:
    """Add a newline to the end of a ticket description

    Required because one isn't added by default for prompted values
    """
    if value:
        return f"{value}\n"
    else:
        return value


@mapped_callback
def validate_ticket_relationship_creation(
    context: click.Context,
    parameter: click.Parameter,
    value: tuple[int, str, str],
) -> tuple[int, ticket.TicketRelationship, str]:
    """Ensure a ticket relationship points to an actual ticket

    Also extract the proper relationship enum member

    Raises:
        click.BadParameter: If the ticket doesn't exist
    """
    raw_ticket_number, raw_relationship, label = value

    ticket_number, relationship = validate_ticket_relationship(
        context, parameter, (raw_ticket_number, raw_relationship)
    )

    return ticket_number, relationship, label


@click.command()
@click.option("-t", "--title", help="A title to assign the ticket.")
@click.option(
    "-d",
    "--description",
    prompt=True,
    prompt_required=False,
    callback=add_terminal_newline_to_description,
    help="A description to provide to the ticket.",
)
@click.option(
    "-s",
    "--status",
    type=ticket_status_choice,
    default=ticket.TicketStatus.TODO.name,
    show_default=True,
    callback=parse_ticket_status,
    help="The status to assign to the ticket.",
)
@click.option(
    "-w",
    "--work-type",
    type=ticket_work_type_choice,
    default=ticket.TicketWorkType.FEATURE.name,
    show_default=True,
    callback=parse_ticket_work_type,
    help="The work_type to assign to the ticket.",
)
@click.option(
    "-g",
    "--group",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    default=None,
    show_default=False,
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
@click.option(
    "-r",
    "--relationship",
    "relationships",
    multiple=True,
    type=(int, ticket_relationship_choice, str),
    callback=validate_ticket_relationship_creation,
    help="A relationship to give the ticket.",
)
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
def new(
    ticket_store: ticket.TicketStore,
    title: str,
    description: str,
    status: ticket.TicketStatus,
    work_type: ticket.TicketWorkType,
    group: pathlib.Path,
    slug: str,
    number: int,
    relationships: list[tuple[int, ticket.TicketRelationship, str]],
    edit: bool,
    echo_path: bool,
):
    """Create a new ticket."""
    relationship_map: dict[
        ticket.TicketRelationship, dict[int, str]
    ] = collections.defaultdict(dict)
    for target_ticket_number, relationship, label in relationships:
        relationship_map[relationship][target_ticket_number] = label

    new_ticket = ticket.Ticket(
        number=number,
        to_slug=slug or title,
        group=group,
        status=status,
        work_type=work_type,
        title=title,
        description=description,
        relationships=relationship_map,
    )

    full_ticket_path = ticket_store.tickets_dir / new_ticket.path

    # Create the ticket storage directory; noop if it already exists
    full_ticket_path.parent.mkdir(parents=True, exist_ok=True)

    # Error out if the file already exists
    with full_ticket_path.open(mode="x") as new_ticket_file:
        new_ticket_file.write(new_ticket.document)

    # Optionally echo the path to the ticket
    if echo_path:
        click.echo(full_ticket_path)

    # Optionally open the file
    if edit:
        click.edit(filename=str(full_ticket_path))
