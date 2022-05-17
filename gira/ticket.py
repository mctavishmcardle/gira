import collections
import dataclasses
import enum
import functools
import itertools
import operator
import os
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


@dataclasses.dataclass
class PathComponents:
    """A container for all the information about a ticket contained in its path"""

    # Should be relative to the ticket root dir
    path: pathlib.Path
    number: int
    slug: typing.Optional[str]

    @property
    def group(self) -> typing.Optional[pathlib.Path]:
        """The group that the ticket is in"""
        group = self.path.parent

        if group == pathlib.Path("."):
            group = None
        else:
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
        match = re.match(TICKET_FILE_REGEX, path.name)

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


# A map from relationship types to: maps of tickets that have those relationships
# to the label for that relationship
RelationshipMap = dict[TicketRelationship, dict[int, str]]


@dataclasses.dataclass
class Ticket:
    """A ticket"""

    number: int
    group: pathlib.Path
    status: TicketStatus
    title: str
    description: str

    sections: dict[str, str] = dataclasses.field(default_factory=dict)
    relationships: RelationshipMap = dataclasses.field(default_factory=dict)

    slug: str = None
    to_slug: dataclasses.InitVar[str] = None

    def __post_init__(self, to_slug: str):
        if self.slug is None:
            if to_slug is not None:
                self.slug = slugify.slugify(
                    to_slug,
                    max_length=60,
                    word_boundary=True,
                    save_order=True,
                )
            else:
                self.slug = ""

    def is_in_group(self, group: pathlib.Path) -> bool:
        """Is this ticket in a specific group?

        Args:
            group: The group to check
        """
        return self.group is not None and self.group.is_relative_to(group)

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

    def relative_path(self, tickets_dir: pathlib.Path) -> pathlib.Path:
        """The path, from the current working directory, to the ticket

        Args:
            tickets_dir: The top-level ticket directory, in which this ticket
                lives (though this ticket may be in a subdirectory, if it's in
                a group)
        """
        return os.path.relpath(tickets_dir / self.path)

    @staticmethod
    def extract_document_relationships(
        document: marko.block.Document,
    ) -> RelationshipMap:
        """Get raw relationships from a ticket document

        Note:
            These relationships are not validated (i.e. the targets might not
            actually correspond to exitsing tickets)

        Returns:
            A map from ticket relationship types to sets of tuples containing:
                1. The number of a target ticket
                2. The label for the relationship to that target
        """
        relationships = collections.defaultdict(dict)

        # Only get relationships from link reference definitions, for now
        for label, (destination, title) in document.link_ref_defs.items():
            destination, title = markdown.parse_link_components(destination, title)

            try:
                title = title.upper()
            # Indicates the title is `None`
            except AttributeError:
                continue

            try:
                relationship = TicketRelationship[title]
            # Indicates that the relationship isn't of a known type
            except KeyError:
                continue

            try:
                relationships[relationship][int(destination)] = label
            # Indicates that the destination can't be parsed as an int (so it
            # can't possibly be a ticket number)
            except ValueError:
                continue

        return relationships

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

        children = itertools.filterfalse(
            lambda element: isinstance(element, marko.block.BlankLine),
            document.children,
        )
        children, children_for_grouping = itertools.tee(children)

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
    def display_title(self) -> str:
        """The title that's displayed"""
        return self.title or ""

    @property
    def document(self) -> str:
        """The contents of the ticket file"""
        return "".join(
            ([f"{self.status.name}", "\n\n"] if self.status else [])
            + ([f"# {self.title}", "\n"] if self.title else [])
            + (["\n", f"{self.description}"] if self.description else [])
            # Format all sections
            + list(
                itertools.chain.from_iterable(
                    ["\n", f"# {section}", "\n\n", f"{contents}"]
                    for section, contents in self.sections.items()
                )
            )
            # Format all relationships
            + (
                (
                    ["\n"]
                    + list(
                        itertools.chain.from_iterable(
                            itertools.chain.from_iterable(
                                [
                                    "\n",
                                    f"[{link_label}]: {target_ticket_number} ({relationship.name})",
                                ]
                                for target_ticket_number, link_label in target_tickets.items()
                            )
                            for relationship, target_tickets in self.relationships.items()
                        )
                    )
                    + ["\n"]
                )
                if self.relationships
                else []
            )
        )

    @functools.cached_property
    def inverted_relationships(self) -> dict[int, TicketRelationship]:
        """A map from ticket numbers to a union of all relationships this ticket has with that ticket

        Warning:
            Because this uses a `defaultdict`, it cannot be used to list all the
            tickets that this ticket has a relationship with, as `keys` will
            erroneously include any ticket numbers that were checked during
            searching
        """
        inverted_relationships = collections.defaultdict(lambda: TicketRelationship(0))

        for relationship, tickets in self.relationships.items():
            for ticket in tickets:
                # Since we've defaulted to the "NONE" condition, ORing each new
                # relationship type will produce the union of all relationships
                # with that ticket
                inverted_relationships[ticket] |= relationship

        return inverted_relationships

    @functools.cached_property
    def related_ticket_numbers(self) -> list[int]:
        """The numbers of all tickets that this ticket is related to"""
        return sorted(set(itertools.chain.from_iterable(self.relationships.values())))


# The individual items in ticket search inclusion & exclusion lists
V = typing.TypeVar("V")


# A combination of a target ticket number & a relationship with that ticket
SpecificTicketRelationship = tuple[int, TicketRelationship]


@dataclasses.dataclass
class SearchConditions:
    """A container for searching collections of tickets"""

    numbers: list[int]
    exclude_numbers: list[int]
    groups: list[pathlib.Path]
    exclude_groups: list[pathlib.Path]
    statuses: list[TicketStatus]
    exclude_statuses: list[TicketStatus]
    titles: list[re.Pattern]
    exclude_titles: list[re.Pattern]
    descriptions: list[re.Pattern]
    exclude_descriptions: list[re.Pattern]
    slugs: list[re.Pattern]
    exclude_slugs: list[re.Pattern]
    relationships: list[SpecificTicketRelationship]
    exclude_relationships: list[SpecificTicketRelationship]

    @staticmethod
    def match_ticket_relationship(
        ticket: Ticket,
    ) -> typing.Callable[[SpecificTicketRelationship], bool]:
        """Generate a callable for testing specific relationships against this ticket"""

        def ticket_relationship_predicate(
            specific_relationship: SpecificTicketRelationship,
        ) -> bool:
            """Does the ticket match the specific relationship?

            Note:
                The ticket being tested is in scope via closure
            """
            ticket_number, relationship = specific_relationship

            # The inverted relationships map defaults to the "NONE" condition,
            # which is falsy when ANDed with anything. If a ticket being tested
            # has one or more relationships with another target ticket, then
            # the value will be the union of all those relationship types, which
            # will be truthy when ANDed with any of those relationships (or the
            # "ANY" condition, which is the union of all possible relationship
            # types) and falsy when ANDed with a type that doesn't correspond to
            # an existing relationship between the tested ticket and the target
            # ticket
            return ticket.inverted_relationships[ticket_number] & relationship

        return ticket_relationship_predicate

    @staticmethod
    def matching_predicate(
        condition: collections.abc.Callable[[V], bool],
        include: list[V],
        exclude: list[V],
    ) -> bool:
        """Distribute inclusion & exclusion conditions for ticket searching

        Args;
            condition: The condition check to apply to a test value
            include: The values to include; the condition check must be truthy for
                at least one (if there are any)
            exclude: The values to exclude; the condition check must be falsy for all
                of these
        """
        return (any(map(condition, include)) if include else True) and not any(
            map(condition, exclude)
        )

    def ticket_matches(self, ticket: Ticket) -> bool:
        """Does a ticket match the configured search criteira?"""
        return (
            self.matching_predicate(
                lambda number: ticket.number == number,
                self.numbers,
                self.exclude_numbers,
            )
            and self.matching_predicate(
                lambda group: ticket.is_in_group(group),
                self.groups,
                self.exclude_groups,
            )
            and self.matching_predicate(
                lambda status: ticket.status is status,
                self.statuses,
                self.exclude_statuses,
            )
            and self.matching_predicate(
                lambda regex: regex.search(ticket.display_title),
                self.titles,
                self.exclude_titles,
            )
            and self.matching_predicate(
                lambda regex: regex.search(ticket.description),
                self.descriptions,
                self.exclude_descriptions,
            )
            and self.matching_predicate(
                lambda regex: regex.search(ticket.slug),
                self.slugs,
                self.exclude_slugs,
            )
            and self.matching_predicate(
                self.match_ticket_relationship(ticket),
                self.relationships,
                self.exclude_relationships,
            )
        )


class LazyTicketStore(dict):
    """A map from ticket numbers to tickets

    The tickets in question are only created when needed, on retrieval.

    Warning:
        Because of how `__missing__`, works, only regular key access should be
        used to get tickets. `get` will return the default value if the ticket
        has not been lazily loaded.
    """

    def __init__(
        self,
        ticket_path_components_by_number: dict[int, PathComponents],
        tickets_dir: pathlib.Path,
    ):
        """
        Args:
            ticket_path_components_by_number: A map from ticket numbers to their
                path component contianers
            tickets_dir: The root directory for tickets
        """
        super().__init__()

        self.ticket_path_components_by_number = ticket_path_components_by_number
        self.tickets_dir = tickets_dir

    def __missing__(self, key: int) -> Ticket:
        # Attempts to get tickets for
        path_components = self.ticket_path_components_by_number[key]

        # Parse the ticket file contents
        with open(self.tickets_dir / path_components.path) as ticket_file:
            document = marko.parse(ticket_file.read())
            status, title, description, sections = Ticket.parse_markdown_document(
                document
            )
            raw_relationships = Ticket.extract_document_relationships(document)

        # Only include relationships to tickets that actually exist
        relationships = collections.defaultdict(dict)
        for relationship_type, target_tickets in raw_relationships.items():
            for target_ticket_number, relationship_label in target_tickets.items():
                if target_ticket_number in self.ticket_path_components_by_number:
                    relationships[relationship_type][
                        target_ticket_number
                    ] = relationship_label

        return Ticket(
            number=path_components.number,
            slug=path_components.slug,
            group=path_components.group,
            status=status,
            title=title,
            description=description,
            sections=sections,
            relationships=relationships,
        )


class TicketStore:
    """A repository-specific collection of tickets

    This store uses an internal `LazyTicketStore` to lazily load tickets, only
    opening & parsing their contents when necessary.
    """

    def __init__(self, tickets_dir: typing.Optional[pathlib.Path]):
        """
        Args:
            tickets_dir: A custom directory where the tickets are stored, if any
        """
        self._tickets_dir = tickets_dir

        self.repo = git.Repo(search_parent_directories=True)
        self.search_conditions: SearchCondtions = None

        self.lazy_ticket_store = LazyTicketStore(
            # Because this is a cached property, it's not actually accessed (so
            # the map isn't actually created) until it's needed
            self.ticket_path_components_by_number,
            self.tickets_dir,
        )

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

    @property
    def _all_ticket_path_components(self) -> collections.abc.Iterator[PathComponents]:
        """Yields all the valid ticket path component containers in the ticket dir"""
        for ticket_path in self.tickets_dir.rglob(f"*{TICKET_FILE_SUFFIX}"):
            try:
                yield PathComponents.from_path(
                    ticket_path.relative_to(self.tickets_dir)
                )
            # Ignore any bad ticket files
            except MalformedTicket:
                continue

    @functools.cached_property
    def all_ticket_path_components(self) -> list[PathComponents]:
        """A list of all the valid ticket path component containers in the ticket dir"""
        return list(self._all_ticket_path_components)

    @functools.cached_property
    def ticket_path_components_by_number(self) -> dict[int, PathComponents]:
        """A map from ticket numbers to containers of path component information"""
        return {
            path_component.number: path_component
            for path_component in self.all_ticket_path_components
        }

    @functools.cached_property
    def all_ticket_numbers(self) -> set[int]:
        """The numbers of all tickets that exist"""
        return set(self.ticket_path_components_by_number.keys())

    @property
    def next_ticket_number(self) -> int:
        """The number that should be used for a newly-created ticket"""
        # Default to -1 so the result is 0 if there are no tickets
        return max(self.all_ticket_numbers, default=-1) + 1

    def get_ticket(self, number: int) -> Ticket:
        """Retrieve a ticket by number

        Args:
            number: The number whose ticket to get
        """
        return self.lazy_ticket_store[number]

    @property
    def _all_tickets(self) -> collections.abc.Iterator[Ticket]:
        """All tickets in the current repo"""
        for ticket_number in self.all_ticket_numbers:
            yield self.get_ticket(ticket_number)

    @functools.cached_property
    def all_tickets(self) -> list[Ticket]:
        """All tickets in the current repo"""
        return sorted(list(self._all_tickets), key=lambda ticket: ticket.number)

    def set_search_conditions(self, search_conditions: SearchConditions) -> None:
        """Set the conditions for ticket filtering"""
        self.search_conditions = search_conditions

    @property
    def _filtered_tickets(self) -> collections.abc.Iterator[Ticket]:
        """Tickets matching the set filtering conditions"""
        for ticket in self.all_tickets:
            if self.search_conditions and self.search_conditions.ticket_matches(ticket):
                yield ticket

    @functools.cached_property
    def filtered_tickets(self) -> list[Ticket]:
        """Tickets matching the set filtering conditions, if any"""
        return sorted(list(self._filtered_tickets), key=lambda ticket: ticket.number)
