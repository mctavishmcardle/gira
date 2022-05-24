import collections
import dataclasses
import functools
import os
import pathlib
import re
import typing

import git
import marko

from gira import ticket, ticket_properties

# The individual items in ticket search inclusion & exclusion lists
V = typing.TypeVar("V")


# A combination of a target ticket number & a relationship with that ticket
SpecificTicketRelationship = tuple[int, ticket_properties.TicketRelationship]


@dataclasses.dataclass
class SearchConditions:
    """A container for searching collections of tickets"""

    numbers: list[int]
    exclude_numbers: list[int]
    groups: list[pathlib.Path]
    exclude_groups: list[pathlib.Path]
    statuses: list[ticket_properties.TicketStatus]
    exclude_statuses: list[ticket_properties.TicketStatus]
    work_types: list[ticket_properties.TicketWorkType]
    exclude_work_types: list[ticket_properties.TicketWorkType]
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
        test_ticket: ticket.Ticket,
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
            return bool(
                test_ticket.inverted_relationships[ticket_number] & relationship
            )

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

    def ticket_matches(self, test_ticket: ticket.Ticket) -> bool:
        """Does a ticket match the configured search criteira?"""
        return (
            self.matching_predicate(
                lambda number: test_ticket.number == number,
                self.numbers,
                self.exclude_numbers,
            )
            and self.matching_predicate(
                lambda group: test_ticket.is_in_group(group),
                self.groups,
                self.exclude_groups,
            )
            and self.matching_predicate(
                lambda status: test_ticket.status is status,
                self.statuses,
                self.exclude_statuses,
            )
            and self.matching_predicate(
                lambda work_type: test_ticket.work_type is work_type,
                self.work_types,
                self.exclude_work_types,
            )
            and self.matching_predicate(
                lambda regex: bool(regex.search(test_ticket.display_title)),
                self.titles,
                self.exclude_titles,
            )
            and self.matching_predicate(
                lambda regex: bool(regex.search(test_ticket.description)),
                self.descriptions,
                self.exclude_descriptions,
            )
            and self.matching_predicate(
                lambda regex: bool(regex.search(test_ticket.slug)),
                self.slugs,
                self.exclude_slugs,
            )
            and self.matching_predicate(
                self.match_ticket_relationship(test_ticket),
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
        ticket_path_components_by_number: dict[int, ticket_properties.PathComponents],
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

    def __missing__(self, key: int) -> ticket.Ticket:
        # Attempts to get tickets for
        path_components = self.ticket_path_components_by_number[key]

        # Parse the ticket file contents
        with open(self.tickets_dir / path_components.path) as ticket_file:
            document = marko.parse(ticket_file.read())
            (
                status,
                work_type,
                title,
                description,
                sections,
            ) = ticket.Ticket.parse_markdown_document(document)
            raw_relationships = ticket.Ticket.extract_document_relationships(document)

        # Only include relationships to tickets that actually exist
        relationships: ticket.RelationshipMap = collections.defaultdict(dict)
        for relationship_type, target_tickets in raw_relationships.items():
            for target_ticket_number, relationship_label in target_tickets.items():
                if target_ticket_number in self.ticket_path_components_by_number:
                    relationships[relationship_type][
                        target_ticket_number
                    ] = relationship_label

        return ticket.Ticket(
            number=path_components.number,
            slug=path_components.slug,
            group=path_components.group,
            status=status,
            work_type=work_type,
            title=title,
            description=description,
            sections=sections,
            relationships=relationships,
        )


class RepoManager:
    """Handles direct interaction with the `git` repo"""

    def __init__(self):
        self.repo = git.Repo(search_parent_directories=True)

    @property
    def staged_paths(self) -> list[pathlib.Path]:
        """The paths of files that have staged modifications"""
        return [
            pathlib.Path(diff.b_path)
            for diff in self.repo.index.diff(self.repo.head.commit)
        ]

    @property
    def unstaged_paths(self) -> list[pathlib.Path]:
        """The paths of tracked files that have unstaged modifications"""
        return [pathlib.Path(diff.b_path) for diff in self.repo.index.diff(None)]

    @property
    def untracked_paths(self) -> list[pathlib.Path]:
        """The paths of untracked files"""
        return [pathlib.Path(path) for path in self.repo.untracked_files]

    def get_branch(self, name: str, create: bool = True) -> typing.Optional[git.Head]:
        """Get the branch with the input name, optionally creating one if none exist

        Args:
            name: The name of the branch
            create: Should a branch be created if one with the input name does
                not exist?

        Returns:
            The `Head` corresponding to the named branch, or `None` if none exists
            and one was not created.
        """
        try:
            return self.repo.branches[name]
        # Indicates that the requested branch name doesn't exist
        except IndexError:
            if create:
                return self.repo.create_head(name)
            else:
                return None

    def branch_exists(self, branch_name: str) -> bool:
        """Does a branch with this name exist?"""
        return self.get_branch(branch_name, create=False) is not None

    @functools.cached_property
    def git_dir(self) -> pathlib.Path:
        """The root of the current repo"""
        return pathlib.Path(self.repo.working_tree_dir)

    def stage(self, path: pathlib.Path):
        """Stage any modifications to this file"""
        self.repo.index.add(str(path))

    def commit(self, message: str):
        """Commit any staged modifications"""
        self.repo.index.commit(message)


class NonexistentTicket(Exception):
    """A request was made for a ticket that doesn't exist"""

    def __init__(self, number: int) -> None:
        """
        Args:
            number: The ticket number that doesn't correspond to an existing ticket
        """
        self.number = number


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
        self.repo_manager = RepoManager()

        self._tickets_dir = tickets_dir
        self.search_conditions: typing.Optional[SearchConditions] = None

        self.lazy_ticket_store = LazyTicketStore(
            # Because this is a cached property, it's not actually accessed (so
            # the map isn't actually created) until it's needed
            self.ticket_path_components_by_number,
            self.tickets_dir,
        )

    def stage(self, target_ticket: ticket.Ticket):
        """Stage this ticket's file"""
        self.repo_manager.stage(self.relative_ticket_path(target_ticket))

    @functools.cached_property
    def staged_nonticket_files(self) -> list[pathlib.Path]:
        """Staged files that do not correspond to tickets"""
        return [
            path
            for path in self.repo_manager.staged_paths
            if not ticket_properties.PathComponents.is_ticket_file(path)
        ]

    @property
    def _unstaged_ticket_numbers(self) -> collections.abc.Iterator[int]:
        """The numbers of tickets which have unstaged modifications to their files"""
        for path in (
            self.repo_manager.unstaged_paths + self.repo_manager.untracked_paths
        ):
            try:
                yield ticket_properties.PathComponents.from_path(path).number
            except ticket_properties.MalformedTicket:
                continue

    @functools.cached_property
    def unstaged_ticket_numbers(self) -> list[int]:
        """The numbers of tickets which have unstaged modifications to their files"""
        return list(self._unstaged_ticket_numbers)

    @functools.cached_property
    def tickets_dir(self) -> pathlib.Path:
        """The ticket storage directory in the current repo"""
        if self._tickets_dir:
            return self._tickets_dir

        return self.repo_manager.git_dir / pathlib.Path(".gira")

    @property
    def _all_ticket_path_components(
        self,
    ) -> collections.abc.Iterator[ticket_properties.PathComponents]:
        """Yields all the valid ticket path component containers in the ticket dir"""
        for ticket_path in self.tickets_dir.rglob(
            f"*{ticket_properties.TICKET_FILE_SUFFIX}"
        ):
            try:
                yield ticket_properties.PathComponents.from_path(
                    ticket_path.relative_to(self.tickets_dir)
                )
            # Ignore any bad ticket files
            except ticket_properties.MalformedTicket:
                continue

    @functools.cached_property
    def all_ticket_path_components(self) -> list[ticket_properties.PathComponents]:
        """A list of all the valid ticket path component containers in the ticket dir"""
        return list(self._all_ticket_path_components)

    @functools.cached_property
    def ticket_path_components_by_number(
        self,
    ) -> dict[int, ticket_properties.PathComponents]:
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

    def get_ticket(self, number: int) -> ticket.Ticket:
        """Retrieve a ticket by number

        Args:
            number: The number whose ticket to get

        Raises:
            NonexistentTicket:
                If the number doesn't correspond to a ticket that actually exists
        """
        try:
            return self.lazy_ticket_store[number]
        except KeyError:
            raise NonexistentTicket(number)

    @property
    def _all_tickets(self) -> collections.abc.Iterator[ticket.Ticket]:
        """All tickets in the current repo"""
        for ticket_number in self.all_ticket_numbers:
            yield self.get_ticket(ticket_number)

    @functools.cached_property
    def all_tickets(self) -> list[ticket.Ticket]:
        """All tickets in the current repo"""
        return sorted(list(self._all_tickets), key=lambda ticket: ticket.number)

    def set_search_conditions(self, search_conditions: SearchConditions) -> None:
        """Set the conditions for ticket filtering"""
        self.search_conditions = search_conditions

    @property
    def _filtered_tickets(self) -> collections.abc.Iterator[ticket.Ticket]:
        """Tickets matching the set filtering conditions"""
        for ticket in self.all_tickets:
            if self.search_conditions and self.search_conditions.ticket_matches(ticket):
                yield ticket

    @functools.cached_property
    def filtered_tickets(self) -> list[ticket.Ticket]:
        """Tickets matching the set filtering conditions, if any"""
        return sorted(list(self._filtered_tickets), key=lambda ticket: ticket.number)

    @functools.cached_property
    def filtered_ticket_numbers(self) -> list[int]:
        """The numbers of tickets matching the set filtering conditions, if any"""
        return [filtered_ticket.number for filtered_ticket in self.filtered_tickets]

    def relative_ticket_path(self, existing_ticket: ticket.Ticket) -> pathlib.Path:
        """The path, from the current working directory, to the ticket file"""
        return pathlib.Path(os.path.relpath(self.tickets_dir / existing_ticket.path))

    def write(self, modified_ticket: ticket.Ticket, stage: bool):
        """Write the contents of a ticket to disk

        Args:
            modified_ticket: The ticket whose contents should be written out
            stage: Should the modifications be staged?
        """
        with self.relative_ticket_path(modified_ticket).open(
            mode="w"
        ) as modified_ticket_file:
            modified_ticket_file.write(modified_ticket.document)

        if stage:
            self.stage(modified_ticket)
