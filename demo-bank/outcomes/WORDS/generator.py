# Demonstrates math embedded *inside* a generated sentence.
#
# SpaTeXt normally wants math marked up structurally, e.g.
#   <p>What is <m>3x</m> when <m>x=2</m>?</p>
# which works when the template author knows where the math goes. In a word
# problem the generator decides the sentence shape at runtime, so the template
# cannot know. Here the generator emits the whole sentence -- <m> tags and all --
# and the template injects it with Mustache's triple brace, which does not
# HTML-escape. The parsed SpaTeXt then contains real <m> elements, so every
# output format (viewer, HTML, LaTeX, PreTeXt) handles it the usual way.
#
# The one rule: the emitted string must be valid XML. Bare & and < inside math
# have to be written &amp; and &lt;.
import bank_helpers as bh

NAMES = ["Avery", "Blake", "Casey", "Devon", "Emerson", "Harper"]
ITEMS = [("notebook", 3), ("binder", 5), ("marker", 2), ("folder", 1)]

class Generator(BaseGenerator):
    def data(self):
        buyer, friend = sample(NAMES, 2)
        item, unit = choice(ITEMS)
        count = randrange(4, 13)
        extra = randrange(2, 9)
        total = unit * count + extra

        # Two sentence shapes, so the math does not sit in a fixed position.
        if choice([True, False]):
            sentence = (
                f"{buyer} bought <m>{count}</m> {item}s at <m>{bh.money(unit)}</m> "
                f"each and paid an extra <m>{bh.money(extra)}</m> in tax. "
                f"How much did {buyer} spend in all?"
            )
        else:
            sentence = (
                f"After paying <m>{bh.money(extra)}</m> in tax, {buyer} spent "
                f"<m>{bh.money(total)}</m> on {bh.spell(count)} {item}s. "
                f"If every {item} cost the same, what did {friend} pay for one?"
            )

        return {
            "sentence": sentence,
            "answer": bh.money(total),
            "unit": bh.money(unit),
            "parts": bh.readable_list([f"{count} {item}s", "tax"]),
        }
