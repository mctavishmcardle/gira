import collections
import dataclasses
import functools
import itertools
import pathlib
import re
import typing

import marko
import slugify

from gira import markdown, ticket_properties

WORK_TYPE_UNION = "|".join(
    work_type.name for work_type in ticket_properties.TicketWorkType
)
TICKET_HEADER_REGEX = re.compile(f"(?P<work_type>{WORK_TYPE_UNION}): (?P<title>.+)")

RelationshipMap = dict[ticket_properties.TicketRelationship, dict[int, str]]


@dataclasses.dataclass
class Ticket:
    """A ticket"""

    number: int
    group: typing.Optional[pathlib.Path]
    status: typing.Optional[ticket_properties.TicketStatus]
    work_type: typing.Optional[ticket_properties.TicketWorkType]
    title: typing.Optional[str]
    description: typing.Optional[str]

    sections: dict[str, str] = dataclasses.field(default_factory=dict)
    relationships: RelationshipMap = dataclasses.field(
        default_factory=lambda: collections.defaultdict(dict)
    )

    slug: typing.Optional[str] = None
    to_slug: dataclasses.InitVar[typing.Optional[str]] = None

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
    def git_branch(self) -> str:
        """The name of the git branch corresponding to this ticket

        Includes the work type and slug, if they exist.

        Defaults to prefixing the branch name with "ticket" if there is no work
        type.
        """
        if self.work_type:
            work_type_prefix = self.work_type.name.lower()
        else:
            work_type_prefix = "ticket"

        work_type_prefix += "/"

        return f"{work_type_prefix}{self.full_slug}"

    @property
    def filename(self) -> pathlib.Path:
        """The filename for this ticket"""
        return pathlib.Path(f"{self.full_slug}{ticket_properties.TICKET_FILE_SUFFIX}")

    @property
    def path(self) -> pathlib.Path:
        """The path to the ticket file"""
        if self.group:
            return self.group / self.filename
        else:
            return self.filename

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
        relationships: RelationshipMap = collections.defaultdict(dict)

        # Only get relationships from link reference definitions, for now
        for label, (raw_destination, raw_title) in document.link_ref_defs.items():
            destination, title = markdown.parse_link_components(
                raw_destination, raw_title
            )

            try:
                title = typing.cast(str, title).upper()
            # Indicates the title is `None`
            except AttributeError:
                continue

            try:
                relationship = ticket_properties.TicketRelationship[title]
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
        typing.Optional[ticket_properties.TicketStatus],
        typing.Optional[ticket_properties.TicketWorkType],
        typing.Optional[str],
        typing.Optional[str],
        dict[str, str],
    ]:
        """Extract significant elements from a ticket file

        Returns:
            A tuple containing:
                1. The ticket status, if any
                2. The ticket work type, if any
                3. The ticket title, if any
                4. The ticket description, if any
                5. A map from section titles to section contents, if any
        """

        children: collections.abc.Iterator[
            marko.block.BlockElement
        ] = itertools.filterfalse(
            lambda element: isinstance(element, marko.block.BlankLine),
            document.children,
        )
        children, children_for_grouping = itertools.tee(children)

        INITIAL_THROWAWAY_VALUE = marko.block.BlockElement()
        children_last_heading: collections.abc.Iterator[
            marko.block.BlockElement
        ] = itertools.accumulate(
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
        work_type = None
        description = []
        sections: dict[str, list[marko.block.BlockElement]] = {}

        for child_group_last_heading, children_under_heading in itertools.groupby(
            zip(children_last_heading, children),
            key=lambda level_child_tuple: level_child_tuple[0],
        ):
            child_elements = [
                child for children_last_heading, child in children_under_heading
            ]

            head = child_elements[0]
            contents = child_elements[1:]

            # Anything before the first heading is the ticket file header
            if child_group_last_heading is INITIAL_THROWAWAY_VALUE:
                try:
                    # The first element in the header should be the ticket status
                    status = ticket_properties.TicketStatus[
                        markdown.get_single_element_text(head)
                    ]
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

        if title:
            title, work_type = Ticket.extract_title_and_work_type(title)

        return (
            status,
            work_type,
            title,
            markdown.render_element_list(description),
            {
                title: markdown.render_element_list(contents)
                for title, contents in sections.items()
            },
        )

    @staticmethod
    def extract_title_and_work_type(
        header: str,
    ) -> tuple[typing.Optional[str], typing.Optional[ticket_properties.TicketWorkType]]:
        """Parse a ticket file header into a title & work type member, if possible

        Returns:
            A tuple containing:
                1. The title, if any
                2. The work type, if any
        """
        try:
            return None, ticket_properties.TicketWorkType[header]
        # Indicates that the header isn't a bare work type (because it's not
        # a member of the enum)
        except KeyError:
            pass

        match = TICKET_HEADER_REGEX.match(header)
        # If either field isn't matched, the match will be falsy
        if match:
            # Because the regex only allows names of the work type members for
            # that match group, we can directly cast the match to a member
            return (
                match.group("title"),
                ticket_properties.TicketWorkType[match.group("work_type")],
            )

        # Default to interpreting the header as a title without a work type
        return header, None

    @property
    def display_title(self) -> str:
        """The title that's displayed"""
        return self.title or ""

    @property
    def title_and_type_header(self) -> str:
        """The header displayed at the top of the document

        The header contains the title and work type indicator, if either are set
        """
        work_type = ""
        if self.work_type is not None:
            work_type = self.work_type.name

        # Only join with a colon and space if both exist
        if work_type and self.display_title:
            return f"{work_type}: {self.display_title}"
        # Since `display_title` will be an empty string if there isn't a title,
        # this will properly display a bare work type
        elif work_type:
            return work_type
        # Finally, if there is no work type, just display the title, which can be
        # an empty string if no title is set
        else:
            return self.display_title

    @property
    def document(self) -> str:
        """The contents of the ticket file"""
        return "".join(
            ([f"{self.status.name}", "\n\n"] if self.status else [])
            + (
                [f"# {self.title_and_type_header}", "\n"]
                if self.title_and_type_header
                else []
            )
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
    def inverted_relationships(self) -> dict[int, ticket_properties.TicketRelationship]:
        """A map from ticket numbers to a union of all relationships this ticket has with that ticket

        Warning:
            Because this uses a `defaultdict`, it cannot be used to list all the
            tickets that this ticket has a relationship with, as `keys` will
            erroneously include any ticket numbers that were checked during
            searching
        """
        inverted_relationships: dict[
            int, ticket_properties.TicketRelationship
        ] = collections.defaultdict(lambda: ticket_properties.TicketRelationship(0))

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
