"""`checkit generate -o SLUG` must narrow what is regenerated, nothing else.

The command used to filter `Bank._outcomes` down to the requested outcome and
then call `write_json()`, which serialises whatever outcomes the Bank can see.
A single-outcome regeneration therefore rewrote bank.json to contain that
outcome alone, and the published site lost the other 27 until someone ran a
full generate. Nothing failed; the per-outcome seeds.json all survived. That is
the shape worth a guard: a filter applied one layer too high, where the damage
lands in a file nobody re-reads.

The same narrowing also skipped the missing-`remote` preflight for the
outcomes it filtered out, so a bank with figures could precompute HTML with
root-relative <img src> that 404s wherever it is displayed.

Reuses test_precompute's two-outcome fixture: PLAIN has no figures, FIGURED
does, which is exactly the pair both symptoms need.
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

from test_precompute import build_bank

REMOTE = "https://example.org/test-bank"


class OutcomeFilterTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bank = build_bank(self.tmp)
        self.cwd = os.getcwd()
        # Bank() defaults to path=".", and the CLI builds one with no argument.
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        return CliRunner().invoke(main, ["generate", *args])

    def bank_json(self):
        with open(os.path.join(self.tmp, "assets", "bank.json"), encoding="utf-8") as f:
            return json.load(f)


class ManifestSurvives(OutcomeFilterTestCase):
    def test_one_outcome_leaves_the_rest_in_bank_json(self):
        result = self.run_cli("-o", "PLAIN", "--remote", REMOTE)
        self.assertEqual(result.exit_code, 0, result.output)
        slugs = [o["slug"] for o in self.bank_json()["outcomes"]]
        self.assertEqual(sorted(slugs), ["FIGURED", "PLAIN"])

    def test_the_untouched_outcome_keeps_its_exercises(self):
        """A manifest entry with an empty exercise list would be the same bug
        wearing the outcome's name."""
        self.run_cli("-o", "PLAIN", "--remote", REMOTE)
        figured = next(
            o for o in self.bank_json()["outcomes"] if o["slug"] == "FIGURED"
        )
        self.assertTrue(figured["exercises"])

    def test_all_is_still_the_default(self):
        result = self.run_cli("--remote", REMOTE)
        self.assertEqual(result.exit_code, 0, result.output)
        slugs = [o["slug"] for o in self.bank_json()["outcomes"]]
        self.assertEqual(sorted(slugs), ["FIGURED", "PLAIN"])


class FilterStillFilters(OutcomeFilterTestCase):
    """Otherwise ManifestSurvives passes for the wrong reason -- a filter that
    does nothing also leaves every outcome in bank.json."""

    def dispatched(self, **kwargs):
        called = []

        def spy(outcome, original):
            def wrapper(*a, **kw):
                called.append(outcome.slug)
                return original(*a, **kw)
            return wrapper

        for o in self.bank.outcomes():
            o.generate_exercises = spy(o, o.generate_exercises)
        self.bank.generate_exercises(**kwargs)
        return called

    def test_only_the_named_outcome_is_regenerated(self):
        self.assertEqual(self.dispatched(only={"PLAIN"}), ["PLAIN"])

    def test_none_means_every_outcome(self):
        self.assertEqual(sorted(self.dispatched(only=None)), ["FIGURED", "PLAIN"])


class RepeatedOutcome(OutcomeFilterTestCase):
    """`-o` is repeatable, and `--thaw` beside it always was.

    While it took a single value, `-o A -o B` kept only B -- and the outcomes
    you thought you had named were regenerated anyway, at the default amount,
    because nothing had narrowed them. Nothing failed and nothing said so.
    """

    def test_two_outcomes_are_both_selected(self):
        result = self.run_cli("-o", "PLAIN", "-o", "FIGURED",
                              "--remote", REMOTE, "--no-precompute")
        self.assertEqual(result.exit_code, 0, result.output)

    def test_a_typo_among_several_is_still_refused(self):
        result = self.run_cli("-o", "PLAIN", "-o", "NOPE", "--remote", REMOTE)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("NOPE", result.output)

    def test_all_cannot_be_mixed_with_a_named_outcome(self):
        result = self.run_cli("-o", "ALL", "-o", "PLAIN", "--remote", REMOTE)
        self.assertNotEqual(result.exit_code, 0)

    def test_no_outcome_flag_still_means_every_outcome(self):
        result = self.run_cli("--remote", REMOTE, "--no-precompute")
        self.assertEqual(result.exit_code, 0, result.output)
        slugs = [o["slug"] for o in self.bank_json()["outcomes"]]
        self.assertEqual(sorted(slugs), ["FIGURED", "PLAIN"])


class PreflightStillRuns(OutcomeFilterTestCase):
    def test_missing_remote_is_caught_for_an_outcome_not_named(self):
        """FIGURED is not the outcome being regenerated, but its precomputed
        HTML still goes into bank.json, so it still needs an absolute base URL."""
        result = self.run_cli("-o", "PLAIN")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("FIGURED", str(result.exception))

    def test_no_precompute_needs_no_remote(self):
        result = self.run_cli("-o", "PLAIN", "--no-precompute")
        self.assertEqual(result.exit_code, 0, result.output)


class UnknownSlug(OutcomeFilterTestCase):
    def test_a_slug_that_matches_nothing_is_refused(self):
        """Regenerating nothing at all is indistinguishable from success."""
        result = self.run_cli("-o", "NOPE", "--remote", REMOTE)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("NOPE", result.output)

    def test_the_refusal_names_the_available_slugs(self):
        result = self.run_cli("-o", "NOPE", "--remote", REMOTE)
        self.assertIn("PLAIN", result.output)
        self.assertIn("FIGURED", result.output)

    def test_slug_matching_stays_case_insensitive(self):
        result = self.run_cli("-o", "plain", "--remote", REMOTE)
        self.assertEqual(result.exit_code, 0, result.output)


if __name__ == "__main__":
    unittest.main()
