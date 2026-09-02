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


if __name__ == "__main__":
    unittest.main()
