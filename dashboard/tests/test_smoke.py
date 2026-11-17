"""`checkit check` runs every generator the bank declares.

RV-14 of the 2026-11-16 review: `smoke.run_generators` globbed
`outcomes/*/generator.py` and used the folder name as the slug, so a
generator kept one folder deeper -- seven of the demo bank's eleven --
was never run. It now asks the Bank which outcomes exist and where.

It also called only `data()`. A generator can fail later, in
`tikz_graphics()` or in turning its values into JSON, which is what
`generate` actually does next; those are exercised too.
"""

import os
import shutil
import tempfile
import unittest

from checkit import smoke
from checkit.bank import Bank

DEMO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "demo-bank")

BANK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Smoke</title>
    <slug>smoke</slug>
    <url>https://example.org</url>
    <outcomes>
        <outcome>
            <title>Deep</title>
            <slug>DEEP</slug>
            <path>outcomes/GROUP/DEEP</path>
            <description>Two folders down.</description>
        </outcome>
    </outcomes>
</bank>
"""


class EveryDeclaredGenerator(unittest.TestCase):
    def test_the_demo_bank_is_smoked_in_full(self):
        found = [slug for slug, _ in smoke.run_generators(DEMO)]
        self.assertEqual(sorted(found),
                         sorted(o.slug for o in Bank(DEMO).outcomes()))


class ANestedFailure(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "outcomes", "GROUP", "DEEP"))
        with open(os.path.join(self.tmp, "bank.xml"), "w", encoding="utf-8") as f:
            f.write(BANK_XML)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def generator(self, body):
        with open(os.path.join(self.tmp, "outcomes", "GROUP", "DEEP",
                               "generator.py"), "w", encoding="utf-8") as f:
            f.write(body)

    def test_a_broken_nested_generator_is_reported(self):
        self.generator("class Generator(BaseGenerator):\n"
                       "    def data(self):\n        return {'x': 1 / 0}\n")
        [(slug, tb)] = list(smoke.run_generators(self.tmp))
        self.assertEqual(slug, "DEEP")
        self.assertIn("ZeroDivisionError", tb)

    def test_a_failure_in_the_figure_is_reported(self):
        self.generator("class Generator(BaseGenerator):\n"
                       "    def data(self):\n        return {'x': '1'}\n"
                       "    @provide_data\n"
                       "    def tikz_graphics(data):\n"
                       "        return {'f': data['missing']}\n")
        [(slug, tb)] = list(smoke.run_generators(self.tmp))
        self.assertIn("KeyError", tb)

    def test_a_good_generator_passes(self):
        self.generator("class Generator(BaseGenerator):\n"
                       "    def data(self):\n        return {'x': '1'}\n")
        self.assertEqual(list(smoke.run_generators(self.tmp)), [("DEEP", None)])


if __name__ == "__main__":
    unittest.main()
