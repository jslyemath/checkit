"""Tests for checks.py.

The point of these is not that the checks run. It is that each one **can
fail**: every check here was written after a build shipped the fault it
catches while every other check was green, and a detector that cannot
demonstrate a failure has not reported a pass.

So each check gets a known-bad input as well as a known-good one. Two of these
guards exist specifically because an earlier version of the detector was wrong
rather than the code: the raw-TeX check once required two or more letters after
the backslash and so reported a confident clean over 300 versions showing
"27.6\\%", and the nested-element check cannot be written against the HTML at
all, because by then the dropped content is gone.
"""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkit import checks

BS = chr(92)


def doc(html=None, latex=None, pretext=None, slug="X"):
    """A minimal bank.json with one outcome and one exercise."""
    exercise = {"seed": 0, "data": {}}
    if html is not None:
        exercise["html"] = html
    if latex is not None:
        exercise["latex"] = latex
    if pretext is not None:
        exercise["pretext"] = pretext
    return {"outcomes": [{"slug": slug, "exercises": [exercise]}]}


class RawTexInProse(unittest.TestCase):
    def test_multi_letter_command_is_found(self):
        found = checks.raw_tex_in_prose(doc(html="<p>" + BS + "text{MDCXLVIII}</p>"))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].check, "raw-tex")

    def test_single_character_escape_is_found(self):
        """The blind spot that let an outcome ship "27.6\\%" to students."""
        for token in ("%", "$", "&", "_", "#"):
            with self.subTest(token=token):
                found = checks.raw_tex_in_prose(doc(html="<p>5" + BS + token + " of it</p>"))
                self.assertEqual(len(found), 1, f"{BS}{token} not detected")

    def test_backslashes_inside_maths_are_not_findings(self):
        """Maths legitimately contains commands; only prose is a leak."""
        html = ('<p><span class="math inline-math" data-latex="' + BS + 'dfrac{1}{2}">'
                + BS + '(' + BS + 'dfrac{1}{2}' + BS + ')</span></p>')
        self.assertEqual(checks.raw_tex_in_prose(doc(html=html)), [])

    def test_clean_prose_is_clean(self):
        self.assertEqual(checks.raw_tex_in_prose(doc(html="<p>plain words</p>")), [])

    def test_a_brace_in_prose_is_found(self):
        """mat-106's W7 showed students "9{,}456 remainder 734" for weeks:
        a LaTeX thousands separator in plain text. No backslash, so the
        command patterns never saw it. A brace in visible text is LaTeX
        leaking either way -- literal on the web, swallowed in print."""
        found = checks.raw_tex_in_prose(doc(html="<p>9{,}456 remainder 7</p>"))
        self.assertEqual([f.detail for f in found], ["'{' renders literally",
                                                     "'}' renders literally"])

    def test_braces_inside_maths_are_not_findings(self):
        html = ('<p><span class="math inline-math" data-latex="9{,}456">'
                + BS + '(9{,}456' + BS + ')</span></p>')
        self.assertEqual(checks.raw_tex_in_prose(doc(html=html)), [])


class EscapedMarkup(unittest.TestCase):
    def test_escaped_element_is_found(self):
        found = checks.escaped_markup(doc(html="<p>&lt;m&gt;x&lt;/m&gt;</p>"))
        self.assertEqual(len(found), 1)

    def test_each_element_name(self):
        for name in ("m", "glyphs", "nobreak", "em"):
            with self.subTest(element=name):
                found = checks.escaped_markup(doc(html=f"<p>&lt;{name}&gt;</p>"))
                self.assertEqual(len(found), 1)

    def test_real_markup_is_not_a_finding(self):
        self.assertEqual(checks.escaped_markup(doc(html="<p><em>fine</em></p>")), [])


class ControlCharacters(unittest.TestCase):
    def test_tab_from_a_non_raw_literal_is_found(self):
        """'\\textpmhg' in a non-raw string is TAB + 'extpmhg'."""
        found = checks.control_characters(doc(latex=BS + "Large\textpmhg{x}"))
        self.assertEqual(len(found), 1)
        self.assertIn("t", found[0].detail)

    def test_newline_is_allowed(self):
        """Legitimate in generated LaTeX, unlike the others."""
        self.assertEqual(checks.control_characters(doc(latex="a\nb")), [])


class RelativeImageSrc(unittest.TestCase):
    def test_root_relative_src_is_found(self):
        found = checks.relative_image_src(doc(html='<img src="assets/X/0/p.png">'))
        self.assertEqual(len(found), 1)

    def test_absolute_src_is_fine(self):
        self.assertEqual(
            checks.relative_image_src(doc(html='<img src="https://example.org/p.png">')), [])


class LatexStructure(unittest.TestCase):
    def test_balance_helper(self):
        self.assertEqual(checks.brace_balance("a{b}c"), 0)
        self.assertEqual(checks.brace_balance("a{b"), 1)
        self.assertEqual(checks.brace_balance("a}b"), -1)
        self.assertEqual(checks.brace_balance(BS + "{ " + BS + "}"), 0,
                         "escaped braces are not grouping")

    def test_the_document_that_would_not_compile(self):
        """The real regression: `\\(\\mbox{\\)`, produced when an <m> wrapper
        swallowed everything but the opening of a command."""
        found = checks.latex_structure(doc(latex=BS + "(" + BS + "mbox{" + BS + ")"))
        self.assertTrue(found)
        self.assertTrue(any(f.check == "latex-braces" for f in found))

    def test_unescaped_dollar_inside_maths(self):
        found = checks.latex_structure(doc(latex=BS + "(a $ b" + BS + ")"))
        self.assertTrue(any("$" in f.detail for f in found))

    def test_par_inside_maths(self):
        found = checks.latex_structure(doc(latex=BS + "(a " + BS + "par b" + BS + ")"))
        self.assertTrue(any("par" in f.detail for f in found))

    def test_mbox_wrapping_maths_is_correct_and_not_flagged(self):
        """The fix inverts the nesting: \\mbox{\\(x\\)}, not \\(\\mbox{x}\\)."""
        latex = BS + "mbox{" + BS + "(x = y" + BS + ")}"
        self.assertEqual(checks.latex_structure(doc(latex=latex)), [])

    def test_legal_text_mode_commands_are_not_flagged(self):
        """All three are legal inside math mode and all are used on purpose:
        \\text{} for Roman numerals, \\textbf{} for the outcome title, \\mbox{}
        wherever a box is wanted. Flagging them produced 976 findings against a
        correct bank, which is how a check teaches people to ignore it."""
        for command in ("text", "textbf", "mbox"):
            with self.subTest(command=command):
                latex = BS + "(" + BS + command + "{W1}" + BS + ")"
                self.assertEqual(checks.latex_structure(doc(latex=latex)), [])


class PunctuationInMath(unittest.TestCase):
    def test_trailing_full_stop_inside_inline_maths(self):
        html = '<span class="math inline-math" data-latex="' + BS + '$982.69.">x</span>'
        self.assertEqual(len(checks.punctuation_in_inline_math(doc(html=html))), 1)

    def test_display_maths_is_exempt(self):
        """Punctuation inside a displayed equation is correct typesetting."""
        html = '<span class="math display-math" data-latex="x = 1.">x</span>'
        self.assertEqual(checks.punctuation_in_inline_math(doc(html=html)), [])


class _StubExercise:
    def __init__(self, data):
        self.data = data


class _StubOutcome:
    def __init__(self, slug, template, data):
        self.slug = slug
        self._template = template
        self._exercises = [_StubExercise(data)]

    def template(self):
        return self._template

    def exercises(self):
        return self._exercises


class _StubBank:
    def __init__(self, outcomes):
        self._outcomes = outcomes

    def outcomes(self):
        return self._outcomes


class TemplateFieldsWithoutData(unittest.TestCase):
    """Mustache renders an absent key as empty, so the sentence survives and
    the value disappears. W4 carried a duplicated block asking students to
    explain "the  " for months: nothing failed, and the question could not be
    answered."""

    def check(self, template, data):
        bank = _StubBank([_StubOutcome("X", template, data)])
        return checks.template_fields_without_data(bank)

    def test_missing_key_is_found(self):
        found = self.check("<p>explain the {{{expl_text}}}</p>", {})
        self.assertEqual(len(found), 1)
        self.assertIn("expl_text", found[0].detail)

    def test_present_key_is_fine(self):
        self.assertEqual(
            self.check("<p>explain the {{{expl_text}}}</p>", {"expl_text": "x"}), [])

    def test_double_and_triple_braces_both_count(self):
        self.assertEqual(len(self.check("<p>{{a}} and {{{b}}}</p>", {})), 2)

    def test_section_tags_are_exempt(self):
        """An absent key in a section means 'false', which is what they are
        for -- F2-E uses {{#p1_prob_text}} exactly that way."""
        self.assertEqual(self.check("<!-- {{#opt}} --><p>x</p><!-- {{/opt}} -->", {}), [])

    def test_seed_is_injected_not_generated(self):
        self.assertEqual(self.check("<p>{{__seed__}}</p>", {}), [])

    def test_commented_out_blocks_are_exempt(self):
        """Retired sub-skills are left commented rather than deleted, and their
        fields are naturally absent. N1, D1, R2 and W5 all carry one, and
        flagging them would be four false positives on a correct bank."""
        self.assertEqual(
            self.check("<!-- <p>{{{explain_prob_1}}}</p> --><p>fine</p>", {}), [])

    def test_a_field_outside_the_comment_is_still_found(self):
        """Stripping comments must not swallow the live markup around them."""
        found = self.check("<!-- old --><p>{{{expl_text}}}</p>", {})
        self.assertEqual(len(found), 1)

    # -- names inside a section resolve against that section's own value ----
    #
    # This check compared every reference against the top-level keys, so a
    # field nested one level down looked absent. The demo bank reported ten
    # findings on templates that were entirely correct.

    def test_a_field_inside_a_section_may_live_in_that_section(self):
        """IMG1's shape: {{slope}} inside {{#line}}, where the generator
        returns {"line": {"slope": 3}}."""
        self.assertEqual(
            self.check(
                "<!-- {{#line}} --><p>slope {{slope}}</p><!-- {{/line}} -->",
                {"line": {"slope": 3}}),
            [])

    def test_a_field_in_neither_place_is_still_found(self):
        """The fix must not make the check unable to fail."""
        found = self.check(
            "<!-- {{#line}} --><p>slope {{slope}}</p><!-- {{/line}} -->",
            {"line": {"intercept": 1}})
        self.assertEqual(len(found), 1)
        self.assertIn("slope", found[0].detail)

    def test_a_section_over_a_list_offers_each_item(self):
        """XML's shape: the section value is a list, and the field lives on
        the items rather than on the list."""
        self.assertEqual(
            self.check(
                "<!-- {{#rows}} --><p>{{left}}</p><!-- {{/rows}} -->",
                {"rows": [{"left": "a"}, {"left": "b"}]}),
            [])

    def test_an_outer_field_stays_visible_inside_a_section(self):
        """Mustache falls back outward, so a top-level key is still in scope."""
        self.assertEqual(
            self.check(
                "<!-- {{#line}} --><p>{{title}}</p><!-- {{/line}} -->",
                {"title": "Lines", "line": {"slope": 3}}),
            [])

    def test_a_field_after_a_section_closes_is_top_level_again(self):
        """A stack that never pops would hide real findings after the section."""
        found = self.check(
            "<!-- {{#line}} --><p>{{slope}}</p><!-- {{/line}} --><p>{{gone}}</p>",
            {"line": {"slope": 3}})
        self.assertEqual(len(found), 1)
        self.assertIn("gone", found[0].detail)


class _ManyExercises(_StubOutcome):
    """`count` versions, all clean except the one at `bad`."""

    def __init__(self, slug, template, good, bad_data, count, bad):
        super().__init__(slug, template, good)
        self._exercises = [_StubExercise(bad_data if i == bad else good)
                           for i in range(count)]


class TheSpatextChecksReadPastTheFirstFewVersions(unittest.TestCase):
    """They read the first 4 and 8 seeds. Generators branch on PUBLIC_SEEDS
    and BUNDLE_UNTIL, so a fault in the instructor range was invisible."""

    def test_a_field_missing_only_in_a_late_version(self):
        outcome = _ManyExercises("X", "<p>{{a}}</p>", {"a": 1}, {}, 300, bad=250)
        found = checks.template_fields_without_data(_StubBank([outcome]))
        self.assertEqual([(f.check, f.count) for f in found], [("missing-data", 1)])

    def test_nested_markup_in_maths_in_a_late_version(self):
        from lxml import etree

        ns = 'xmlns="https://spatext.clontz.org"'
        clean = f'<knowl {ns}><content><p><m>x</m></p></content></knowl>'
        nested = f'<knowl {ns}><content><p><m>x<m>y</m></m></p></content></knowl>'

        class Ex:
            def __init__(self, xml):
                self.xml = xml

            def spatext_ele(self):
                return etree.fromstring(self.xml)

        outcome = _StubOutcome("X", "", {})
        outcome._exercises = [Ex(nested if i == 300 else clean) for i in range(400)]
        found = checks.nested_elements_in_math(_StubBank([outcome]))
        self.assertEqual([(f.check, f.count) for f in found], [("nested-in-m", 1)])


class TheBundlesGetEveryCheck(unittest.TestCase):
    """bundles() said it ran "the same checks" and re-implemented three of
    the seven. Each of these four was never looked for past seed 49."""

    def findings(self, formats):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = os.path.join(tmp.name, "assets", "X", "generated")
        os.makedirs(folder)
        with open(os.path.join(folder, "derived.json"), "w", encoding="utf-8") as f:
            json.dump({"slug": "X", "seeds": {"60": formats}}, f)
        return checks.bundles(tmp.name)

    def test_each(self):
        cases = {
            "escaped-markup": {"html": "<p>&lt;m&gt;x&lt;/m&gt;</p>"},
            "relative-img": {"html": '<img src="assets/X/60/p.png">'},
            "math-punctuation": {"html": '<span class="math inline-math" data-latex="x.">x</span>'},
            "latex-maths": {"latex": BS + "(a $ b" + BS + ")"},
        }
        for check, formats in cases.items():
            with self.subTest(check):
                found = self.findings(formats)
                self.assertEqual([f.check for f in found], [check])
                self.assertIn("in versions 50-399", found[0].detail)

    def test_a_clean_bundle_is_clean(self):
        self.assertEqual(self.findings({"html": "<p>fine</p>", "latex": "fine"}), [])


class WhatTheStylesheetsDropSilently(unittest.TestCase):
    """Every stylesheet turns an element it does not expect into nothing.
    Each case here is one the 2026-11-16 review found the renderers
    disagreeing on, or one that simply vanishes everywhere."""

    NS = 'xmlns="https://spatext.clontz.org"'

    def dropped(self, body):
        from lxml import etree
        root = etree.fromstring(f'<knowl {self.NS}>{body}</knowl>')
        return checks._dropped(root)

    def test_a_clean_exercise(self):
        self.assertEqual(self.dropped(
            "<title>T <m>x</m> <c>c</c> <q>q</q></title>"
            "<intro><p>Find <em>it</em>.</p></intro>"
            "<content><list><item><p><m>a</m></p></item></list></content>"
            "<outtro><p><q>b</q> <url href='h'>u</url></p></outtro>"), [])

    def test_content_beside_parts(self):
        found = self.dropped("<content><p>a</p></content>"
                             "<knowl><content><p>b</p></content></knowl>")
        self.assertEqual(len(found), 1)
        self.assertIn("both <content> and parts", found[0])

    def test_a_second_outtro(self):
        found = self.dropped("<content><p>a</p></content>"
                             "<outtro><p>1</p></outtro><outtro><p>2</p></outtro>")
        self.assertEqual(len(found), 1)
        self.assertIn("dropped in print", found[0])

    def test_distractors_are_not_a_second_outtro(self):
        """A multiple-choice question: print shows the correct one only,
        on purpose."""
        self.assertEqual(self.dropped(
            "<content><p>a</p></content><outtro><p>1</p></outtro>"
            "<outtro distractor='true'><p>2</p></outtro>"), [])

    def test_emphasis_in_a_title(self):
        self.assertEqual(self.dropped("<title><em>T</em></title>"),
                         ["<em> inside <title>"])

    def test_an_html_tag(self):
        """The demo's EX3 has a <ul> in an <intro>; all three drop it."""
        self.assertEqual(self.dropped("<intro><ul><li>a</li></ul></intro>"),
                         ["<ul> inside <intro>"])

    def test_text_outside_a_paragraph(self):
        self.assertEqual(self.dropped("<content>Solve it.</content>"),
                         ["text directly in <content>, outside a <p>"])

    def test_a_url_without_href(self):
        self.assertEqual(self.dropped("<content><p><url>x</url></p></content>"),
                         ["<url> without href"])

    def test_maths_is_left_to_its_own_check(self):
        self.assertEqual(self.dropped(
            "<content><p><m>x<m>y</m></m></p></content>"), [])

    def test_the_bank_level_check_counts_versions(self):
        from lxml import etree
        ns = self.NS

        class Ex:
            def __init__(self, xml):
                self.xml = xml

            def spatext_ele(self):
                return etree.fromstring(self.xml)

        outcome = _StubOutcome("X", "", {})
        outcome._exercises = [
            Ex(f'<knowl {ns}><title><em>t</em></title></knowl>' if i in (3, 700)
               else f'<knowl {ns}><title>t</title></knowl>')
            for i in range(1000)]
        found = checks.dropped_by_stylesheets(_StubBank([outcome]))
        self.assertEqual([(f.check, f.count) for f in found], [("dropped", 2)])


class RunAllRunsEveryCheck(unittest.TestCase):
    """A check written and not wired in reports a clean bank forever."""

    def test_the_spatext_checks_are_in_it(self):
        import tempfile
        from lxml import etree

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with open(os.path.join(tmp.name, "bank.json"), "w", encoding="utf-8") as f:
            json.dump({"outcomes": []}, f)

        class Bank(_StubBank):
            def build_path(self):
                return tmp.name

            def abspath(self):
                return tmp.name

        ns = 'xmlns="https://spatext.clontz.org"'

        class Ex:
            data = {}

            def __init__(self, bad):
                self.bad = bad

            def spatext_ele(self):
                if not self.bad:
                    return etree.fromstring(f"<knowl {ns}><title>t</title></knowl>")
                return etree.fromstring(
                    f"<knowl {ns}><title><em>t</em></title><content><p>"
                    f"<m>x<m>y</m></m></p></content></knowl>")

        # The bad one is a print-only version: run_all must read them.
        outcome = _StubOutcome("X", "", {})
        outcome._exercises = [Ex(i == 700) for i in range(1000)]
        kinds = {f.check for f in checks.run_all(Bank([outcome]))}
        self.assertTrue({"dropped", "nested-in-m"} <= kinds, kinds)


class TheTableKeepsUpWithTheStylesheets(unittest.TestCase):
    """`_HOLDS` is a second statement of what the stylesheets select. If a
    stylesheet learns a tag and the table does not, every use of it would
    be reported as dropped -- loud, but wrong. This fails first."""

    def test(self):
        from checkit.static import read_resource
        for sheet in ("html.xsl", "latex.xsl", "pretext.xsl"):
            text = read_resource(sheet)
            selected = set(re.findall(r"stx:([a-z-]+)", text))
            known = set(checks._HOLDS) | {"m", "me"}
            for holds in checks._HOLDS.values():
                known |= holds
            with self.subTest(sheet):
                self.assertEqual(selected - known, set())


if __name__ == "__main__":
    unittest.main()
