import collections
import dataclasses
import enum
import functools
import itertools
import pathlib
import re
import typing

import git
import marko
import slugify

from gira import markdown

TICKET_FILE_SUFFIX: str = ".gira.md"
TICKET_FILE_REGEX: str = (
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


@dataclasses.dataclass
class Ticket:
    """A ticket"""

    number: int
    group: pathlib.Path
    status: TicketStatus
    title: str
    description: str
    sections: dict[str, str] = dataclasses.field(default_factory=dict)

    slug: str = None
    to_slug: dataclasses.InitVar[str] = None

    def __post_init__(self, to_slug: str):
        if to_slug is not None and self.slug is None:
            self.slug = slugify.slugify(
                to_slug,
                max_length=60,
                word_boundary=True,
                save_order=True,
            )

    @property
    def full_slug(self) -> str:
        """The 'full' slug, including the ticket number"""
        name = str(self.number)
        if self.slug:
            name += f"-{self.slug}"

        return name

    @property
    def filename(self) -> pathlib.Path:
        """The filename for this ticket"""
        return pathlib.Path(f"{self.full_slug}{TICKET_FILE_SUFFIX}")

    @property
    def path(self) -> pathlib.Path:
        """The path to the ticket file"""
        if self.group:
            return self.group / self.filename
        else:
            return self.filename

    @classmethod
    def from_path(cls, path: pathlib.Path, tickets_dir: pathlib.Path) -> "Ticket":
        """Create a ticket from a file

        Args:
            path: The full path to the ticket
            tickets_dir: The directory containing all the tickets
        """
        match = re.match(TICKET_FILE_REGEX, path.name)
        if match:
            # Slugs are optional in ticket filenames
            slug = match.group("slug")
            if not slug:
                slug = None

            # Groups are optional: ungrouped tickets are directly under the ticket dir
            group = path.relative_to(tickets_dir).parent
            if group == pathlib.Path("."):
                group = None

            with open(path) as ticket_file:
                status, title, description, sections = cls.parse_markdown_document(
                    marko.parse(ticket_file.read())
                )

            return Ticket(
                number=int(match.group("number")),
                slug=slug,
                to_slug=title,
                group=group,
                status=status,
                title=title,
                description=description,
                sections=sections,
            )
        else:
            raise MalformedTicket(path)

    @staticmethod
    def parse_markdown_document(
        document: marko.block.Document,
    ) -> tuple[
        typing.Optional[TicketStatus],
        typing.Optional[str],
        typing.Optional[str],
        dict[str, str],
    ]:
        """Extract significant elements from a ticket file

        Returns:
            A tuple containing:
                1. The ticket status, if any
                2. The ticket title, if any
                3. The ticket description, if any
                4. A map from section titles to section contents, if any
        """
        children, children_for_grouping = itertools.tee(document.children)

        INITIAL_THROWAWAY_VALUE = "initial"
        children_last_heading = itertools.accumulate(
            children_for_grouping,
            lambda previous_level, child: (
                child if isinstance(child, marko.block.Heading) else previous_level
            ),
            initial=INITIAL_THROWAWAY_VALUE,
        )
        # `accumulate` will include the initial value, which breaks the alignment
        # between the copies of `children`, so wrap it in a slice that drops the
        # first element
        children_last_heading = itertools.islice(
            children_last_heading,
            # Start at the first element & don't stop until the end is reached
            1,
            None,
        )

        status = None
        title = None
        description = []
        sections = {}

        for child_group_last_heading, children in itertools.groupby(
            zip(children_last_heading, children),
            key=lambda level_child_tuple: level_child_tuple[0],
        ):
            children = [child for children_last_heading, child in children]

            head = children[0]
            contents = children[1:]

            # Anything before the first heading is the ticket file header
            if child_group_last_heading is INITIAL_THROWAWAY_VALUE:
                try:
                    # The first element in the header should be the ticket status
                    status = TicketStatus[markdown.get_single_element_text(head)]
                except (KeyError, TypeError):
                    # If it isn't, treat it as a description
                    description.append(head)
                # Any remaining elements are counted as a description
                description.extend(contents)
            else:
                heading_text = markdown.get_single_element_text(head)

                # The first heading encountered will be treated as the ticket title,
                # and any text following it, until the next heading, is the ticket
                # description
                if title is None:
                    title = heading_text
                    if contents:
                        description.extend(contents)
                # Anything after that is treated as a generic section
                else:
                    sections[heading_text] = contents

        description = markdown.render_element_list(description)
        sections = {
            title: markdown.render_element_list(contents)
            for title, contents in sections.items()
        }

        return status, title, description, sections

    @property
    def document(self) -> str:
        """The contents of the ticket file"""
        return "".join(
            ([f"{self.status.name}\n"] if self.status else [])
            + ([f"# {self.title}\n"] if self.title else [])
            + ([self.description] if self.description else [])
            + list(
                itertools.chain(
                    ["# {section}\n", contents]
                    for section, contents in self.sections.items()
                )
            )
        )


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
                yield Ticket.from_path(ticket_path, self.tickets_dir)
            except MalformedTicket:
                # Ignore any bad ticket files
                pass
