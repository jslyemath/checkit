"""Prose reaches LaTeX as the reader wrote it.

latex.xsl used to copy text outside <m> straight into the LaTeX. The web
shows that text exactly as written, so the two disagreed whenever prose held
one of the ten characters LaTeX reads as an instruction: "50% off" printed
as "50" (the % starts a comment), an & stopped the compile, and braces
vanished. mat-106's W7 showed students "9{,}456" on the web for weeks; the
printed copy would have shown "9,456" -- right by accident.

Maths is not prose. <m>, <me> and a <glyphs latex="..."> attribute are LaTeX
already and must come through untouched.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from lxml import etree

from checkit.static import read_resource

NS = 'xmlns="https://spatext.clontz.org" version="0.3"'

PROSE = r"50% off & {braced} a_b #1 $5 ~ ^ \ end"


def latex(body):
    doc = f'<knowl mode="exercise" {NS}><content>{body}</content></knowl>'
    transform = etree.XSLT(etree.fromstring(read_resource("latex.xsl")))
    return str(transform(etree.fromstring(doc.encode("utf-8"))))


def body_of(rendered):
    """What sits inside \\stxKnowl{...}, without the definitions above it."""
    return rendered.split("%" * 28, 1)[1].strip()


class EveryReservedCharacterIsEscaped(unittest.TestCase):

    def test_in_a_paragraph(self):
        got = body_of(latex(f"<p>{PROSE.replace('&', '&amp;')}</p>"))
        self.assertIn(
            r"50\% off \& \{braced\} a\_b \#1 \$5 \textasciitilde{} "
            r"\textasciicircum{} \textbackslash{} end", got)

    def test_in_code(self):
        got = body_of(latex("<p><c>file_name.tex</c></p>"))
        self.assertIn(r"\texttt{file\_name.tex}", got)

    def test_in_a_title_and_emphasis_and_a_quote(self):
        doc = (f'<knowl mode="exercise" {NS}><title>Save 10%</title>'
               "<content><p><em>a_b</em> <q>c_d</q></p></content></knowl>")
        transform = etree.XSLT(etree.fromstring(read_resource("latex.xsl")))
        got = str(transform(etree.fromstring(doc.encode("utf-8"))))
        self.assertIn(r"\stxTitle{Save 10\%}", got)
        self.assertIn(r"\textbf{a\_b}", got)
        self.assertIn(r"``c\_d''", got)

    def test_in_glyphs_without_a_latex_attribute(self):
        got = body_of(latex("<p><glyphs>a_b</glyphs></p>"))
        self.assertIn(r"a\_b", got)

    def test_a_long_paragraph_does_not_hit_the_recursion_limit(self):
        # libxslt stops at a depth of 3000. Recursing once per special
        # character -- the first version -- failed here.
        got = body_of(latex("<p>" + "_" * 20000 + "</p>"))
        self.assertEqual(got.count(r"\_"), 20000)

    def test_plain_text_and_whitespace_are_unchanged(self):
        got = body_of(latex("<p>Solve <m>x</m> for the  value.</p>"))
        self.assertIn(r"Solve \(x\) for the value.", got)


class MathsIsLeftAlone(unittest.TestCase):

    def test_inline_and_display(self):
        got = body_of(latex(r"<p><m>\text{ 9{,}456 } \% x_1</m></p>"
                            r"<p><me>a &amp; b \\ c</me></p>"))
        self.assertIn(r"\(\text{ 9{,}456 } \% x_1\)", got)
        self.assertIn(r"\[a & b \\ c\]", got)

    def test_a_glyphs_latex_attribute(self):
        got = body_of(latex(r'<p><glyphs latex="\Large\Hone">x</glyphs></p>'))
        self.assertIn(r"{\Large\Hone}", got)


@unittest.skipUnless(shutil.which("pdflatex"), "needs pdflatex")
class ItPrintsWhatTheWebShows(unittest.TestCase):
    """The strings above are what we think LaTeX needs. This is LaTeX saying
    so: the escaped prose compiles, and the PDF's text is the prose."""

    def test_compiled(self):
        try:
            import pypdfium2
        except ImportError:
            self.skipTest("needs pypdfium2 to read the PDF back")
        rendered = latex(f"<p>{PROSE.replace('&', '&amp;')}</p>")
        tex = ("\\documentclass{article}\\usepackage[T1]{fontenc}"
               "\\pagestyle{empty}"  # or the page number is read back too
               "\\begin{document}\n" + rendered + "\n\\end{document}\n")
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "t.tex"), "w", encoding="utf-8") as f:
                f.write(tex)
            run = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "t.tex"],
                cwd=tmp, capture_output=True, text=True, errors="replace")
            self.assertEqual(run.returncode, 0, run.stdout[-2000:])
            pdf = pypdfium2.PdfDocument(os.path.join(tmp, "t.pdf"))
            text = pdf[0].get_textpage().get_text_range()
            pdf.close()
        self.assertEqual(" ".join(text.split()), PROSE)


if __name__ == "__main__":
    unittest.main()
