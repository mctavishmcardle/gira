import enum
import pathlib
import typing

import click

from cli.callbacks import plain_callback
from gira import ticket


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


ticket_work_type_choice = choice_from_enum(ticket.TicketWorkType)


@plain_callback
def parse_ticket_work_type(value: str) -> ticket.TicketWorkType:
    """Parse the ticket work type choice into a proper enum member"""
    return ticket.TicketWorkType[value]


ticket_status_choice = choice_from_enum(ticket.TicketStatus)
ticket_exclude_status_remove_default = "!"
ticket_exclude_status_choice = click.Choice(
    list(ticket_status_choice.choices) + [ticket_exclude_status_remove_default],
    case_sensitive=False,
)


@plain_callback
def parse_ticket_status(value: str) -> ticket.TicketStatus:
    """Parse the ticket status choice into a proper enum member"""
    return ticket.TicketStatus[value]


ticket_relationship_choice = choice_from_enum(ticket.TicketRelationship)
ticket_relationship_match_any = "ANY"
ticket_relationship_search_choice = click.Choice(
    list(ticket_relationship_choice.choices) + [ticket_relationship_match_any],
    case_sensitive=False,
)


def validate_ticket_relationship(
    context: click.Context, parameter: click.Parameter, value: tuple[int, str]
) -> ticket.SpecificTicketRelationship:
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
        relationship = ~ticket.TicketRelationship(0)
    else:
        relationship = ticket.TicketRelationship[raw_relationship]

    return ticket_number, relationship
