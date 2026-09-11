"""Asking for images must produce images.

`generate --images` used to be ignored for any outcome whose seeds already
loaded: generate_exercises() returned as soon as it found a valid seeds.json,
before reaching the figure compile. So the only way to get images was to also
pass -r and regenerate every version -- which changes the problems, and is
exactly what an author avoids doing mid-term.

The visible result was a bank published with figures for the first few
versions and none after, with `generate` reporting no error.

These tests use a fake compile step, so they check the decision to rasterize
rather than pdflatex itself.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkit import outcome as outcome_mod


class FakeOutcome(outcome_mod.Outcome):
    """An Outcome whose seeds are present or absent on demand.

    seeds_json_path is stubbed because generate_exercises passes it as an
    argument to run_generator, and an argument is evaluated even when the call
    it belongs to is mocked out.
    """

    def __init__(self, seeds_load):
        self._seeds_load = seeds_load

    def load_exercises(self, reload=False, strict=True):
        # reload=True is the call made *after* generating, by which point the
        # seeds exist however things stood beforehand.
        if reload:
            return
        if not self._seeds_load:
            raise RuntimeError("no seeds.json")

    def seeds_json_path(self):
        return "seeds.json"


class ImagesAreCompiledTestCase(unittest.TestCase):
    def run_generate(self, seeds_load, images, regenerate=False):
        outcome = FakeOutcome(seeds_load)
        with mock.patch.object(outcome_mod, "compile_tikz_for_outcome") as compile_, \
             mock.patch.object(outcome_mod, "run_generator") as generator:
            outcome_mod.Outcome.generate_exercises(
                outcome, regenerate=regenerate, images=images, image_seeds=400)
        return compile_, generator

    def test_existing_seeds_still_get_their_images(self):
        """The bug. Seeds are fine, so nothing is generated -- but --images was
        asked for, and the figures may be missing."""
        compile_, generator = self.run_generate(seeds_load=True, images=True)

        compile_.assert_called_once()
        self.assertEqual(compile_.call_args.kwargs["image_seeds"], 400)
        generator.assert_not_called()

    def test_existing_seeds_without_images_compile_nothing(self):
        """No --images means no rasterizing, which is the fast path an author
        takes when only the bank.json needs rewriting."""
        compile_, generator = self.run_generate(seeds_load=True, images=False)

        compile_.assert_not_called()
        generator.assert_not_called()

    def test_missing_seeds_generate_and_then_compile(self):
        compile_, generator = self.run_generate(seeds_load=False, images=True)

        generator.assert_called_once()
        compile_.assert_called_once()

    def test_regenerate_always_runs_the_generator(self):
        compile_, generator = self.run_generate(
            seeds_load=True, images=True, regenerate=True)

        generator.assert_called_once()
        compile_.assert_called_once()


if __name__ == "__main__":
    unittest.main()
