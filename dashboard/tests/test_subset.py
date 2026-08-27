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


def transform_as(sheet, spatext, subset=None):
    """Run any one of the three stylesheets over a SpaTeXt string.

    `transform` above is html-only. latex.xsl declares method="text", which
    produces no root element, so that result is stringified rather than
    serialised from a tree.
    """
    xslt = etree.XSLT(etree.fromstring(read_resource(sheet)))
    src = etree.fromstring(spatext.encode("utf-8"))
    result = xslt(src) if subset is None else xslt(src, subset=f"'{subset}'")
    if result.getroot() is None:
        return str(result)
    return etree.tostring(result.getroot()).decode("utf-8")


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


class GlyphsElement(unittest.TestCase):
    """<glyphs> exists so a typeface difference lives in the stylesheets rather
    than in a generator branching on `mode`. The trap when adding any SpaTeXt
    element is parseDisplay: apply-templates with an explicit select ignores
    anything not named there, so the rule fires but the element renders as
    nothing, silently, in every format."""

    def test_html_renders_the_characters(self):
        html = transform(fx.GLYPHS, "all")
        self.assertIn("stx-glyphs", html)
        self.assertIn('data-font="egyptian"', html)
        # lxml's html serialiser writes non-ASCII as numeric entities, so
        # compare decoded text rather than raw bytes: &#77824; IS U+13000.
        import html as html_module

        self.assertIn("𓀀", html_module.unescape(html))

    def test_it_is_listed_in_every_parseDisplay(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in ("html.xsl", "latex.xsl", "pretext.xsl"):
            with self.subTest(stylesheet=name):
                path = os.path.join(root, "dashboard", "checkit", "static", name)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                self.assertIn("stx:glyphs", source.split("parseDisplay")[1][:400],
                              "%s has a rule but does not select it" % name)

    def test_the_viewer_dispatches_it_too(self):
        """The student view builds DOM from SpaTeXt directly and never touches
        the stylesheets, so an element added only to the XSLT is invisible
        there."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(root, "viewer", "src", "spatext", "NodeList",
                            "ParagraphNodes.svelte")
        with open(path, encoding="utf-8") as f:
            self.assertIn('"glyphs"', f.read())


class NobreakElement(unittest.TestCase):
    """<nobreak> is the fourth kind of `mode` branch, and the one the mode
    retirement missed.

    W4 wrote \mbox into its strings behind mode='latex' and stripped it again
    for HTML. Dropping `mode` left the \mbox in the string for both media, and
    the template's <m> wrapper then swallowed it into `\(\mbox{\)` -- an
    unmatched brace inside math mode, which does not compile. Print was broken
    for 50 versions while every HTML check was green.

    Unlike <glyphs>, this element WRAPS other elements, so each rule must
    recurse rather than read text(): reading text nodes would discard the very
    <m> elements it exists to hold together.
    """

    def test_latex_emits_mbox_around_the_maths(self):
        latex = transform_as("latex.xsl", fx.NOBREAK, "all")
        self.assertIn("\mbox{", latex)
        # the point of the element: the maths must survive inside the box
        self.assertIn("k + (j + u + 0) =", latex)
        self.assertNotIn("\mbox{}", latex)

    def test_html_marks_it_unbreakable_and_keeps_the_maths(self):
        html = transform(fx.NOBREAK, "all")
        self.assertIn("nowrap", html)
        self.assertIn("k + (j + u + 0) =", html)

    def test_no_stray_mbox_reaches_the_browser(self):
        """The symptom students actually saw."""
        self.assertNotIn("mbox", transform(fx.NOBREAK, "all"))

    def test_pretext_passes_the_content_through(self):
        pretext = transform_as("pretext.xsl", fx.NOBREAK, "all")
        self.assertIn("k + (j + u + 0) =", pretext)
        self.assertNotIn("mbox", pretext)

    def test_it_is_listed_in_every_parseDisplay(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in ("html.xsl", "latex.xsl", "pretext.xsl"):
            with self.subTest(stylesheet=name):
                path = os.path.join(root, "dashboard", "checkit", "static", name)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                self.assertIn("stx:nobreak", source.split("parseDisplay")[1][:400],
                              "%s has a rule but does not select it" % name)

    def test_the_viewer_dispatches_it_too(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(root, "viewer", "src", "spatext", "NodeList",
                            "ParagraphNodes.svelte")
        with open(path, encoding="utf-8") as f:
            self.assertIn('"nobreak"', f.read())


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

    def test_unknown_consumer_raises(self):
        """Returning basic output under an LMS label is the failure mode that
        hid the dead parameters for four years."""
        with self.assertRaises(ValueError):
            self.ex.html_ele(consumer="blackboard")

    def test_pretext_refuses_what_it_cannot_do(self):
        for kwargs in ({"subset": "answer"}, {"consumer": "canvas"}):
            with self.subTest(**kwargs):
                with self.assertRaises(NotImplementedError):
                    self.ex.pretext_ele(**kwargs)

    def test_pretext_and_latex_defaults_still_work(self):
        self.assertIn("<exercise", self.ex.pretext())
        self.assertIn("stxKnowl", self.ex.latex())


def _exercise_from(spatext, tmpdir):
    path = os.path.join(tmpdir, "template.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(spatext)
    return Exercise(data={}, seed=0, outcome=_StubOutcome(path))


class MathmlConsumer(unittest.TestCase):
    """An LMS renders imported HTML without CheckIt's JavaScript, so LaTeX
    delimiters would reach the student as literal backslashes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ex = _exercise_from(fx.MATH, self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_basic_consumer_keeps_latex_delimiters(self):
        html = self.ex.html(consumer="basic", remote="")
        self.assertIn(r"\(", html)
        self.assertNotIn("<math", html)

    def test_canvas_consumer_emits_mathml(self):
        html = self.ex.html(consumer="canvas", remote="")
        self.assertIn("<math", html)
        self.assertIn("http://www.w3.org/1998/Math/MathML", html)
        self.assertNotIn(r"\(", html)

    def test_brightspace_behaves_like_canvas(self):
        self.assertEqual(
            canon(self.ex.html(consumer="canvas", remote="")),
            canon(self.ex.html(consumer="brightspace", remote="")),
        )

    def test_fraction_becomes_mfrac_not_flattened_text(self):
        """Matching characters is not matching maths: 1/3 written inline would
        contain the same digits as a stacked fraction."""
        html = self.ex.html(consumer="canvas", remote="")
        self.assertIn("<mfrac", html)

    def test_display_and_inline_are_distinguished(self):
        html = self.ex.html(consumer="canvas", remote="")
        self.assertIn('display="block"', html)
        self.assertIn('display="inline"', html)

    def test_every_math_span_is_converted(self):
        ele = self.ex.html_ele(consumer="canvas", remote="")
        spans = [
            el for el in ele.iter()
            if "math" in (el.get("class") or "").split()
            and el.get("data-latex") is not None
        ]
        self.assertEqual(len(spans), 3)  # inline, display, and the <me> answer
        for span in spans:
            kids = list(span)
            self.assertEqual(len(kids), 1, "span should hold exactly the <math>")
            self.assertTrue(kids[0].tag.endswith("}math"))
            self.assertIsNone(span.text, "LaTeX text should be gone")

    def test_data_latex_survives_so_the_source_is_recoverable(self):
        ele = self.ex.html_ele(consumer="canvas", remote="")
        found = [el.get("data-latex") for el in ele.iter()
                 if el.get("data-latex") is not None]
        self.assertIn(r"\frac{1}{3}", found)


class RemoteBaseUrl(unittest.TestCase):
    """html.xsl builds <img src> as @remote + "/" + @source. The viewer fills
    @remote from location.href; a build has no page to read, so it must be
    supplied or the URLs silently point nowhere."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.with_image = _exercise_from(fx.IMAGE, self.tmp.name)
        self.tmp2 = tempfile.TemporaryDirectory()
        self.no_image = _exercise_from(fx.SIMPLE, self.tmp2.name)

    def tearDown(self):
        self.tmp.cleanup()
        self.tmp2.cleanup()

    def test_images_without_remote_raise(self):
        """A dead <img src> is invisible until a student meets it, so this must
        fail at build time rather than export quietly."""
        with self.assertRaises(ValueError) as cm:
            self.with_image.html_ele()
        self.assertIn("remote", str(cm.exception))

    def test_no_images_means_remote_is_irrelevant(self):
        self.no_image.html_ele()  # must not raise

    def test_remote_is_prepended_to_source(self):
        html = self.with_image.html(remote="https://checkit.clontz.org/demo")
        self.assertIn(
            'src="https://checkit.clontz.org/demo/assets/IMG2/2.png"', html
        )

    def test_trailing_slashes_do_not_double_up(self):
        html = self.with_image.html(remote="https://example.org/bank//")
        self.assertIn('src="https://example.org/bank/assets/IMG2/2.png"', html)

    def test_empty_remote_keeps_the_old_relative_behaviour(self):
        html = self.with_image.html(remote="")
        self.assertIn('src="/assets/IMG2/2.png"', html)

    def test_remote_applies_under_every_subset_and_consumer(self):
        for subset in ("all", "statement"):
            for consumer in ("basic", "canvas"):
                with self.subTest(subset=subset, consumer=consumer):
                    html = self.with_image.html(
                        subset=subset, consumer=consumer,
                        remote="https://example.org/b",
                    )
                    self.assertIn('src="https://example.org/b/assets/', html)


class CrossLanguageConstants(unittest.TestCase):
    """PUBLIC_SEEDS exists twice, once per language, because the browser cannot
    import from Python. Nothing but this test stops them drifting -- and a drift
    would be quiet: the picker would offer versions the preview never generated,
    or assessments would draw from seeds a student can open in the viewer."""

    def _viewer_constant(self, name):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ts = os.path.join(root, "viewer", "src", "utils", "index.ts")
        with open(ts, encoding="utf-8") as f:
            source = f.read()
        found = re.search(r"export const %s\s*=\s*(\d+)" % name, source)
        self.assertIsNotNone(found, "%s not declared in utils/index.ts" % name)
        return int(found.group(1))

    def test_python_and_viewer_agree(self):
        import checkit

        for name in ("PUBLIC_SEEDS", "BUNDLE_UNTIL"):
            with self.subTest(constant=name):
                self.assertEqual(
                    self._viewer_constant(name),
                    getattr(checkit, name),
                    "viewer %s and checkit.%s disagree" % (name, name),
                )

    def test_the_browser_range_is_above_the_public_one(self):
        """An empty or inverted instructor range would make the assessment
        builder compute a negative seed span, silently."""
        import checkit

        self.assertGreater(checkit.BUNDLE_UNTIL, checkit.PUBLIC_SEEDS)


class StylesheetsExistOnlyOnce(unittest.TestCase):
    """The three stylesheets used to exist twice, once for lxml and once for the
    browser, kept in sync by hand across six files. That duplication caused the
    document-vs-element bug and forced every SpaTeXt element to be added in six
    places. The viewer no longer transforms anything, so the browser copy is
    gone -- this guards against it coming back."""

    def test_the_viewer_has_no_stylesheets(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        viewer = os.path.join(root, "viewer", "src")
        found = [
            os.path.relpath(os.path.join(dirpath, name), root)
            for dirpath, _, names in os.walk(viewer)
            for name in names
            if name.endswith(".xsl")
        ]
        self.assertEqual(found, [], "the browser-side stylesheets are back")

    def test_the_dashboard_still_has_all_three(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in ("html.xsl", "latex.xsl", "pretext.xsl"):
            with self.subTest(stylesheet=name):
                self.assertTrue(os.path.isfile(
                    os.path.join(root, "dashboard", "checkit", "static", name)))


if __name__ == "__main__":
    unittest.main()
