import click
import git
import pathlib
import dataclasses
import slugify
import functools
import typing
import re
import collections
import enum

TICKET_FILE_SUFFIX: str = ".gira.md"
TICKET_FILE_REGEX: str = (
    f"(?P<number>\d+)(-(?P<slug>(\w+)(-\w+)+))?{re.escape(TICKET_FILE_SUFFIX)}"
)


class MalformedTicket(Exception):
    """Raised when a ticket file can't be interpreted as a valid ticket"""

    def __init__(self, path: pathlib.Path):
        """
        Args:
            ticket: The path to the ticket that couldn't be parsed
        """
        self.path = path


@enum.unique
class TicketStatus(enum.Enum):
    """The statuses that a ticket can have"""

    # A ticket that has yet to be started
    TODO = enum.auto()
    # A ticket that is currently being worked on
    STARTED = enum.auto()
    # A ticket on which work has been paused
    STOPPED = enum.auto()
    # A ticket which has been finished
    DONE = enum.auto()


ticket_status_choice = click.Choice(
    [status.name for status in TicketStatus], case_sensitive=False
)


@dataclasses.dataclass
class Ticket:
    """A ticket"""

    number: int
    slug: str
    directory: pathlib.Path

    status: TicketStatus = None

    @property
    def filename(self) -> pathlib.Path:
        """The filename for this ticket"""
        name = str(self.number)
        if self.slug:
            name += f"-{self.slug}"

        return pathlib.Path(f"{name}{TICKET_FILE_SUFFIX}")

    @property
    def path(self) -> pathlib.Path:
        """The path to the ticket file"""
        return self.directory / self.filename

    def __str__(self) -> str:
        return click.format_filename(self.path)

    @classmethod
    def from_path(cls, path: pathlib.Path) -> "Ticket":
        """Create a ticket from a file"""
        match = re.match(TICKET_FILE_REGEX, path.name)
        if match:
            slug = match.group("slug")
            if not slug:
                slug = ""

            return Ticket(
                number=int(match.group("number")), slug=slug, directory=path.parent
            )
        else:
            raise MalformedTicket(path)


class TicketStore:
    """A repository-specific collection of tickets"""

    def __init__(self, tickets_dir: typing.Optional[pathlib.Path]):
        """
        Args:
            tickets_dir: A custom directory where the tickets are stored, if any
        """
        self._tickets_dir = tickets_dir

        self.repo = git.Repo(search_parent_directories=True)

    @functools.cached_property
    def git_dir(self) -> pathlib.Path:
        """The root of the current repo"""
        return pathlib.Path(self.repo.working_tree_dir)

    @functools.cached_property
    def tickets_dir(self) -> pathlib.Path:
        """The ticket storage directory in the current repo"""
        if self._tickets_dir:
            return self._tickets_dir

        return self.git_dir / pathlib.Path(".gira")

    @functools.cached_property
    def all_tickets(self) -> list[Ticket]:
        """All tickets in the current repo"""
        return sorted(list(self._all_tickets), key=lambda ticket: ticket.number)

    @functools.cached_property
    def tickets_by_number(self) -> dict[int, Ticket]:
        """A map from ticket numbers to individual tickets"""
        return {ticket.number: ticket for ticket in self.all_tickets}

    @property
    def _all_tickets(self) -> collections.abc.Iterator[Ticket]:
        """All tickets in the current repo"""
        for ticket_path in self.tickets_dir.glob(f"**/*{TICKET_FILE_SUFFIX}"):
            try:
                yield Ticket.from_path(ticket_path)
            except MalformedTicket:
                # Ignore any bad ticket files
                pass


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
def gira(context: click.Context, tickets_dir: typing.Optional[pathlib.Path]):
    context.obj = TicketStore(tickets_dir)


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
) -> TicketStatus:
    """Parse the ticket status choice into a proper enum member"""
    return TicketStatus[value]


@gira.command(help="Create a new ticket.")
@click.option(
    "-n",
    "--number",
    type=int,
    help="A ticket number to assign. If not specified, one will be chosen automatically.",
    callback=validate_new_ticket_number,
)
@click.option(
    "-s",
    "--slug",
    help="A slugifiable string to label the ticket file with.",
    default="",
    show_default=False,
)
@click.option(
    "-u",
    "--status",
    type=ticket_status_choice,
    default=TicketStatus.TODO.name,
    show_default=True,
    callback=parse_ticket_status,
    help="The status to assign to the ticket.",
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
    ticket_store: TicketStore,
    number: int,
    slug: str,
    status: TicketStatus,
    edit: bool,
    echo_path: bool,
):
    ticket = Ticket(
        number=number,
        slug=slugify.slugify(
            slug,
            max_length=60,
            word_boundary=True,
            save_order=True,
        ),
        directory=ticket_store.tickets_dir,
        status=status,
    )

    # Create the ticket storage directory; noop if it already exists
    ticket_store.tickets_dir.mkdir(parents=True, exist_ok=True)

    # Error out if the file already exists
    ticket.path.touch(exist_ok=False)

    # Optionally echo the path to the ticket
    if echo_path:
        click.echo(ticket.path)

    # Optionally open the file
    if edit:
        click.edit(filename=ticket.path)


@gira.command(name="list", help="List existing tickets.")
@click.pass_obj
def list_tickets(ticket_store: TicketStore):
    for ticket in ticket_store.all_tickets:
        click.echo(ticket)
