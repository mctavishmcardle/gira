import functools
import typing

import click
import git

from gira import ticket, ticket_store


def get_ticket(
    context: click.Context,
    parameter: click.Parameter,
    value: int,
) -> ticket.Ticket:
    """Get the ticket corresponding to an input ticket number.

    Errors out if the ticket doesn't exist
    """
    try:
        return context.obj.get_ticket(value)
    except ticket_store.NonexistentTicket:
        raise click.BadParameter(f"Ticket #{value} cannot be found.")


@click.command(name="checkout")
@click.option(
    "-n",
    "-number",
    "target_ticket",
    type=int,
    required=True,
    callback=get_ticket,
    help="The number of the ticket to check out.",
)
@click.pass_obj
def checkout_ticket(store: ticket_store.TicketStore, target_ticket: ticket.Ticket):
    """Check out a ticket's branch.

    If the corresponding branch doesn't exist, it will be created.
    """
    typing.cast(
        git.Head, store.repo_manager.get_branch(target_ticket.git_branch)
    ).checkout()


COMMIT_FLAG_NAME = "commit"

commit_flag = functools.partial(
    click.option,
    "-c/-C",
    "--commit/--no-commit",
    COMMIT_FLAG_NAME,
    default=False,
    show_default=True,
)


def committing(context: click.Context) -> bool:
    return context.params[COMMIT_FLAG_NAME]


def validate_committing_nontickets(
    context: click.Context, parameter: click.Parameter, value: bool
):
    """Check for staged non-ticket modifications and error if appropriate

    If:
       * user requests not to commit nonticket files, and
       * user requests we commit, and
       * there are staged nonticket files
    then we error out

    Raises:
        BadParameter
    """
    if not value and committing(context) and context.obj.staged_nonticket_files:
        raise click.BadParameter("There are staged files that don't contain tickets.")

    # Don't need to return because this parameter is not exposed


commit_nonticket_flag = click.option(
    "--commit-non-tickets/--no-commit-non-tickets",
    default=False,
    show_default=True,
    expose_value=False,
    callback=validate_committing_nontickets,
    help="Allow commits if there are staged changes to non-ticket files.",
)


def format_ticket_numbers(ticket_numbers: list[int]) -> str:
    """Format a list of ticket numbers"""
    return ", ".join(f"#{ticket_number}" for ticket_number in ticket_numbers)


def validate_committing_with_unstaged_tickets(
    context: click.Context, parameter: click.Parameter, value: bool
):
    """Check for staged non-ticket modifications and error if appropriate

    If:
      * user requests not to commit with unstaged ticket files, and
      * user requests we commit, and
      * there are unstaged ticket files
    then we error out

    Raises:
        BadParameter
    """
    if not value and committing(context) and context.obj.unstaged_ticket_numbers:
        raise click.BadParameter(
            f"There are unstaged ticket files: {format_ticket_numbers(context.obj.unstaged_ticket_numbers)}."
        )

    # Don't need to return because this parameter is not exposed


commit_unstaged_ticket_flag = click.option(
    "--commit-with-unstaged-tickets/--no-commit-with-unstaged-tickets",
    default=False,
    show_default=True,
    expose_value=False,
    callback=validate_committing_with_unstaged_tickets,
    help="Allow commits if there are unstaged changes to ticket files.",
)


def validate_staging_ticket(
    context: click.Context, parameter: click.Parameter, value: bool
) -> bool:
    """Default to staging modifications if we're committing"""
    return value or committing(context)


stage_flag = functools.partial(
    click.option,
    "-z/-Z",
    "--stage/--no-stage",
    default=False,
    callback=validate_staging_ticket,
    show_default=True,
)


def ticket_commit_options(commit_help: str, stage_help: str):
    """Add options for staging & committing ticket modifications

    Args:
        commit_help: The help text to display for the `--commit` flag
        stage_help: The help text to display for the `--stage` flag
    """
    stage_flag_with_help = stage_flag(help=f"{stage_help}  (implied by `-c`)")

    commit_flag_with_help = commit_flag(help=commit_help)

    def wrap_with_options(func: typing.Callable):
        return commit_flag_with_help(
            commit_nonticket_flag(
                commit_unstaged_ticket_flag(stage_flag_with_help(func))
            )
        )

    return wrap_with_options
