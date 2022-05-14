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
