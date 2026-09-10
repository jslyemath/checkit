r"""A figure that compiled through an error is not a finished figure.

pdflatex recovers from most errors and writes a PDF anyway. The rasterizer
used to treat that PDF as success, so two wrong pictures reached a published
site without anything failing:

  - an undefined colour drew the answer dot black instead of the theme's blue
  - an undefined \dfrac dropped the fraction bar, so a number line labelled
    5/6 was published reading "56"

Both looked like clean builds. `generate` reported the figures compiled.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkit.wrapper.tikz import _log_errors


class LogErrorsTestCase(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".log", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.remove, handle.name)
        return handle.name

    def test_an_undefined_command_is_reported(self):
        """The \\dfrac case, in the form pdflatex actually logs it."""
        path = self.write(
            "This is pdfTeX\n"
            "! Undefined control sequence.\n"
            "l.7 ...x tick labels={$0$,$\\dfrac\n"
            "Output written on figure.pdf (1 page).\n"
        )
        self.assertEqual(_log_errors(path), ["! Undefined control sequence."])

    def test_an_unknown_key_is_reported(self):
        """The scCOLOR case: pgfkeys does not recognise the colour name."""
        path = self.write(
            "! Package pgfkeys Error: I do not know the key '/tikz/scCOLOR'.\n"
        )
        self.assertEqual(len(_log_errors(path)), 1)

    def test_a_clean_log_reports_nothing(self):
        """Warnings are left alone. Overfull boxes and font substitutions are
        normal in a figure, and reporting them would make this unusable."""
        path = self.write(
            "This is pdfTeX\n"
            "Overfull \\hbox (3.0pt too wide) in paragraph at lines 1--2\n"
            "LaTeX Font Warning: Font shape `OT1/ppl/m/n' undefined\n"
            "Package pgfplots Warning: running in backwards compatibility mode\n"
            "Output written on figure.pdf (1 page).\n"
        )
        self.assertEqual(_log_errors(path), [])

    def test_many_errors_are_truncated(self):
        """One broken figure can log hundreds of cascading errors; the first
        few say what is wrong and the rest are noise."""
        path = self.write("\n".join(f"! Error number {i}." for i in range(50)))

        reported = _log_errors(path, limit=8)

        self.assertEqual(len(reported), 9)
        self.assertIn("42 more", reported[-1])

    def test_a_missing_log_is_not_an_error(self):
        """pdflatex may die before writing one. That case is already caught by
        the check for a missing PDF, which reports the process output."""
        self.assertEqual(_log_errors("no-such-file.log"), [])


if __name__ == "__main__":
    unittest.main()
