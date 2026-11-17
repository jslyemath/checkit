"""Every file CheckIt reads or writes is UTF-8, whatever the machine's locale.

RV-6 of the 2026-11-16 review. `open(path)` with no encoding uses the
locale's, which on this Windows machine is cp1252. A template is read to
be published in bank.json, and the viewer renders the student's page from
that text -- so an em dash came out as three wrong characters. One mat-106
template, R2's, already has one (inside an XML comment, so nothing shows).

And cp1252 has five bytes with no meaning at all. A curly closing quote is
E2 80 9D in UTF-8, and 9D is one of them, so that character in a template
was not garbage but a crash.

The test forces the locale's encoding to cp1252 rather than relying on the
machine it runs on, so it means the same thing everywhere.
"""

import builtins
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from checkit.bank import Bank

NS = 'xmlns="https://spatext.clontz.org" version="0.3"'
PROSE = "The operation you chose — and “why”, for Renée."
TEMPLATE = f"""<knowl mode="exercise" {NS}>
    <content><p>{PROSE}</p></content>
    <outtro><p>Answer.</p></outtro>
</knowl>"""

BANK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Encoding</title>
    <slug>enc</slug>
    <url>https://example.org</url>
    <outcomes>
        <outcome>
            <title>Prose — with a dash</title>
            <slug>P1</slug>
            <path>outcomes/P1</path>
            <description>An outcome whose prose is not ASCII — at all.</description>
        </outcome>
    </outcomes>
</bank>
"""

GENERATOR = '''
class Generator(BaseGenerator):
    def data(self):
        return {"n": "1"}

    @provide_data
    def tikz_graphics(data):
        return {"fig": "\\\\node {Ren\\u00e9e};"}
'''


def as_if_cp1252():
    """`open` behaving as it does here: text mode without an encoding
    means cp1252."""
    real = builtins.open

    def opener(file, mode="r", buffering=-1, encoding=None, *args, **kw):
        if "b" not in mode and encoding is None:
            encoding = "cp1252"
        return real(file, mode, buffering, encoding, *args, **kw)
    return mock.patch.object(builtins, "open", opener)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = os.path.join(self.tmp, "outcomes", "P1")
        os.makedirs(d)
        with open(os.path.join(d, "template.xml"), "w", encoding="utf-8") as f:
            f.write(TEMPLATE)
        with open(os.path.join(d, "generator.py"), "w", encoding="utf-8") as f:
            f.write(GENERATOR)
        with open(os.path.join(self.tmp, "bank.xml"), "w", encoding="utf-8") as f:
            f.write(BANK_XML)
        gen = os.path.join(self.tmp, "assets", "P1", "generated")
        os.makedirs(gen)
        with open(os.path.join(gen, "seeds.json"), "w", encoding="utf-8") as f:
            json.dump({"seeds": [{"seed": i, "data": {"n": "1"}}
                                 for i in range(60)],
                       "generated_on": "2026-11-17T00:00:00+00:00"}, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bank_json(self):
        with open(os.path.join(self.tmp, "assets", "bank.json"),
                  encoding="utf-8") as f:
            return json.load(f)


class TheBankIsPublishedInUtf8(Base):
    def test_the_template_reaches_bank_json_unchanged(self):
        with as_if_cp1252():
            Bank(self.tmp).write_json(remote="https://example.org")
        outcome = self.bank_json()["outcomes"][0]
        self.assertIn(PROSE, outcome["template"])

    def test_the_precomputed_html_agrees_with_it(self):
        """The student page renders from `template`; the LMS export and
        the instructor tabs from `html`. They have to say the same."""
        with as_if_cp1252():
            Bank(self.tmp).write_json(remote="https://example.org")
        import html
        exercise = self.bank_json()["outcomes"][0]["exercises"][0]
        # lxml writes non-ASCII as character references (&#8212;), which a
        # browser renders as the character; compare what is rendered.
        self.assertIn(PROSE, html.unescape(exercise["html"]))

    def test_the_bank_xml_title_and_description_survive(self):
        with as_if_cp1252():
            Bank(self.tmp).write_json(remote="https://example.org")
        outcome = self.bank_json()["outcomes"][0]
        self.assertEqual(outcome["title"], "Prose — with a dash")


class GeneratedFilesAreUtf8(Base):
    """The wrapper runs as a subprocess, so it is forced into cp1252 the
    honest way: an environment that says so."""

    def test_a_tikz_figure_is_written_in_utf8(self):
        env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp1252")
        env.pop("PYTHONUTF8", None)
        wrapper = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "checkit", "wrapper", "wrapper.py")
        out = os.path.join(self.tmp, "assets", "P1", "generated", "seeds.json")
        subprocess.run(
            [sys.executable, "-X", "utf8=0", wrapper,
             os.path.join(self.tmp, "outcomes", "P1", "generator.py"),
             out, "2", "no"],
            cwd=self.tmp, env=env, check=True, capture_output=True)
        raw = open(os.path.join(self.tmp, "assets", "P1", "generated",
                                "0000", "fig.tikz"), "rb").read()
        self.assertIn("Renée".encode("utf-8"), raw)


if __name__ == "__main__":
    unittest.main()
