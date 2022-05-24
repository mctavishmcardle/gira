import typing

import click
import tabulate

from cli import git, new, validation
from gira import ticket, ticket_properties, ticket_store


def error_on_empty_target_list(
    context: click.Context, parameter: click.Parameter, value: bool
) -> None:
    """Error out if requested and no tickets were found"""
    if value and not context.obj.filtered_tickets:
        raise click.BadParameter(f"No tickets matched the search criteria.")


error_none_found = click.option(
    "--error-none-found/--no-error-none_found",
    default=True,
    show_default=True,
    expose_value=False,
    callback=error_on_empty_target_list,
    help="Fail if no tickets matched.",
)


@click.command(name="list")
@click.pass_obj
def list_tickets(store: ticket_store.TicketStore):
    """List matching tickets and their properties."""
    click.echo(
        tabulate.tabulate(
            (
                (
                    found_ticket.status.name
                    if found_ticket.status
                    else found_ticket.status,
                    found_ticket.work_type.name
                    if found_ticket.work_type
                    else found_ticket.work_type,
                    found_ticket.number,
                    found_ticket.title,
                    found_ticket.group,
                    # `None` results in a blank for empty related ticket lists
                    found_ticket.related_ticket_numbers or None,
                    # `None` results in a blank for nonexistent branches
                    found_ticket.git_branch
                    if store.repo_manager.branch_exists(found_ticket.git_branch)
                    else None,
                )
                for found_ticket in store.filtered_tickets
            ),
            tablefmt="plain",
        )
    )


@click.command()
@click.pass_obj
@error_none_found
def stage(store: ticket_store.TicketStore):
    """Stage any changes to matching tickets."""
    for found_ticket in store.filtered_tickets:
        store.stage(found_ticket)


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
    help="Use a pager if there are multiple tickets.",
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

commit_modifications_options = git.ticket_commit_options(
    commit_help="Commit any modifications.", stage_help="Stage any modifications."
)


def commit_modifications(store: ticket_store.TicketStore) -> None:
    """Commit changes to filtered tickets

    The commit message will include all filtered ticket numbers

    Args:
        store: The ticket store
    """
    if len(store.filtered_tickets) == 1:
        ticket_word = "ticket"
    else:
        ticket_word = "tickets"

    store.repo_manager.commit(
        f"Modified {ticket_word} {git.format_ticket_numbers(store.filtered_ticket_numbers)}."
    )


@click.command()
@check_single_found_ticket
@error_none_found
@commit_modifications_options
@click.pass_obj
def edit(store: ticket_store.TicketStore, stage: bool, commit: bool):
    """Open matching tickets in an editor."""
    for found_ticket in store.filtered_tickets:
        click.edit(filename=str(store.relative_ticket_path(found_ticket)))

        if stage:
            store.stage(found_ticket)

    if commit:
        commit_modifications(store)


@click.command(name="set")
@check_single_found_ticket
@error_none_found
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
@commit_modifications_options
@click.pass_obj
def set_properties(
    store: ticket_store.TicketStore,
    description: typing.Optional[str],
    status: typing.Optional[ticket_properties.TicketStatus],
    work_type: typing.Optional[ticket_properties.TicketWorkType],
    stage: bool,
    commit: bool,
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

        store.write(found_ticket, stage)

    if commit:
        commit_modifications(store)


@click.command()
@check_single_found_ticket
@error_none_found
@new.new_ticket_relationships
@commit_modifications_options
@click.pass_obj
def add(
    store: ticket_store.TicketStore,
    relationships: ticket.RelationshipMap,
    stage: bool,
    commit: bool,
):
    """Add new field elements to matching tickets."""
    for found_ticket in store.filtered_tickets:
        for relationship, tickets_to_labels in relationships.items():
            for ticket_number, label in tickets_to_labels.items():
                found_ticket.relationships[relationship][ticket_number] = label

        store.write(found_ticket, stage)

    if commit:
        commit_modifications(store)
