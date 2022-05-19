import collections
import enum
import pathlib
import typing

import click

from cli.callbacks import (
    compose_callbacks,
    mapped_callback,
    none_passthrough,
    plain_callback,
)
from gira import ticket, ticket_properties, ticket_store


@plain_callback
@none_passthrough
def add_terminal_newline_to_description(value: str) -> str:
    """Add a newline to the end of a ticket description

    Required because one isn't added by default for prompted values
    """
    return f"{value}\n"


def relativize_group(
    context: click.Context,
    parameter: click.Parameter,
    value: typing.Optional[pathlib.Path],
) -> typing.Optional[pathlib.Path]:
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


def choice_from_enum(
    enum_type: typing.Type[enum.Enum], case_sensitive: bool = False
) -> click.Choice:
    """Constructs a `click` parameter choice from enum members

    Args:
        enum_type: The enum whose members to permit
        case_sensitive: Should the choice by case-sensitive?
        choice_type: If desired, the `Choice` subclass to use
    """
    return click.Choice(
        [member.name for member in enum_type], case_sensitive=case_sensitive
    )


ticket_work_type_choice = choice_from_enum(ticket_properties.TicketWorkType)


@plain_callback
@none_passthrough
def parse_ticket_work_type(value: str) -> ticket_properties.TicketWorkType:
    """Parse the ticket work type choice into a proper enum member"""
    return ticket_properties.TicketWorkType[value]


ticket_status_choice = choice_from_enum(ticket_properties.TicketStatus)
ticket_exclude_status_remove_default = "!"
ticket_exclude_status_choice = click.Choice(
    list(ticket_status_choice.choices) + [ticket_exclude_status_remove_default],
    case_sensitive=False,
)


@plain_callback
@none_passthrough
def parse_ticket_status(value: str) -> ticket_properties.TicketStatus:
    """Parse the ticket status choice into a proper enum member"""
    return ticket_properties.TicketStatus[value]


ticket_relationship_choice = choice_from_enum(ticket_properties.TicketRelationship)
ticket_relationship_match_any = "ANY"
ticket_relationship_search_choice = click.Choice(
    list(ticket_relationship_choice.choices) + [ticket_relationship_match_any],
    case_sensitive=False,
)


def validate_ticket_relationship(
    context: click.Context, parameter: click.Parameter, value: tuple[int, str]
) -> ticket_store.SpecificTicketRelationship:
    """Validate a specifc ticket relationship.

    This function:
        * Ensures it points to an actual ticket
        * Extracts the correct relationship enum member
        * Handles matching "ANY" ticket relationship

    Raises:
        click.BadParameter: If the ticket doesn't exist
    """
    ticket_number, raw_relationship = value

    if ticket_number not in context.obj.all_ticket_numbers:
        raise click.BadParameter(message=f"Ticket #{ticket_number} does not exist.")

    if raw_relationship == ticket_relationship_match_any:
        # Negating the null flag is equivalent to ORing all of them
        # i.e. it corresponds to "ANY"
        relationship = ~ticket_properties.TicketRelationship(0)
    else:
        relationship = ticket_properties.TicketRelationship[raw_relationship]

    return ticket_number, relationship


TicketRelationshipTuple = tuple[int, ticket_properties.TicketRelationship, str]


@mapped_callback
def validate_raw_ticket_relationships(
    context: click.Context,
    parameter: click.Parameter,
    value: tuple[int, str, str],
) -> TicketRelationshipTuple:
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


@plain_callback
def build_ticket_relationship_map(
    relationships: list[TicketRelationshipTuple],
) -> ticket.RelationshipMap:
    """Construct a ticket relationship map"""
    relationship_map: ticket.RelationshipMap = collections.defaultdict(dict)
    for target_ticket_number, relationship, label in relationships:
        relationship_map[relationship][target_ticket_number] = label

    return relationship_map


validate_ticket_relationship_creation = compose_callbacks(
    [build_ticket_relationship_map, validate_raw_ticket_relationships]
)
