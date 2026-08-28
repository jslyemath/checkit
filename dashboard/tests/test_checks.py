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


if __name__ == "__main__":
    unittest.main()
