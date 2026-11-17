"""What the generator wrapper leaves on disk when a run fails, or changes.

RV-11 of the 2026-11-16 review: each seed's .tikz was written as the run
went and seeds.json only at the end, so a generator failing at seed 7 left
new figures for seeds 0-6 beside the old seeds.json. Print \\input's the
.tikz, so a page's picture and its numbers disagreed. And a seed that no
longer drew a figure kept its old one.

Run as a subprocess, as `checkit generate` runs it.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

WRAPPER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "checkit", "wrapper", "wrapper.py")

GENERATOR = '''
class Generator(BaseGenerator):
    def data(self):
        if self.seed == FAIL_AT:
            raise RuntimeError("generator broke")
        return {"n": str(self.seed) + LABEL}

    @provide_data
    def tikz_graphics(data):
        if DRAW is None:
            return None
        return {"fig": "\\\\node {" + data["n"] + "};"}
'''


class WrapperTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.gen = os.path.join(self.tmp, "generator.py")
        self.out = os.path.join(self.tmp, "assets", "X", "generated", "seeds.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_wrapper(self, label="", fail_at=-1, draw=True, check=True):
        with open(self.gen, "w", encoding="utf-8") as f:
            f.write(f"FAIL_AT = {fail_at}\nLABEL = {label!r}\n"
                    f"DRAW = {'True' if draw else 'None'}\n" + GENERATOR)
        return subprocess.run([sys.executable, WRAPPER, self.gen, self.out,
                               "10", "no"], cwd=self.tmp, capture_output=True,
                              text=True, check=check)

    def tikz(self, seed):
        path = os.path.join(os.path.dirname(self.out), f"{seed:04}", "fig.tikz")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_a_failed_run_leaves_the_old_figures_and_data(self):
        self.run_wrapper(label="-old")
        before = open(self.out, "rb").read()
        result = self.run_wrapper(label="-new", fail_at=7, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(open(self.out, "rb").read(), before)
        for seed in range(10):
            self.assertIn("-old", self.tikz(seed),
                          f"seed {seed}'s figure changed without its data")

    def test_a_successful_run_writes_both(self):
        self.run_wrapper(label="-old")
        self.run_wrapper(label="-new")
        self.assertIn("-new", self.tikz(3))
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["seeds"][3]["data"]["n"], "3-new")

    def test_a_figure_the_seed_no_longer_draws_is_removed(self):
        self.run_wrapper()
        png = os.path.join(os.path.dirname(self.out), "0002", "fig.png")
        with open(png, "wb") as f:
            f.write(b"png")
        self.run_wrapper(draw=False)
        self.assertIsNone(self.tikz(2))
        self.assertFalse(os.path.exists(png), "its picture outlived it")

    def test_an_unchanged_figure_is_not_rewritten(self):
        """So the figure compiler and anybody's diff see no change."""
        import time
        self.run_wrapper()
        path = os.path.join(os.path.dirname(self.out), "0004", "fig.tikz")
        old = time.time() - 3600
        os.utime(path, (old, old))
        self.run_wrapper()
        self.assertAlmostEqual(os.path.getmtime(path), old, delta=1)


if __name__ == "__main__":
    unittest.main()
