"""Faults the 2026-11-16 review found by reading, fixed 2026-11-17.

None of these had shipped anything wrong that anyone saw. Each test was run
against the code before its fix and failed there; see "The review's smaller
items" in CODEBASE_NOTES.md.
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkit.bank import Bank
from checkit.exercise import stylesheet
from checkit.wrapper.wrapper import CheckIt, latex, set_random_seed

BANK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Reading</title>
    <slug>reading</slug>
    <url>https://example.org</url>
    <latex-support>
        <file path="support/real.sty" role="theme"/>
    </latex-support>
    <color_map>
        <category prefix="A" color="Violet"/>
    </color_map>
    <outcomes>
        <outcome>
            <title>A</title>
            <slug>A1</slug>
            <path>outcomes/A1</path>
            <description>{description}</description>
        </outcome>
    </outcomes>
</bank>
"""

TEMPLATE = """<knowl mode="exercise" xmlns="https://spatext.clontz.org" version="0.3">
    <content><p>{body}</p></content>
</knowl>
"""


class _ABank(unittest.TestCase):
    """A one-outcome bank whose seeds.json is written by hand."""

    description = "plain"
    body = "{{{figure}}}"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        out = os.path.join(self.tmp, "outcomes", "A1")
        os.makedirs(out)
        with open(os.path.join(self.tmp, "bank.xml"), "w", encoding="utf-8") as f:
            f.write(BANK_XML.format(description=self.description))
        self.template_path = os.path.join(out, "template.xml")
        self.write_template(self.body)

    def write_template(self, body):
        with open(self.template_path, "w", encoding="utf-8") as f:
            f.write(TEMPLATE.format(body=body))

    def seeds(self, values):
        gen = os.path.join(self.tmp, "assets", "A1", "generated")
        os.makedirs(gen, exist_ok=True)
        with open(os.path.join(gen, "seeds.json"), "w", encoding="utf-8") as f:
            json.dump({"generated_on": "now",
                       "seeds": [{"seed": i, "data": d} for i, d in enumerate(values)]}, f)

    def bank(self):
        return Bank(self.tmp)


class AFigureInAnyVersionNeedsRemote(_ABank):
    """has_images() rendered seed 0 alone, so a figure only some versions draw
    let the build through without --remote, and those versions published
    links to nowhere."""

    def test_a_figure_only_in_a_later_version(self):
        self.seeds([{"figure": "no figure"}] * 5
                   + [{"figure": '<image source="p.png"/>'}])
        self.assertTrue(self.bank().outcomes()[0].has_images())

    def test_no_figure_anywhere(self):
        self.seeds([{"figure": "no figure"}] * 6)
        self.assertFalse(self.bank().outcomes()[0].has_images())


class AFigureInTheTemplate(_ABank):
    body = '<!-- <image source="old.png"/> --> {{x}}'

    def test_one_inside_a_comment_does_not_count(self):
        self.seeds([{"x": 1}])
        self.assertFalse(self.bank().outcomes()[0].has_images())

    def test_one_outside_does(self):
        self.write_template('{{x}} <tikz-image source="fig"/>')
        self.seeds([{"x": 1}])
        self.assertTrue(self.bank().outcomes()[0].has_images())


class BankXmlIsReadWhereItSaysSo(_ABank):
    """<category> and <file> were found anywhere in bank.xml."""

    description = ('see <category prefix="A" color="Red"/> and '
                   '<file path="support/stray.sty"/>')

    def test_only_the_declared_ones(self):
        # The description holds the stray elements as XML, which is what a
        # template fragment or a copied example in bank.xml would look like.
        self.seeds([{"figure": ""}])
        bank = self.bank()
        self.assertEqual(bank.color("A1"), "Violet")
        self.assertEqual([p for p, _ in bank._declared_support], ["support/real.sty"])


class ATemplateEditedMidProcessIsSeen(_ABank):
    """The parsed template is cached; editing the file must still show."""

    body = "first {{x}}"

    def test(self):
        self.seeds([{"x": 1}])
        ex = self.bank().outcomes()[0].exercises()[0]
        self.assertIn("first 1", ex.spatext())
        self.write_template("second {{x}}")
        self.assertIn("second 1", ex.spatext())


class StylesheetsAreCompiledOncePerThread(unittest.TestCase):

    def test_same_object_in_one_thread(self):
        self.assertIs(stylesheet("latex.xsl"), stylesheet("latex.xsl"))

    def test_a_different_one_in_another(self):
        mine = stylesheet("latex.xsl")
        theirs = []
        t = threading.Thread(target=lambda: theirs.append(stylesheet("latex.xsl")))
        t.start()
        t.join()
        self.assertIsNot(mine, theirs[0])


class VarsPrintTheirDisplayNames(unittest.TestCase):
    """CheckIt.vars dropped the names it was given, so the symbols would have
    printed as `q_mi_var_123456_0`. Sage's original passes latex_name."""

    def test_printed(self):
        set_random_seed(1)
        x, y = CheckIt.vars("x", "y")
        self.assertIn(latex(x + y), ("x + y", "y + x"))
        self.assertEqual(latex(3 * x ** 2), "3 x^{2}")

    def test_order_varies(self):
        orders = set()
        for seed in range(40):
            set_random_seed(seed)
            x, y = CheckIt.vars("x", "y")
            orders.add(latex(x + y))
        self.assertEqual(orders, {"x + y", "y + x"})

    def test_in_a_fixed_order_when_asked(self):
        orders = set()
        for seed in range(40):
            set_random_seed(seed)
            a, b = CheckIt.vars("a", "b", random_order=False)
            orders.add(latex(a + b))
        self.assertEqual(orders, {"a + b"})


if __name__ == "__main__":
    unittest.main()
