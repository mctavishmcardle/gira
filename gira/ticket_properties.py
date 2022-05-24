import dataclasses
import enum
import pathlib
import re
import typing

TICKET_FILE_SUFFIX: str = ".gira.md"
TICKET_FILE_REGEX: re.Pattern = re.compile(
    f"(?P<number>\d+)(-(?P<slug>(\w+)(-\w+)*))?{re.escape(TICKET_FILE_SUFFIX)}"
)


class MalformedTicket(Exception):
    """Raised when a ticket file can't be interpreted as a valid ticket"""

    def __init__(self, path: pathlib.Path):
        """
        Args:
            ticket: The path to the ticket that couldn't be parsed
        """
        self.path = path


@dataclasses.dataclass
class PathComponents:
    """A container for all the information about a ticket contained in its path"""

    # Should be relative to the ticket root dir
    path: pathlib.Path
    number: int
    slug: typing.Optional[str]

    @classmethod
    def is_ticket_file(cls, path: pathlib.Path) -> bool:
        """Does the path correspond to a ticket file?

        Args:
            path: The path to check
        """
        try:
            cls.from_path(path)
            return True
        except MalformedTicket:
            return False

    @property
    def group(self) -> typing.Optional[pathlib.Path]:
        """The group that the ticket is in"""
        group: typing.Optional[pathlib.Path] = self.path.parent

        if group == pathlib.Path("."):
            group = None

        return group

    @property
    def filename(self) -> str:
        """The filename of the ticket"""
        return self.path.name

    @classmethod
    def from_path(cls, path: pathlib.Path) -> "PathComponents":
        """Extract the components from a path

        Args:
            path: The path to get ticket component information from; should be
                relative to the root ticket dir

        Raises:
            MalformedTicket:
                If required information can't be extracted from the ticket path
        """
        match = TICKET_FILE_REGEX.match(path.name)

        if match:
            return cls(
                path,
                int(match.group("number")),
                # Slugs are optional in ticket filenames: `slug` will be `None`
                # if that group is missing from the match
                match.group("slug"),
            )
        else:
            raise MalformedTicket(path)


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


@enum.unique
class TicketRelationship(enum.Flag):
    """The relationships a ticket have with another ticket

    Note:
        These are directional: The ticket with the relationship 'verbs' the
        ticket that is the target of the relationship

    Note:
        Because a ticket can have multiple relationships, of different types,
        to another ticket, this enum is a `Flag` to allow easy comparisons.
    """

    # One ticket refers to another one
    REFERENCES = enum.auto()
    # One ticket relates to another one
    RELATES_TO = enum.auto()

    # One ticket prevents another from being worked on
    BLOCKS = enum.auto()
    BLOCKED_BY = enum.auto()
    # One ticket results in another being required
    CAUSES = enum.auto()
    CAUSED_BY = enum.auto()
    # One ticket makes another's work unecessary
    FIXES = enum.auto()
    FIXED_BY = enum.auto()


@enum.unique
class TicketWorkType(enum.Enum):
    """The types of work that a ticket can correspond to"""

    # A ticket that implements a new feature
    FEATURE = enum.auto()
    # A ticket that corresponds to non-feature work
    TASK = enum.auto()
    # A ticket that fixes a bug
    BUG = enum.auto()
