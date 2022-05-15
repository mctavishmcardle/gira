import collections
import functools
import pathlib
import re
import typing

import click
import slugify
import tabulate

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


# The input parameter value
V = typing.TypeVar("V")
# The output parameter value
O = typing.TypeVar("O")
GenericClickCallback = collections.abc.Callable[[click.Context, click.Parameter, V], O]


def plain_callback(callback: collections.abc.Callable[[V], O]) -> GenericClickCallback:
    """Wrap a function so it has the correct signature for a `click` callback

    If the input callable doesn't need access to the ocntext or the parameter,
    this is more straightforward & flexible than defining a function that takes
    all of the inputs & ignores all but the parameter value.

    Args:
        callback: The function to wrap
    """
    return functools.wraps(callback)(lambda context, parameter, value: callback(value))


@plain_callback
def parse_ticket_status(value: str) -> ticket.TicketStatus:
    """Parse the ticket status choice into a proper enum member"""
    return ticket.TicketStatus[value]


ticket_status_choice = click.Choice(
    [status.name for status in ticket.TicketStatus], case_sensitive=False
)


@plain_callback
def add_terminal_newline_to_description(value: typing.Optional[str]) -> str:
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


@cli.command()
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
    "-s",
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
    "-l",
    "--slug",
    help="A slugifiable string to label the ticket file with. If a title is specified but a slug is not, the slug will be generated from by title",
)
@click.option(
    "-n",
    "--number",
    type=int,
    callback=validate_new_ticket_number,
    help="A ticket number to assign. If not specified, one will be chosen automatically.",
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
    group: pathlib.Path,
    slug: str,
    number: int,
    edit: bool,
    echo_path: bool,
):
    """Create a new ticket."""
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


def mapped_callback(
    callback: GenericClickCallback,
    condition: collections.abc.Callable[[V], bool] = lambda value: True,
) -> collections.abc.Callable[[click.Context, click.Parameter, list[V]], list[O]]:
    """Maps a single-value `click` callback to multiple values

    Args:
        callback: The callback to wrap
        condition: An optional test to apply to the input value list, to exclude
            elements whose return-value is falsy
    """
    return functools.wraps(callback)(
        lambda context, parameter, values: [
            callback(context, parameter, value) for value in values if condition(value)
        ]
    )


ticket_exclude_status_remove_default = "!"
ticket_exclude_status_choice = click.Choice(
    ticket_status_choice.choices + [ticket_exclude_status_remove_default],
    case_sensitive=False,
)

# Partials to reduce redundancy in setting up the search options
search_option = functools.partial(click.option, multiple=True)
search_number = functools.partial(search_option, type=int)
search_group = functools.partial(
    search_option,
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    callback=mapped_callback(relativize_group),
)
search_regex = functools.partial(
    search_option,
    callback=mapped_callback(plain_callback(re.compile)),
)


@cli.group(invoke_without_command=True)
@search_number(
    "-n",
    "--number",
    "numbers",
    help="Show tickets with these numbers",
)
@search_number(
    "-N",
    "--exclude_number",
    "exclude_numbers",
    help="Exclude tickets with these numbers",
)
@search_group(
    "-g",
    "--group",
    "groups",
    help="Show tickets in these groups.",
)
@search_group(
    "-G",
    "--exclude-group",
    "exclude_groups",
    help="Exclude tickets in these groups.",
)
@search_option(
    "-s",
    "--status",
    "statuses",
    type=ticket_status_choice,
    callback=mapped_callback(parse_ticket_status),
    help="Show tickets with one of these statuses.",
)
@search_option(
    "-S",
    "--exclude-status",
    "exclude_statuses",
    type=ticket_exclude_status_choice,
    default=[ticket.TicketStatus.DONE.name],
    show_default=True,
    callback=mapped_callback(
        parse_ticket_status, lambda value: value != ticket_exclude_status_remove_default
    ),
    help=(
        "Filter out tickets with one of these statuses. "
        f"Pass `{ticket_exclude_status_remove_default}` to bypass the default exclusion."
    ),
)
@search_regex(
    "-t", "--title", "titles", help="Show tickets whose titles match this pattern."
)
@search_regex(
    "-T",
    "--exclude-title",
    "exclude_titles",
    help="Exclude tickets whose titles match this pattern.",
)
@search_regex(
    "-d",
    "--description",
    "descriptions",
    help="Show tickets whose descriptions match this pattern.",
)
@search_regex(
    "-D",
    "--exclude-description",
    "exclude_descriptions",
    help="Exclude tickets whose descriptions match this pattern.",
)
@search_regex(
    "-l",
    "--slug",
    "slugs",
    help="Show tickets whose slugs match this pattern.",
)
@search_regex(
    "-L",
    "--exclude-slug",
    "exclude_slugs",
    help="Exclude tickets whose slugs match this pattern.",
)
@click.pass_obj
@click.pass_context
def search(
    context: click.Context,
    ticket_store: ticket.TicketStore,
    numbers: list[int],
    exclude_numbers: list[int],
    groups: list[pathlib.Path],
    exclude_groups: list[pathlib.Path],
    statuses: list[ticket.TicketStatus],
    exclude_statuses: list[ticket.TicketStatus],
    titles: list[re.Pattern],
    exclude_titles: list[re.Pattern],
    descriptions: list[re.Pattern],
    exclude_descriptions: list[re.Pattern],
    slugs: list[re.Pattern],
    exclude_slugs: list[re.Pattern],
):
    """Search for tickets.

    Multiple instances of the same option are OR'd together, and multiple
    different options are AND'd together.

    If no subcommand is invoked, this will output the relative paths to all the
    matched tickets.
    """
    ticket_store.set_search_conditions(
        ticket.SearchConditions(
            numbers,
            exclude_numbers,
            groups,
            exclude_groups,
            statuses,
            exclude_statuses,
            titles,
            exclude_titles,
            descriptions,
            exclude_descriptions,
            slugs,
            exclude_slugs,
        )
    )

    # Default to echoing relative paths
    if context.invoked_subcommand is None:
        for found_ticket in ticket_store.filtered_tickets:
            click.echo(found_ticket.relative_path(ticket_store.tickets_dir))


@search.command(name="list")
@click.pass_obj
def list_tickets(ticket_store: ticket.TicketStore):
    """List matching tickets."""
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
                for ticket in ticket_store.filtered_tickets
            ),
            tablefmt="plain",
        )
    )


def handle_page_on_single_tickets(
    context: click.Context, parameter: click.Parameter, value: bool
) -> bool:
    """Page on single tickets only if requested"""
    if len(context.obj.filtered_tickets) == 1:
        return (
            value
            and not context.get_parameter_source("pager")
            == click.core.ParameterSource.DEFAULT
        )
    else:
        return value


@search.command()
@click.option(
    "-p/-P",
    "--pager/--no-pager",
    default=True,
    callback=handle_page_on_single_tickets,
    help="Use a pager if there are multiple tickets?",
)
@click.pass_obj
def show(ticket_store: ticket.TicketStore, pager: bool):
    """Display matching tickets."""
    documents = (ticket.document for ticket in ticket_store.filtered_tickets)
    if pager:
        click.echo_via_pager(documents)
    else:
        for document in documents:
            click.echo(document)


def handle_multiple_found_tickets(
    context: click.Context, parameter: click.Parameter, value: bool
) -> bool:
    """Errors out if found ticket count conflicts with acceptable ticket count

    `value` should be a bool indicating whether more than one ticket is acceptable
    """
    if value and len(context.obj.filtered_tickets) > 1:
        raise click.BadParameter("Multiple tickets matched the search criteria")

    return value


check_single_found_ticket = click.option(
    "-o/-O",
    "--one/--many",
    default=True,
    show_default=True,
    callback=handle_multiple_found_tickets,
    expose_value=False,
    help="Fail if the search turns up more than one ticket.",
)


@search.command()
@check_single_found_ticket
@click.pass_obj
def edit(ticket_store: ticket.TicketStore):
    """Edit matching tickets."""
    for found_ticket in ticket_store.filtered_tickets:
        click.edit(filename=found_ticket.relative_path(ticket_store.tickets_dir))
