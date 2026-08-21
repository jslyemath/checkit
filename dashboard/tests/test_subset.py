"""Tests for html.xsl's `subset` parameter.

The point of these is not that the filter works -- it is that it agrees with the
*other* implementation of the same idea. html.xsl filters during the transform;
viewer/src/utils/index.ts filters after it, by removing elements by class. Those
two must produce identical HTML, and nothing but a test enforces that.

Run:  python -m unittest discover -s dashboard/tests -t dashboard/tests

Stdlib unittest on purpose: this repo has no test dependency and no test
runner, and adding one should not be the price of adding the first test.
"""

import copy
import os
import re
import sys
import tempfile
import unittest

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkit.exercise import Exercise
from checkit.static import read_resource

import spatext_fixtures as fx


def canon(html_string):
    """Collapse whitespace so comparisons are about structure, not formatting."""
    s = re.sub(r">\s+<", "><", html_string)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def transform(spatext, subset=None):
    """Run html.xsl over a SpaTeXt string, optionally passing `subset`.

    `subset=None` means "pass no parameter at all", which is what the viewer
    does -- so it is a case worth being able to express.
    """
    xslt = etree.XSLT(etree.fromstring(read_resource("html.xsl")))
    src = etree.fromstring(spatext.encode("utf-8"))
    result = xslt(src) if subset is None else xslt(src, subset=f"'{subset}'")
    return etree.tostring(result.getroot(), method="html").decode("utf-8")


def viewer_filter(html_string, classes):
    """Reproduce utils/index.ts: ele.querySelectorAll(...).forEach(remove)."""
    root = etree.fromstring(html_string.encode("utf-8"), etree.HTMLParser())
    tree = copy.deepcopy(root)
    doomed = [
        el
        for el in tree.iter()
        if any(c in (el.get("class") or "").split() for c in classes)
    ]
    for el in doomed:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    found = tree.find(".//div[@class='stx']")
    return etree.tostring(found, method="html").decode("utf-8")


class SubsetMatchesViewer(unittest.TestCase):
    """The property that actually matters: two implementations, one result."""

    def test_every_fixture_and_subset(self):
        for name, spatext in fx.ALL.items():
            unfiltered = transform(spatext, "all")
            for solutions, (subset, classes) in fx.CASES.items():
                with self.subTest(fixture=name, subset=subset):
                    from_stylesheet = canon(transform(spatext, subset))
                    from_viewer = canon(viewer_filter(unfiltered, classes))
                    self.assertEqual(
                        from_stylesheet,
                        from_viewer,
                        f"{name}: stylesheet subset={subset!r} disagrees with the "
                        f"viewer's solutions={solutions!r} filtering",
                    )

    def test_subsets_are_not_no_ops(self):
        """A filter that removed nothing would pass the test above trivially."""
        for name, spatext in fx.ALL.items():
            if name == "NO_OUTTRO":
                continue  # nothing for 'statement' to remove; asserted below
            with self.subTest(fixture=name):
                every = canon(transform(spatext, "all"))
                self.assertNotEqual(every, canon(transform(spatext, "statement")))
                self.assertNotEqual(every, canon(transform(spatext, "answer")))


class DefaultBehaviour(unittest.TestCase):
    def test_omitting_the_parameter_means_all(self):
        """The viewer never passes `subset`, so the default is load-bearing.

        If this fails, browser output changed the moment the stylesheet was
        edited rather than at migration time.
        """
        for name, spatext in fx.ALL.items():
            with self.subTest(fixture=name):
                self.assertEqual(
                    canon(transform(spatext, subset=None)),
                    canon(transform(spatext, "all")),
                )

    def test_nothing_removed_when_there_is_nothing_to_remove(self):
        every = canon(transform(fx.NO_OUTTRO, "all"))
        self.assertEqual(every, canon(transform(fx.NO_OUTTRO, "statement")))


class Structure(unittest.TestCase):
    def test_list_wrapper_survives_answer_subset(self):
        """Guarding the whole xsl:choose instead of the apply-templates would
        drop the <ol>, silently renumbering an instructor's answer key."""
        for subset in ("all", "statement", "answer"):
            with self.subTest(subset=subset):
                html = transform(fx.TASKS, subset)
                self.assertIn("<ol>", html)
                self.assertEqual(html.count("<li>"), 2)

    def test_answer_subset_drops_intro_and_content_at_every_depth(self):
        html = transform(fx.TASKS, "answer")
        self.assertNotIn("stx-intro", html)
        self.assertNotIn("stx-content", html)
        self.assertEqual(html.count("stx-outtro"), 3)  # two tasks + the outer one

    def test_statement_subset_drops_outtro_at_every_depth(self):
        html = transform(fx.TASKS, "statement")
        self.assertNotIn("stx-outtro", html)
        self.assertEqual(html.count("stx-content"), 2)

    def test_title_survives_every_subset(self):
        for subset in ("all", "statement", "answer"):
            with self.subTest(subset=subset):
                self.assertIn("stx-title", transform(fx.TITLED, subset))


class _StubOutcome:
    """Enough of an Outcome for Exercise.spatext_ele() to render a template."""

    def __init__(self, path):
        self._path = path

    def template_filepath(self):
        return self._path


class ExerciseApi(unittest.TestCase):
    """Covers the plumbing in exercise.py, not the stylesheet.

    Notably that `subset=f"'{subset}'"` keeps its inner quotes: an XSLT
    parameter is an XPath expression, so a bare `answer` would select an
    <answer> element -- yielding an empty string and no filtering, silently.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self.tmp.name, "template.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(fx.SIMPLE)
        self.ex = Exercise(data={}, seed=0, outcome=_StubOutcome(path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_parameter_reaches_the_stylesheet(self):
        every = canon(self.ex.html(subset="all"))
        self.assertNotEqual(every, canon(self.ex.html(subset="statement")))
        self.assertNotEqual(every, canon(self.ex.html(subset="answer")))

    def test_default_matches_explicit_all(self):
        self.assertEqual(canon(self.ex.html()), canon(self.ex.html(subset="all")))

    def test_unknown_subset_raises(self):
        with self.assertRaises(ValueError):
            self.ex.html_ele(subset="statements")  # plausible typo

    def test_unimplemented_consumer_raises(self):
        """Returning basic output under an LMS label is the failure mode that
        hid the dead parameters for four years."""
        with self.assertRaises(NotImplementedError):
            self.ex.html_ele(consumer="canvas")

    def test_pretext_refuses_what_it_cannot_do(self):
        for kwargs in ({"subset": "answer"}, {"consumer": "canvas"}):
            with self.subTest(**kwargs):
                with self.assertRaises(NotImplementedError):
                    self.ex.pretext_ele(**kwargs)

    def test_pretext_and_latex_defaults_still_work(self):
        self.assertIn("<exercise", self.ex.pretext())
        self.assertIn("stxKnowl", self.ex.latex())


class StylesheetCopies(unittest.TestCase):
    def test_dashboard_and_viewer_copies_are_identical(self):
        """The two copies must be edited together; nothing else enforces it.

        Note there is a third, frozen copy inside static/viewer.zip, baked in at
        Vite build time -- it only updates when update_viewer.py runs.
        """
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in ("html.xsl", "latex.xsl", "pretext.xsl"):
            with self.subTest(stylesheet=name):
                a = os.path.join(root, "dashboard", "checkit", "static", name)
                b = os.path.join(root, "viewer", "src", "spatext", "xsl", name)
                with open(a, "rb") as f1, open(b, "rb") as f2:
                    self.assertEqual(
                        f1.read(),
                        f2.read(),
                        f"{name} differs between dashboard/ and viewer/",
                    )


if __name__ == "__main__":
    unittest.main()
