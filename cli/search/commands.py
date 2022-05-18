import click
import tabulate

from gira import ticket


@click.command(name="list")
@click.pass_obj
def list_tickets(ticket_store: ticket.TicketStore):
    """List matching tickets."""
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


@click.command()
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
def edit(ticket_store: ticket.TicketStore):
    """Edit matching tickets."""
    for found_ticket in ticket_store.filtered_tickets:
        click.edit(filename=str(found_ticket.relative_path(ticket_store.tickets_dir)))
