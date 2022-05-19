import typing

import click
import tabulate

from cli import new, validation
from gira import ticket, ticket_properties, ticket_store


@click.command(name="list")
@click.pass_obj
def list_tickets(store: ticket_store.TicketStore):
    """List matching tickets and their properties."""
    click.echo(
        tabulate.tabulate(
            (
                (
                    ticket.status.name if ticket.status else ticket.status,
                    ticket.work_type.name if ticket.work_type else ticket.work_type,
                    ticket.number,
                    ticket.title,
                    ticket.group,
                    # `None` results in a blank for empty related ticket lists
                    ticket.related_ticket_numbers or None,
                )
                for ticket in store.filtered_tickets
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


@click.command()
@click.option(
    "-p/-P",
    "--pager/--no-pager",
    default=True,
    callback=handle_page_on_single_tickets,
    help="Use a pager if there are multiple tickets?",
)
@click.pass_obj
def show(store: ticket_store.TicketStore, pager: bool):
    """Display the contents of matching tickets."""
    documents = (ticket.document for ticket in store.filtered_tickets)
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
        raise click.BadParameter("Multiple tickets matched the search criteria.")

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


@click.command()
@check_single_found_ticket
@click.pass_obj
def edit(store: ticket_store.TicketStore):
    """Open matching tickets in an editor."""
    for found_ticket in store.filtered_tickets:
        click.edit(filename=str(store.relative_ticket_path(found_ticket)))


@click.command(name="set")
@check_single_found_ticket
@click.option(
    "-d",
    "--description",
    prompt=True,
    prompt_required=False,
    callback=validation.add_terminal_newline_to_description,
    help="A description to assign to the ticket.",
)
@click.option(
    "-s",
    "--status",
    type=validation.ticket_status_choice,
    callback=validation.parse_ticket_status,
    help="The status to assign to the ticket.",
)
@click.option(
    "-w",
    "--work-type",
    type=validation.ticket_work_type_choice,
    callback=validation.parse_ticket_work_type,
    help="The work type to assign to the ticket.",
)
@click.pass_obj
def set_properties(
    store: ticket_store.TicketStore,
    description: typing.Optional[str],
    status: typing.Optional[ticket_properties.TicketStatus],
    work_type: typing.Optional[ticket_properties.TicketWorkType],
):
    """Set fields of matching tickets to new values.

    Since a ticket can have only a single value of one of these fields, this
    overwrites any existing value.
    """
    for found_ticket in store.filtered_tickets:
        if description:
            found_ticket.description = description

        if status:
            found_ticket.status = status

        if work_type:
            found_ticket.work_type = work_type

        with store.relative_ticket_path(found_ticket).open(
            mode="w"
        ) as found_ticket_file:
            found_ticket_file.write(found_ticket.document)


@click.command()
@check_single_found_ticket
@new.new_ticket_relationships
@click.pass_obj
def add(store: ticket_store.TicketStore, relationships: ticket.RelationshipMap):
    """Add new field elements to matching tickets."""
    for found_ticket in store.filtered_tickets:
        for relationship, tickets_to_labels in relationships.items():
            for ticket_number, label in tickets_to_labels.items():
                found_ticket.relationships[relationship][ticket_number] = label

        with store.relative_ticket_path(found_ticket).open(
            mode="w"
        ) as found_ticket_file:
            found_ticket_file.write(found_ticket.document)
