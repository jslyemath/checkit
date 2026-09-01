import textwrap

CHECKIT_NS = "{https://checkit.clontz.org}"
SPATEXT_NS = "{https://spatext.clontz.org}"

def optional_text(ele, tag):
    """Text of an *optional* CheckIt-namespaced child element, or None.

    Unlike <title>/<slug>/<path>, optional elements must not blow up when a bank
    predates them -- an older bank.xml simply doesn't have the element, and the
    caller falls back. Returns None for absent, empty, and whitespace-only.

    The text is dedented and stripped because these hold free prose that authors
    write across several lines inside an indented XML document; without dedent,
    every line after the first would carry the surrounding indentation into the
    output.
    """
    if ele is None:
        return None
    found = ele.find(f"{CHECKIT_NS}{tag}")
    if found is None or found.text is None:
        return None
    return textwrap.dedent(found.text).strip() or None


def has_flag(ele, tag):
    """Whether an *optional* empty CheckIt-namespaced child element is present.

    For flags rather than values: `<frozen/>` says something by existing, and
    has no text for `optional_text` to return. An older bank.xml simply lacks
    the element and gets False.
    """
    if ele is None:
        return False
    return ele.find(f"{CHECKIT_NS}{tag}") is not None
