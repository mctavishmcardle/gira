import pathlib
import typing

import click
import slugify
import tabulate

from gira import ticket


@click.group(help="A barebones ticketing system for `git`")
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
    context.obj = ticket.TicketStore(tickets_dir)


def validate_new_ticket_number(
    context: click.Context, parameter: click.Parameter, value: typing.Optional[int]
) -> int:
    """Validate a user-input ticket number, for ticket creation"""
    tickets_by_number = context.obj.tickets_by_number

    # If no ticket number is specified, assign the next available one
    if value is None:
        # Default to -1 if there are no tickets, so the first ticket is #0
        value = max(tickets_by_number.keys(), default=-1) + 1
    # If the ticket number is already in use, error out
    elif value in tickets_by_number.keys():
        ticket = tickets_by_number[value]

        raise click.BadParameter(
            message=f"Ticket numbers must be unique; ticket #{value} already exists: {ticket}.",
            ctx=context,
        )

    return value


def parse_ticket_status(
    context: click.Context, parameter: click.Parameter, value: str
) -> ticket.TicketStatus:
    """Parse the ticket status choice into a proper enum member"""
    return ticket.TicketStatus[value]


ticket_status_choice = click.Choice(
    [status.name for status in ticket.TicketStatus], case_sensitive=False
)


def add_terminal_newline_to_description(
    context: click.Context, parameter: click.Parameter, value: typing.Optional[str]
) -> str:
    """Add a newline to the end of a ticket description

    Required because one isn't added by default for prompted values
    """
    if value:
        return f"{value}\n"
    else:
        return value


def relativize_group(
    context: click.Context,
    parameter: click.Parameter,
    value: typing.Optional[pathlib.Path],
) -> str:
    """Ensure a group is relative to the ticket dir"""
    if value:
        try:
            return value.relative_to(context.obj.tickets_dir)
        # A value error indicates that the group isn't in the subpath of the
        # ticket dir - treat it as relative already
        except ValueError:
            return value
    else:
        return value


@cli.command(help="Create a new ticket.")
@click.option(
    "-n",
    "--number",
    type=int,
    callback=validate_new_ticket_number,
    help="A ticket number to assign. If not specified, one will be chosen automatically.",
)
@click.option(
    "-s",
    "--slug",
    help="A slugifiable string to label the ticket file with. If a title is specified but a slug is not, the slug will be generated from by title",
)
@click.option("-t", "--title", help="A title to assign the ticket.")
@click.option(
    "-d",
    "--description",
    prompt=True,
    prompt_required=False,
    callback=add_terminal_newline_to_description,
    help="A description to provide to the ticket",
)
@click.option(
    "-u",
    "--status",
    type=ticket_status_choice,
    default=ticket.TicketStatus.TODO.name,
    show_default=True,
    callback=parse_ticket_status,
    help="The status to assign to the ticket.",
)
@click.option(
    "-g",
    "--group",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    default=None,
    show_default=False,
    callback=relativize_group,
    help="The group in which to place the ticket",
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
    number: int,
    slug: str,
    title: str,
    description: str,
    status: ticket.TicketStatus,
    group: pathlib.Path,
    edit: bool,
    echo_path: bool,
):
    new_ticket = ticket.Ticket(
        number=number,
        to_slug=slug or title,
        group=group,
        status=status,
        title=title,
        description=description,
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
        click.edit(filename=full_ticket_path)


@cli.command(name="list", help="List existing tickets.")
@click.pass_obj
def list_tickets(ticket_store: ticket.TicketStore):
    click.echo(
        tabulate.tabulate(
            (
                (
                    ticket.number,
                    ticket.status.name if ticket.status else ticket.status,
                    ticket.title,
                    ticket.group,
                    ticket.full_slug,
                )
                for ticket in ticket_store.all_tickets
            ),
            tablefmt="plain",
        )
    )
