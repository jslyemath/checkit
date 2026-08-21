"""Tests for the precomputed derived formats emitted at generate time.

Browsers remove XSLT in Chrome 158 (2026-11-17), so the viewer will read these
instead of transforming SpaTeXt itself. The coverage is deliberately unequal --
three formats for the public seeds, two for the rest -- and unequal coverage is
what --image-seeds already got wrong once: the build succeeded, and the hole
only surfaced when a student met a broken figure. So most of what is asserted
here is *which seeds and formats exist*, and that a gap is declared rather than
silent.

Builds a real Bank from temporary files. No generator runs: Outcome loads from
seeds.json when it is present, so the fixture supplies one directly.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkit import (
    BUNDLE_FILENAME,
    BUNDLE_FORMATS,
    INLINE_FORMATS,
    PUBLIC_SEEDS,
)
from checkit.bank import Bank

import spatext_fixtures as fx

BANK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Test Bank</title>
    <slug>test-bank</slug>
    <url>https://example.org</url>
    <outcomes>
        <outcome>
            <title>Plain</title>
            <slug>PLAIN</slug>
            <path>outcomes/PLAIN</path>
            <description>An outcome with no figures.</description>
        </outcome>
        <outcome>
            <title>Figured</title>
            <slug>FIGURED</slug>
            <path>outcomes/FIGURED</path>
            <description>An outcome with an image.</description>
        </outcome>
    </outcomes>
</bank>
"""

SEED_COUNT = PUBLIC_SEEDS + 10  # enough to populate both tiers


def build_bank(root):
    """A two-outcome bank on disk, one with images and one without."""
    for slug, template in (("PLAIN", fx.MATH), ("FIGURED", fx.IMAGE)):
        odir = os.path.join(root, "outcomes", slug)
        os.makedirs(odir)
        with open(os.path.join(odir, "template.xml"), "w", encoding="utf-8") as f:
            f.write(template)

        gen = os.path.join(root, "assets", slug, "generated")
        os.makedirs(gen)
        seeds = {
            "seeds": [{"seed": i, "data": {}} for i in range(SEED_COUNT)],
            "generated_on": "2026-08-21T00:00:00+00:00",
        }
        with open(os.path.join(gen, "seeds.json"), "w", encoding="utf-8") as f:
            json.dump(seeds, f)

    with open(os.path.join(root, "bank.xml"), "w", encoding="utf-8") as f:
        f.write(BANK_XML)
    return Bank(root)


class PrecomputeTestCase(unittest.TestCase):
    REMOTE = "https://example.org/test-bank"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bank = build_bank(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bank_json(self):
        with open(os.path.join(self.tmp, "assets", "bank.json"), encoding="utf-8") as f:
            return json.load(f)

    def bundle(self, slug):
        path = os.path.join(self.tmp, "assets", slug, "generated", BUNDLE_FILENAME)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def exercises(self, doc, slug):
        outcome = next(o for o in doc["outcomes"] if o["slug"] == slug)
        return {e["seed"]: e for e in outcome["exercises"]}


class InlineTier(PrecomputeTestCase):
    def setUp(self):
        super().setUp()
        self.bank.write_json(remote=self.REMOTE)
        self.doc = self.bank_json()

    def test_public_seeds_carry_every_inline_format(self):
        exs = self.exercises(self.doc, "PLAIN")
        for seed in (0, 1, PUBLIC_SEEDS - 1):
            with self.subTest(seed=seed):
                for fmt in INLINE_FORMATS:
                    self.assertIn(fmt, exs[seed], f"seed {seed} is missing {fmt}")
                    self.assertTrue(exs[seed][fmt].strip())

    def test_non_public_seeds_are_not_inlined(self):
        """Inlining all 1000 seeds would multiply bank.json roughly tenfold for
        content only an instructor ever asks for."""
        exs = self.exercises(self.doc, "PLAIN")
        for seed in (PUBLIC_SEEDS, SEED_COUNT - 1):
            with self.subTest(seed=seed):
                self.assertEqual(sorted(exs[seed].keys()), ["data", "seed"])

    def test_inlined_html_is_the_base_form(self):
        """The viewer still applies its own subset filtering and KaTeX on top,
        so only subset='all', consumer='basic' is emitted."""
        html = self.exercises(self.doc, "PLAIN")[0]["html"]
        self.assertIn("stx-content", html)
        self.assertIn("stx-outtro", html)
        self.assertNotIn("<math", html)


class BundleTier(PrecomputeTestCase):
    def setUp(self):
        super().setUp()
        self.bank.write_json(remote=self.REMOTE)

    def test_bundle_covers_exactly_the_non_public_seeds(self):
        bundle = self.bundle("PLAIN")
        seeds = sorted(int(s) for s in bundle["seeds"])
        self.assertEqual(seeds[0], PUBLIC_SEEDS)
        self.assertEqual(seeds[-1], SEED_COUNT - 1)
        self.assertEqual(len(seeds), SEED_COUNT - PUBLIC_SEEDS)

    def test_bundle_carries_exactly_the_bundle_formats(self):
        entry = self.bundle("PLAIN")["seeds"][str(PUBLIC_SEEDS)]
        self.assertEqual(sorted(entry.keys()), sorted(BUNDLE_FORMATS))

    def test_pretext_is_absent_on_purpose(self):
        """PreTeXt's only consumer is the instructor tab, and the version picker
        cannot reach past PUBLIC_SEEDS -- so it would be dead weight here."""
        self.assertNotIn("pretext", BUNDLE_FORMATS)
        entry = self.bundle("PLAIN")["seeds"][str(PUBLIC_SEEDS)]
        self.assertNotIn("pretext", entry)

    def test_bundle_declares_its_own_range(self):
        bundle = self.bundle("PLAIN")
        self.assertEqual(bundle["first_seed"], PUBLIC_SEEDS)
        self.assertEqual(bundle["slug"], "PLAIN")


class CoverageDeclaration(PrecomputeTestCase):
    """A consumer must be able to ask 'was this emitted?' rather than infer it
    from finding nothing."""

    def test_declaration_matches_what_was_actually_emitted(self):
        self.bank.write_json(remote=self.REMOTE)
        declared = self.bank_json()["precomputed"]
        self.assertEqual(declared["inline_formats"], list(INLINE_FORMATS))
        self.assertEqual(declared["inline_below"], PUBLIC_SEEDS)
        self.assertEqual(declared["bundle_formats"], list(BUNDLE_FORMATS))
        self.assertEqual(declared["bundle_from"], PUBLIC_SEEDS)
        self.assertIn("{slug}", declared["bundle_path"])

    def test_declared_bundle_path_resolves(self):
        self.bank.write_json(remote=self.REMOTE)
        declared = self.bank_json()["precomputed"]
        rel = declared["bundle_path"].format(slug="FIGURED")
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, rel)), rel)

    def test_absent_declaration_means_not_precomputed(self):
        """An older bank has no such key at all, which is how a viewer tells
        'not precomputed' from 'precomputed but missing this seed'."""
        self.bank.write_json(remote=self.REMOTE, precompute=False)
        self.assertNotIn("precomputed", self.bank_json())


class RemoteIsRequired(PrecomputeTestCase):
    def test_images_without_remote_refuse_to_build(self):
        with self.assertRaises(ValueError) as cm:
            self.bank.write_json()
        message = str(cm.exception)
        self.assertIn("FIGURED", message, "the message should name the outcome")
        self.assertIn("--remote", message)

    def test_the_check_happens_before_anything_is_written(self):
        """Failing several minutes into a build, after writing a partial
        bank.json, would be worse than failing at once."""
        try:
            self.bank.write_json()
        except ValueError:
            pass
        self.assertFalse(
            os.path.exists(os.path.join(self.tmp, "assets", "bank.json"))
        )

    def test_no_precompute_needs_no_remote(self):
        self.bank.write_json(precompute=False)  # must not raise

    def test_images_get_absolute_urls(self):
        self.bank.write_json(remote=self.REMOTE)
        html = self.exercises(self.bank_json(), "FIGURED")[0]["html"]
        self.assertIn(f'src="{self.REMOTE}/assets/IMG2/2.png"', html)


class StaleBundles(PrecomputeTestCase):
    def test_turning_precompute_off_removes_old_bundles(self):
        """Otherwise bank.json says 'not precomputed' while stale bundles sit
        next to it, which is a trap for anything that looks for files rather
        than reading the declaration."""
        self.bank.write_json(remote=self.REMOTE)
        path = os.path.join(self.tmp, "assets", "PLAIN", "generated", BUNDLE_FILENAME)
        self.assertTrue(os.path.isfile(path))

        self.bank.write_json(precompute=False)
        self.assertFalse(os.path.isfile(path), "stale bundle survived")


if __name__ == "__main__":
    unittest.main()
