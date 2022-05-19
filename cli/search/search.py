import functools
import pathlib
import re

import click

from cli.callbacks import mapped_callback, plain_callback
from cli.validation import (
    parse_ticket_status,
    parse_ticket_work_type,
    relativize_group,
    ticket_exclude_status_choice,
    ticket_exclude_status_remove_default,
    ticket_relationship_match_any,
    ticket_relationship_search_choice,
    ticket_status_choice,
    ticket_work_type_choice,
    validate_ticket_relationship,
)
from gira import ticket_properties, ticket_store

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

search_relationship = functools.partial(
    search_option,
    type=(int, ticket_relationship_search_choice),
    callback=mapped_callback(validate_ticket_relationship),
)


@click.group(invoke_without_command=True)
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
    default=[ticket_properties.TicketStatus.DONE.name],
    show_default=True,
    callback=mapped_callback(
        parse_ticket_status, lambda value: value != ticket_exclude_status_remove_default
    ),
    help=(
        "Exclude tickets with one of these statuses. "
        f"Pass `{ticket_exclude_status_remove_default}` to bypass the default exclusion."
    ),
)
@search_option(
    "-w",
    "--work-type",
    "work_types",
    type=ticket_work_type_choice,
    callback=mapped_callback(parse_ticket_work_type),
    help="Show tickets with one of these work types.",
)
@search_option(
    "-W",
    "--exclude-work-type",
    "exclude_work_types",
    type=ticket_work_type_choice,
    callback=mapped_callback(parse_ticket_work_type),
    help="Exclude tickets with one of these work types.",
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
@search_relationship(
    "-r",
    "--relationship",
    "relationships",
    help=(
        "Show tickets with this relationship to another ticket. "
        f"Pass `{ticket_relationship_match_any}` to match any relationship type."
    ),
)
@search_relationship(
    "-R",
    "--exclude-relationship",
    "exclude_relationships",
    help=(
        "Exclude tickets with this relationship to another ticket. "
        f"Pass `{ticket_relationship_match_any}` to match any relationship type."
    ),
)
@click.pass_obj
@click.pass_context
def search(
    context: click.Context,
    store: ticket_store.TicketStore,
    numbers: list[int],
    exclude_numbers: list[int],
    groups: list[pathlib.Path],
    exclude_groups: list[pathlib.Path],
    statuses: list[ticket_properties.TicketStatus],
    exclude_statuses: list[ticket_properties.TicketStatus],
    work_types: list[ticket_properties.TicketWorkType],
    exclude_work_types: list[ticket_properties.TicketWorkType],
    titles: list[re.Pattern],
    exclude_titles: list[re.Pattern],
    descriptions: list[re.Pattern],
    exclude_descriptions: list[re.Pattern],
    slugs: list[re.Pattern],
    exclude_slugs: list[re.Pattern],
    relationships: list[ticket_store.SpecificTicketRelationship],
    exclude_relationships: list[ticket_store.SpecificTicketRelationship],
):
    """Search for tickets.

    Multiple instances of the same option are OR'd together, and multiple
    different options are AND'd together.

    If no subcommand is invoked, this will output the relative paths to all the
    matched tickets.
    """
    store.set_search_conditions(
        ticket_store.SearchConditions(
            numbers,
            exclude_numbers,
            groups,
            exclude_groups,
            statuses,
            exclude_statuses,
            work_types,
            exclude_work_types,
            titles,
            exclude_titles,
            descriptions,
            exclude_descriptions,
            slugs,
            exclude_slugs,
            relationships,
            exclude_relationships,
        )
    )

    # Default to echoing relative paths
    if context.invoked_subcommand is None:
        for found_ticket in store.filtered_tickets:
            click.echo(found_ticket.relative_path(store.tickets_dir))
