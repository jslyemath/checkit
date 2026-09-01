"""`<frozen/>`: an outcome whose seeds must not be regenerated.

mat-106's W1 and W1-E are homework students are working through. Replacing
their seeds.json changes the problems underneath a half-finished assignment,
and it is unrecoverable without the previous file from git. A note in the
codebase notes asked people to remember; this is the mechanism that means they
do not have to.

The tests that matter are the negative ones: that a frozen outcome survives
`-r`, that thawing it is possible but must be deliberate, and -- the one that
would make the whole thing worthless -- that everything else still regenerates
normally.
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
from checkit.bank import Bank

BANK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Freeze Test</title>
    <slug>freeze-test</slug>
    <url>https://example.org</url>
    <outcomes>
        <outcome>
            <title>Frozen</title>
            <slug>FROZEN</slug>
            <path>outcomes/FROZEN</path>
            <description>Students are working through this one.</description>
            <frozen/>
        </outcome>
        <outcome>
            <title>Thawed</title>
            <slug>THAWED</slug>
            <path>outcomes/THAWED</path>
            <description>Safe to regenerate.</description>
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

# Generation is reproducible: the wrapper seeds `random` before each call, so
# re-running an unchanged generator yields byte-identical data. That is the
# whole point of seeds, and it means a regeneration is only *visible* once the
# generator itself changes -- which is also the real hazard. Edit a generator,
# run -r, and every student's version moves.
#
# So the fixture ships two generators and swaps them, rather than trying to
# detect a rewrite that changes nothing.
GENERATOR = """import random


class Generator(BaseGenerator):
    def data(self):
        return {"n": random.randint(0, 10**9)}
"""

EDITED_GENERATOR = """import random


class Generator(BaseGenerator):
    def data(self):
        return {"n": "EDITED-" + str(random.randint(0, 10**9))}
"""


class FrozenTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for slug in ("FROZEN", "THAWED"):
            d = os.path.join(self.tmp, "outcomes", slug)
            os.makedirs(d)
            with open(os.path.join(d, "template.xml"), "w", encoding="utf-8") as f:
                f.write(TEMPLATE)
            with open(os.path.join(d, "generator.py"), "w", encoding="utf-8") as f:
                f.write(GENERATOR)
        with open(os.path.join(self.tmp, "bank.xml"), "w", encoding="utf-8") as f:
            f.write(BANK_XML)
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        # A first build, so there is something to protect.
        self.run_cli()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        return CliRunner().invoke(main, ["generate", "-a", "50", *args])

    def seeds(self, slug):
        path = os.path.join(self.tmp, "assets", slug, "generated", "seeds.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)["seeds"]

    def values(self, slug):
        return [e["data"]["n"] for e in self.seeds(slug)]

    def edit_generators(self):
        """Simulate the thing freezing actually guards against."""
        for slug in ("FROZEN", "THAWED"):
            path = os.path.join(self.tmp, "outcomes", slug, "generator.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(EDITED_GENERATOR)


class TheFlagIsRead(unittest.TestCase):
    def test_bank_xml_frozen_element_sets_the_attribute(self):
        tmp = tempfile.mkdtemp()
        try:
            for slug in ("FROZEN", "THAWED"):
                d = os.path.join(tmp, "outcomes", slug)
                os.makedirs(d)
                with open(os.path.join(d, "template.xml"), "w", encoding="utf-8") as f:
                    f.write(TEMPLATE)
            with open(os.path.join(tmp, "bank.xml"), "w", encoding="utf-8") as f:
                f.write(BANK_XML)
            bank = Bank(tmp)
            by_slug = {o.slug: o for o in bank.outcomes()}
            self.assertTrue(by_slug["FROZEN"].frozen)
            self.assertFalse(by_slug["THAWED"].frozen)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_bank_predating_the_flag_is_not_frozen(self):
        """An older bank.xml has no <frozen/>; absence must mean False, not an
        exception."""
        tmp = tempfile.mkdtemp()
        try:
            d = os.path.join(tmp, "outcomes", "THAWED")
            os.makedirs(d)
            with open(os.path.join(d, "template.xml"), "w", encoding="utf-8") as f:
                f.write(TEMPLATE)
            with open(os.path.join(tmp, "bank.xml"), "w", encoding="utf-8") as f:
                f.write(BANK_XML.replace("<frozen/>", ""))
            self.assertFalse(any(o.frozen for o in Bank(tmp).outcomes()))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RegenerationIsRefused(FrozenTestCase):
    def test_an_edited_generator_does_not_move_a_frozen_outcome(self):
        """The hazard in full: someone edits a generator and runs -r while
        students are mid-assignment."""
        before = self.values("FROZEN")
        self.edit_generators()
        result = self.run_cli("-r")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(before, self.values("FROZEN"))
        self.assertFalse(any(str(v).startswith("EDITED") for v in self.values("FROZEN")))

    def test_the_refusal_is_announced(self):
        """A -r that silently did less than asked is its own hazard."""
        result = self.run_cli("-r")
        self.assertIn("SKIPPING FROZEN", result.output)
        self.assertIn("--thaw FROZEN", result.output)

    def test_everything_else_still_regenerates(self):
        """The check that stops this being a footgun of its own: freezing one
        outcome must not quietly freeze the bank."""
        self.edit_generators()
        self.run_cli("-r")
        self.assertTrue(all(str(v).startswith("EDITED") for v in self.values("THAWED")))

    def test_a_frozen_outcome_still_appears_in_bank_json(self):
        """Frozen means "keep these versions", not "drop this outcome"."""
        self.run_cli("-r")
        path = os.path.join(self.tmp, "assets", "bank.json")
        with open(path, encoding="utf-8") as f:
            slugs = [o["slug"] for o in json.load(f)["outcomes"]]
        self.assertEqual(sorted(slugs), ["FROZEN", "THAWED"])


class ThawingIsDeliberate(FrozenTestCase):
    def test_thaw_permits_regeneration(self):
        self.edit_generators()
        result = self.run_cli("-r", "--thaw", "FROZEN")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(all(str(v).startswith("EDITED") for v in self.values("FROZEN")))

    def test_thawing_an_unfrozen_outcome_is_refused(self):
        """Otherwise someone believes an outcome is protected when it is not."""
        result = self.run_cli("-r", "--thaw", "THAWED")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not marked", result.output)

    def test_thawing_an_unknown_slug_is_refused(self):
        result = self.run_cli("-r", "--thaw", "NOPE")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("NOPE", result.output)

    def test_thaw_is_repeatable(self):
        result = self.run_cli("-r", "--thaw", "FROZEN", "--thaw", "FROZEN")
        self.assertEqual(result.exit_code, 0, result.output)


class WithoutRegenerate(FrozenTestCase):
    def test_a_plain_generate_is_unaffected(self):
        """Freezing blocks regeneration, not rendering. A stylesheet fix has to
        be able to reach a frozen outcome's published HTML without anyone
        thawing it -- the problems do not change, only how they are drawn."""
        before = self.values("FROZEN")
        self.edit_generators()
        result = self.run_cli()
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(before, self.values("FROZEN"))


if __name__ == "__main__":
    unittest.main()
