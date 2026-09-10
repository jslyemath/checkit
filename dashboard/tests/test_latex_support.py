r"""Publishing a bank's LaTeX support files.

Raw docstring: it names LaTeX commands, and \usepackage begins with \u, which
Python otherwise reads as the start of a unicode escape.

A bank may carry LaTeX that the viewer's Assessment export needs in order to
build a document resembling the printed handouts. Two sources:

  - files another tool installed, which the bank declares in `bank.xml` under
    <latex-support>. CheckIt publishes them without knowing what wrote them.
  - `bank_helpers.sty`, which CheckIt scaffolds itself.

The declaration is the part worth covering. CheckIt deliberately holds no
constant naming another tool's file, so an undeclared file is not published no
matter what it is called -- and a declared path that is missing from disk is
skipped rather than raising, because installing it is the other tool's job and
a fresh clone is a normal state.

Source path and published name differ too: installed in a folder, published
flat, because \usepackage takes a package name rather than a path.

These tests cover what a consumer relies on: that the files reach `assets/`,
that `bank.json` declares them in the order they must be loaded, that a bank
without them is unaffected, and -- the one that bites later -- that removing a
theme removes the published copy too.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from click.testing import CliRunner

from checkit.__main__ import main

BANK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Support Test</title>
    <slug>support-test</slug>
    <url>https://example.org</url>
    <latex-support>
        <file path="printit/printit.sty" role="theme"/>
    </latex-support>
    <color_map>
        <category prefix="F" color="Teal" />
        <category prefix="FCP" color="Sepia" />
        <category prefix="W" color="Violet" />
    </color_map>
    <outcomes>
        <outcome>
            <title>Only</title>
            <slug>ONLY</slug>
            <path>outcomes/ONLY</path>
            <description>One outcome is enough to build a bank.</description>
        </outcome>
        <outcome>
            <title>Checkpoint</title>
            <slug>FCP</slug>
            <path>outcomes/FCP</path>
            <description>Claims a colour of its own, against the F prefix.</description>
        </outcome>
        <outcome>
            <title>Family</title>
            <slug>F2-E</slug>
            <path>outcomes/F2-E</path>
            <description>Covered by the F prefix.</description>
        </outcome>
    </outcomes>
</bank>
"""

# The declaration the fixture adds, and the same file without it -- one
# test removes it to check an undeclared file stays unpublished.
NEW_XML = """    <url>https://example.org</url>
    <latex-support>
        <file path="printit/printit.sty" role="theme"/>
    </latex-support>
    <color_map>"""
OLD_XML = """    <url>https://example.org</url>
    <color_map>"""

TEMPLATE = """<?xml version='1.0' encoding='UTF-8'?>
<knowl mode="exercise" xmlns="https://spatext.clontz.org" version="0.3">
    <content><p>Value: {{n}}</p></content>
    <outtro><p>{{n}}</p></outtro>
</knowl>
"""

GENERATOR = """import random


class Generator(BaseGenerator):
    def data(self):
        return {"n": random.randint(0, 10**9)}
"""

THEME = "\\ProvidesPackage{printit}\n\\newcommand{\\scmarker}{theme}\n"
HELPERS = "\\ProvidesPackage{bank_helpers}\n\\newcommand{\\bhmarker}{helpers}\n"


class LatexSupportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for slug in ("ONLY", "FCP", "F2-E"):
            outcome = os.path.join(self.tmp, "outcomes", slug)
            os.makedirs(outcome)
            self.write(os.path.join(outcome, "template.xml"), TEMPLATE)
            self.write(os.path.join(outcome, "generator.py"), GENERATOR)
        self.write(os.path.join(self.tmp, "bank.xml"), BANK_XML)
        self.cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def theme_path(self):
        """Where checkit-printit installs a bank's theme."""
        return os.path.join(self.tmp, "printit", "printit.sty")

    def write_theme(self, text):
        os.makedirs(os.path.dirname(self.theme_path()), exist_ok=True)
        self.write(self.theme_path(), text)

    def build(self):
        result = CliRunner().invoke(main, ["generate", "-a", "50"])
        self.assertEqual(result.exit_code, 0, result.output)

    def bank_json(self):
        with open(os.path.join(self.tmp, "assets", "bank.json"),
                  encoding="utf-8") as f:
            return json.load(f)

    def asset(self, filename):
        return os.path.join(self.tmp, "assets", filename)

    def test_theme_is_copied_and_declared(self):
        self.write_theme(THEME)
        self.build()

        self.assertTrue(os.path.isfile(self.asset("printit.sty")))
        with open(self.asset("printit.sty"), encoding="utf-8") as f:
            self.assertEqual(f.read(), THEME)

        declared = self.bank_json()["latex_support"]
        self.assertEqual(declared, [{
            "filename": "printit.sty",
            "role": "theme",
            "path": "assets/printit.sty",
        }])

    def test_load_order_puts_the_theme_before_the_bank_macros(self):
        """The bank's macros may build on the theme, so they load after it.

        Declaring them as a list is what carries that; a consumer reading a
        dict would have to know the order from somewhere else.
        """
        self.write_theme(THEME)
        self.write(os.path.join(self.tmp, "bank_helpers.sty"), HELPERS)
        self.build()

        roles = [e["role"] for e in self.bank_json()["latex_support"]]
        self.assertEqual(roles, ["theme", "helpers"])

    def test_helpers_alone_are_published(self):
        """A bank may have macros without having a theme."""
        self.write(os.path.join(self.tmp, "bank_helpers.sty"), HELPERS)
        self.build()

        declared = self.bank_json()["latex_support"]
        self.assertEqual([e["filename"] for e in declared], ["bank_helpers.sty"])
        self.assertTrue(os.path.isfile(self.asset("bank_helpers.sty")))

    def test_a_bank_with_neither_declares_an_empty_list(self):
        """Not a fault -- most banks have no theme, and must be unaffected.

        The key is still present, so a consumer can tell "this bank ships
        nothing" from "this bank predates the feature".
        """
        self.build()

        self.assertEqual(self.bank_json()["latex_support"], [])
        self.assertFalse(os.path.exists(self.asset("printit.sty")))

    def test_removing_the_theme_removes_the_published_copy(self):
        """Otherwise the site keeps serving a theme the bank no longer has."""
        theme_path = self.theme_path()
        self.write_theme(THEME)
        self.build()
        self.assertTrue(os.path.isfile(self.asset("printit.sty")))

        os.remove(theme_path)
        self.build()

        self.assertFalse(os.path.exists(self.asset("printit.sty")))
        self.assertEqual(self.bank_json()["latex_support"], [])

    def test_a_renamed_theme_stops_being_published(self):
        """The case the first version of this cleanup missed.

        It only removed files LATEX_SUPPORT still named, so renaming the theme
        left the old copy served forever -- nothing named it any more, so
        nothing swept it up. The sweep is by directory for that reason.
        """
        self.write_theme(THEME)
        self.build()
        stale = self.asset("skillcheckpoints.sty")
        self.write(stale, "% a theme from a previous name\n")

        self.build()

        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.isfile(self.asset("printit.sty")))

    def test_an_undeclared_file_is_not_published(self):
        """CheckIt names no tool's file, so an undeclared one is invisible to
        it however it is spelled. This is what keeps CheckIt free of hooks for
        tools that may never be installed."""
        self.write(os.path.join(self.tmp, "bank.xml"),
                   BANK_XML.replace(NEW_XML, OLD_XML))
        self.write_theme(THEME)
        self.build()

        self.assertEqual(self.bank_json()["latex_support"], [])
        self.assertFalse(os.path.exists(self.asset("printit.sty")))

    def test_a_declared_but_missing_file_is_skipped(self):
        """A bank cloned before the installing tool has run. Normal, not
        broken -- so the build carries on without it."""
        self.build()

        self.assertEqual(self.bank_json()["latex_support"], [])

    def test_the_longest_matching_colour_prefix_wins(self):
        """FCP must take its own entry, not the one for F.

        The rule matters because a themed export in the browser and a printed
        handout both colour a skill box from this map. If they resolved it
        differently, the mismatch would only show up with the two side by side.
        """
        self.build()

        colors = {o["slug"]: o.get("color") for o in self.bank_json()["outcomes"]}
        self.assertEqual(colors["FCP"], "Sepia")
        self.assertEqual(colors["F2-E"], "Teal")

    def test_an_outcome_matching_no_prefix_has_no_colour(self):
        """Absent, not empty -- absent means "the theme's default"."""
        self.build()

        only = next(o for o in self.bank_json()["outcomes"] if o["slug"] == "ONLY")
        self.assertNotIn("color", only)

    def test_an_edited_theme_republishes(self):
        """The published copy tracks the bank's, not the first build's."""
        theme_path = self.theme_path()
        self.write_theme(THEME)
        self.build()

        self.write_theme(THEME + "\\newcommand{\\second}{edited}\n")
        self.build()

        with open(self.asset("printit.sty"), encoding="utf-8") as f:
            self.assertIn("second", f.read())


if __name__ == "__main__":
    unittest.main()
