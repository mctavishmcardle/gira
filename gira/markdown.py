import typing

import marko
import marko.md_renderer


def get_single_element_text(element: marko.element.Element) -> str:
    """Get the text from a single element

    Used for things like headings and paragraphs
    """
    return element.children[0].children


def render_element_list(elements: list[marko.element.Element]) -> str:
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
    link_element = marko.inline_parser.parse(
        f"[]({destination}{title})", [marko.inline.LinkOrEmph], fallback=None
    )[0]

    return link_element.dest, link_element.title
