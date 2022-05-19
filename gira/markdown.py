import typing

import marko
import marko.md_renderer


def get_single_element_text(element: marko.block.BlockElement) -> str:
    """Get the text from a single element

    Used for things like headings and paragraphs
    """
    return element.children[0].children


def render_element_list(elements: list[marko.block.BlockElement]) -> str:
    """Render a list of elements to text"""
    with marko.md_renderer.MarkdownRenderer() as renderer:
        return "".join(renderer.render(element) for element in elements)


def parse_link_components(
    destination: str, title: typing.Optional[str]
) -> tuple[str, typing.Optional[str]]:
    """Properly parse the components of a link

    When `marko` parses the link reference definitions in a document, the
    `link_ref_defs` map it creates doesn't fully parse out the destination &
    title of that link. This extracts those components so they can be used.

    Args:
        destination: The incompletely-parsed destination string
        title: The incompletely-parsed title string, if any

    Returns:
        A tuple containing:
            1. The properly-parsed destination string
            2. The properly-parsed title string, if any
    """
    # If no title was matched in the ref def element, then we don't want to
    # erroneously create one when parsing it
    if title is not None:
        # The title must be separated from the destination by at least one space
        title = f" {title}"
    else:
        title = ""

    # Create a fake markdown link & then parse it; the resulting element instance
    # will have the proper destination & title
    # Need to mess with types a bit, because `parse` is built for generic parsing
    # of full documents
    link_element = typing.cast(
        typing.Type[marko.inline.Link],
        marko.inline_parser.parse(
            f"[]({destination}{title})",
            # `Link`s are virtual elements which can be produced by parsing but
            # aren't accepteed as an element type to parse on their own
            [marko.inline.LinkOrEmph],
            # This should fail if it can't parse a title out of what we've created,
            # so pass in `None`, which definitely won't work, as the fallback
            fallback=typing.cast(typing.Type[marko.inline.InlineElement], None),
        )[0],
    )

    return link_element.dest, link_element.title
