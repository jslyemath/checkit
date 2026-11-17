"""Which figures get rasterized, and what that costs.

Three findings of the 2026-11-16 review, all in `compile_tikz_for_outcome`:

* RV-8: every figure rebuilt a whole `Bank` -- bank.xml parsed and every
  outcome's seeds.json loaded -- to find the support files, about a second
  each on mat-106, so about half an hour of a full F2 rasterise.
* RV-11: a PNG counted as current when it was newer than its .tikz, and on
  nothing else. Editing tikz_preamble.tex or the figure style left every
  PNG as it was while print -- which \\input's the .tikz -- picked the
  change up at once, so the web and the handout drifted apart. And `-r`
  rewrites every .tikz, so every PNG recompiled even when nothing changed.
* RV-14: "raising here cancels what has not started" was false. After the
  first bad figure, every queued figure still compiled before the error
  appeared.

The compile step is faked: what is under test is the decision.
"""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from checkit import bank as bank_mod
from checkit.bank import Bank
from checkit.wrapper import tikz

BANK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Figures</title>
    <slug>fig</slug>
    <url>https://example.org</url>
    <latex-support>
        <file path="printit/printitfigures.sty" role="figures"/>
    </latex-support>
    <outcomes>
        <outcome>
            <title>F</title>
            <slug>F</slug>
            <path>outcomes/F</path>
            <description>Figures.</description>
        </outcome>
    </outcomes>
</bank>
"""

FIGURES = 12


class _FigureBank(unittest.TestCase):
    """The fixture, with no tests of its own, so a class built on it runs
    only its own."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "outcomes", "F"))
        os.makedirs(os.path.join(self.tmp, "printit"))
        self.write("bank.xml", BANK_XML)
        self.write("tikz_preamble.tex", "\\documentclass{standalone}\n")
        self.write("printit/printitfigures.sty", "% style one\n")
        for n in range(FIGURES):
            self.write(f"assets/F/generated/{n:04}/fig.tikz", f"\\node {{{n}}};\n")
        self.bank = Bank(self.tmp)
        self.outcome = self.bank.outcomes()[0]
        self.compiled = []
        self.env = mock.patch.dict(os.environ, {"CHECKIT_TIKZ_WORKERS": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.tmp, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def fake(self, **kw):
        self.compiled.append(kw["png_path"])
        with open(kw["png_path"], "wb") as f:
            f.write(b"png")

    def run_compile(self, fake=None):
        self.compiled = []
        with mock.patch.object(tikz, "_compile_one", fake or self.fake):
            tikz.compile_tikz_for_outcome(self.outcome)
        return len(self.compiled)


class FigureCompileTestCase(_FigureBank):

    def test_the_first_run_compiles_everything(self):
        self.assertEqual(self.run_compile(), FIGURES)

    def test_a_second_run_compiles_nothing(self):
        self.run_compile()
        self.assertEqual(self.run_compile(), 0)

    def test_rewriting_a_tikz_with_the_same_content_compiles_nothing(self):
        """What `generate -r` does to every figure.

        The rewrite is dated a minute later, as a real one is. Without
        that this passed against the old code too: Windows' clock ticks
        every 15ms or so, so the rewrite and the PNG shared a timestamp
        and the old freshness rule called the PNG current."""
        import time
        self.run_compile()
        later = time.time() + 60
        for n in range(FIGURES):
            self.write(f"assets/F/generated/{n:04}/fig.tikz", f"\\node {{{n}}};\n")
            os.utime(os.path.join(self.tmp, "assets", "F", "generated",
                                  f"{n:04}", "fig.tikz"), (later, later))
        self.assertEqual(self.run_compile(), 0)

    def test_a_changed_figure_is_compiled(self):
        self.run_compile()
        self.write("assets/F/generated/0003/fig.tikz", "\\node {changed};\n")
        self.assertEqual(self.run_compile(), 1)

    def test_editing_the_preamble_recompiles_every_figure(self):
        self.run_compile()
        self.write("tikz_preamble.tex", "\\documentclass{standalone}\n% v2\n")
        self.assertEqual(self.run_compile(), FIGURES)

    def test_editing_the_figure_style_recompiles_every_figure(self):
        """printitfigures.sty is what keeps the web figure and the printed
        one the same picture."""
        self.run_compile()
        self.write("printit/printitfigures.sty", "% style two\n")
        self.assertEqual(self.run_compile(), FIGURES)

    def test_a_deleted_png_is_compiled_again(self):
        self.run_compile()
        os.remove(os.path.join(self.tmp, "assets", "F", "generated", "0005",
                               "fig.png"))
        self.assertEqual(self.run_compile(), 1)

    def test_no_bank_is_built_per_figure(self):
        built = []
        real = bank_mod.Bank.__init__

        def counting(self_, *a, **k):
            built.append(1)
            return real(self_, *a, **k)
        with mock.patch.object(bank_mod.Bank, "__init__", counting):
            self.run_compile()
        self.assertEqual(built, [])

    def test_a_failure_stops_the_queue(self):
        """One worker and every figure broken: the first fails, and at
        most the one the worker had already picked up runs after it --
        not the other ten. (The worker takes the next job the moment it
        finishes one, before the main thread has seen the error.)"""
        calls = []

        def broken(**kw):
            calls.append(1)
            raise RuntimeError("bad figure")
        with self.assertRaises(RuntimeError):
            self.run_compile(fake=broken)
        self.assertLessEqual(len(calls), 2)

    def test_figures_compiled_before_a_failure_are_not_redone(self):
        state = {"n": 0}

        def third_fails(**kw):
            state["n"] += 1
            if state["n"] == 3:
                raise RuntimeError("bad figure")
            self.fake(**kw)
        with self.assertRaises(RuntimeError):
            self.run_compile(fake=third_fails)
        # Two done before the failure, perhaps one more in flight.
        self.assertIn(self.run_compile(), (FIGURES - 2, FIGURES - 3))


class TheSiteCarriesTheFiguresAnAssessmentCanUse(_FigureBank):
    """The viewer's assessment builder emits `\\input{...fig.tikz}` -- the
    same source print uses -- so the published site has to carry it for
    every seed an assessment can draw (below BUNDLE_UNTIL). It carried
    none: `build_viewer` left every .tikz out, and an assessment with a
    figure could not compile (2026-11-17). Print-only seeds stay
    unpublished, as their data does."""

    def publish(self):
        from checkit import BUNDLE_UNTIL
        self.write(f"assets/F/generated/{BUNDLE_UNTIL:04}/fig.tikz", "\\node {p};\n")
        self.write("assets/F/generated/seeds.json",
                   '{"seeds": [], "generated_on": "2026-11-17"}')
        Bank(self.tmp).build_viewer()
        return os.path.join(self.tmp, "docs", "assets", "F", "generated")

    def test_a_drawable_seed_s_figure_is_published(self):
        self.assertTrue(os.path.isfile(os.path.join(self.publish(), "0003",
                                                    "fig.tikz")))

    def test_a_print_only_seed_s_figure_is_not(self):
        from checkit import BUNDLE_UNTIL
        self.assertFalse(os.path.exists(os.path.join(
            self.publish(), f"{BUNDLE_UNTIL:04}", "fig.tikz")))

    def test_seeds_json_and_the_figure_keys_are_still_not(self):
        out = self.publish()
        self.assertFalse(os.path.exists(os.path.join(out, "seeds.json")))
        self.assertFalse(os.path.exists(os.path.join(out, tikz.FIGURE_KEYS)))


if __name__ == "__main__":
    unittest.main()
