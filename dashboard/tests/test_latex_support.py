"""Publishing a bank's LaTeX support files.

A bank that prints with checkit-printit keeps its look in a
`skillcheckpoints.sty` at the bank root, and its own macros in a
`bank_helpers.sty` beside it. Neither was ever published, so the viewer's
Assessment export could not build a document that looked like the printed one
-- it had no way to reach the theme.

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
    <outcomes>
        <outcome>
            <title>Only</title>
            <slug>ONLY</slug>
            <path>outcomes/ONLY</path>
            <description>One outcome is enough to build a bank.</description>
        </outcome>
    </outcomes>
</bank>
"""

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

THEME = "\\ProvidesPackage{skillcheckpoints}\n\\newcommand{\\scmarker}{theme}\n"
HELPERS = "\\ProvidesPackage{bank_helpers}\n\\newcommand{\\bhmarker}{helpers}\n"


class LatexSupportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        outcome = os.path.join(self.tmp, "outcomes", "ONLY")
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
        self.write(os.path.join(self.tmp, "skillcheckpoints.sty"), THEME)
        self.build()

        self.assertTrue(os.path.isfile(self.asset("skillcheckpoints.sty")))
        with open(self.asset("skillcheckpoints.sty"), encoding="utf-8") as f:
            self.assertEqual(f.read(), THEME)

        declared = self.bank_json()["latex_support"]
        self.assertEqual(declared, [{
            "filename": "skillcheckpoints.sty",
            "role": "theme",
            "path": "assets/skillcheckpoints.sty",
        }])

    def test_load_order_puts_the_theme_before_the_bank_macros(self):
        """The bank's macros may build on the theme, so they load after it.

        Declaring them as a list is what carries that; a consumer reading a
        dict would have to know the order from somewhere else.
        """
        self.write(os.path.join(self.tmp, "skillcheckpoints.sty"), THEME)
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
        self.assertFalse(os.path.exists(self.asset("skillcheckpoints.sty")))

    def test_removing_the_theme_removes_the_published_copy(self):
        """Otherwise the site keeps serving a theme the bank no longer has."""
        theme_path = os.path.join(self.tmp, "skillcheckpoints.sty")
        self.write(theme_path, THEME)
        self.build()
        self.assertTrue(os.path.isfile(self.asset("skillcheckpoints.sty")))

        os.remove(theme_path)
        self.build()

        self.assertFalse(os.path.exists(self.asset("skillcheckpoints.sty")))
        self.assertEqual(self.bank_json()["latex_support"], [])

    def test_an_edited_theme_republishes(self):
        """The published copy tracks the bank's, not the first build's."""
        theme_path = os.path.join(self.tmp, "skillcheckpoints.sty")
        self.write(theme_path, THEME)
        self.build()

        self.write(theme_path, THEME + "\\newcommand{\\second}{edited}\n")
        self.build()

        with open(self.asset("skillcheckpoints.sty"), encoding="utf-8") as f:
            self.assertIn("second", f.read())


if __name__ == "__main__":
    unittest.main()
