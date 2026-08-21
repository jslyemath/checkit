# Demonstrates two things a generator could not do before:
#   * `import` a helper module from the bank root (slye_demo)
#   * branch on `self.seed`, which is what lets a fixed, hand-written problem
#     serve the first len(CURATED) versions while higher seeds -- including
#     the ones printed assessments draw from -- are chosen randomly.
#
#     Note this list is shorter than the number of versions the viewer exposes,
#     so the later public versions repeat. A real bank using this pattern would
#     write one problem per public seed.
#
# The pattern matters whenever a skill cannot be randomized algorithmically and
# the problems have to be written by hand.
import bank_helpers as bh

CURATED = [
    ("<m>7 + 0 = 7</m>", "additive identity"),
    (r"<m>5 \cdot 1 = 5</m>", "multiplicative identity"),
    ("<m>3 + 4 = 4 + 3</m>", "commutative property of addition"),
    (r"<m>6 \cdot 2 = 2 \cdot 6</m>", "commutative property of multiplication"),
    ("<m>(1 + 2) + 3 = 1 + (2 + 3)</m>", "associative property of addition"),
    (r"<m>(2 \cdot 3) \cdot 4 = 2 \cdot (3 \cdot 4)</m>", "associative property of multiplication"),
    ("<m>4(x + 5) = 4x + 20</m>", "distributive property"),
    (r"<m>9 \cdot 0 = 0</m>", "zero product property"),
    ("<m>8 + (-8) = 0</m>", "additive inverse"),
    (r"<m>3 \cdot \frac{1}{3} = 1</m>", "multiplicative inverse"),
    ("<m>x + 0 = x</m>", "additive identity"),
    (r"<m>1 \cdot y = y</m>", "multiplicative identity"),
    ("<m>a + b = b + a</m>", "commutative property of addition"),
    ("<m>mn = nm</m>", "commutative property of multiplication"),
    ("<m>(p + q) + r = p + (q + r)</m>", "associative property of addition"),
    ("<m>(uv)w = u(vw)</m>", "associative property of multiplication"),
    ("<m>7(a - 3) = 7a - 21</m>", "distributive property"),
    (r"<m>0 \cdot t = 0</m>", "zero product property"),
    ("<m>k + (-k) = 0</m>", "additive inverse"),
    (r"<m>5 \cdot \frac{1}{5} = 1</m>", "multiplicative inverse"),
]

class Generator(BaseGenerator):
    def data(self):
        if self.seed < len(CURATED):
            # The first seeds, in a
            # fixed order, so nothing is missed and nothing repeats.
            statement, prop = CURATED[self.seed]
            provenance = "curated"
        else:
            # Higher seeds -- what printed assessments draw from -- pick freely.
            statement, prop = choice(CURATED)
            provenance = "randomly selected"
        return {
            "statement": statement,
            "property": prop,
            "provenance": provenance,
            "seed_shown": bh.spell(self.seed) if self.seed < 13 else str(self.seed),
        }
