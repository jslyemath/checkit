"""Guards on what actually ends up in an installed copy.

These exist because of a bug that only appears outside the development
environment. `sympy` was added to setup.cfg when the plain-Python generator
runtime landed, but not to the duplicate list in setup.py -- and setuptools uses
setup.py's, because a setup() keyword overrides the .cfg. Every wheel built from
this repo therefore shipped without sympy, and every bank generated from such an
install died with ModuleNotFoundError.

It was invisible here for months: the dev venv is an *editable* install into an
environment where sympy was already present, so nothing ever exercised the
dependency list. Only building a wheel and installing it into a clean venv shows
it, which is not something anyone does by accident.
"""

import ast
import configparser
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DASHBOARD = os.path.join(ROOT, "dashboard")


def cfg_requires():
    parser = configparser.ConfigParser()
    parser.read(os.path.join(DASHBOARD, "setup.cfg"), encoding="utf-8")
    raw = parser.get("options", "install_requires")
    return {line.strip() for line in raw.splitlines() if line.strip()}


def py_requires():
    """Read setup.py's list without executing it."""
    with open(os.path.join(DASHBOARD, "setup.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "setup":
            for kw in node.keywords:
                if kw.arg == "install_requires":
                    return set(ast.literal_eval(kw.value))
    raise AssertionError("no setup(install_requires=[...]) found in setup.py")


class InstallRequires(unittest.TestCase):
    def test_the_two_dependency_lists_agree(self):
        """setup.py wins, so anything only in setup.cfg is missing from wheels."""
        cfg, py = cfg_requires(), py_requires()
        self.assertEqual(
            cfg,
            py,
            "setup.cfg and setup.py declare different dependencies.\n"
            f"  only in setup.cfg: {sorted(cfg - py)}\n"
            f"  only in setup.py : {sorted(py - cfg)}\n"
            "setuptools uses setup.py's list, so anything missing there is "
            "absent from an installed copy even though it works in the "
            "editable dev environment.",
        )

    def test_sympy_is_declared(self):
        """The default generator runtime imports it; without it every bank
        fails to generate on a clean install."""
        self.assertIn("sympy", py_requires())

    def test_matplotlib_stays_optional(self):
        """Only banks calling plot() need it, and tikz_graphics() needs no
        plotting library at all, so it must not be a hard dependency."""
        self.assertNotIn("matplotlib", py_requires())
        self.assertNotIn("matplotlib", cfg_requires())


class VersionString(unittest.TestCase):
    """The version has to survive being a GitHub release asset's filename.

    '0.2.8+slye.1' is what this fork means semantically -- a PEP 440 local
    version -- but GitHub rewrites '+' to '.' on upload, producing
    checkit_dashboard-0.2.8.slye.1-py3-none-any.whl, which pip rejects with
    "Invalid wheel filename (invalid version)". Measured, not assumed.
    """

    def test_version_is_safe_in_a_wheel_filename(self):
        from checkit import VERSION

        self.assertNotIn("+", VERSION, "GitHub Releases rewrites '+' to '.'")
        self.assertRegex(VERSION, r"^\d+(\.\d+)*$")

    def test_version_differs_from_upstream(self):
        """checkit-dashboard 0.2.8 on PyPI is Steven Clontz's package and is
        different code; sharing its version makes them indistinguishable."""
        from checkit import VERSION

        self.assertNotEqual(VERSION, "0.2.8")


class PackagedFiles(unittest.TestCase):
    def test_static_resources_the_runtime_reads_are_declared(self):
        """package_data must cover static/ and wrapper/, or an installed copy
        has the Python but none of the stylesheets, scaffolds, or viewer."""
        parser = configparser.ConfigParser()
        parser.read(os.path.join(DASHBOARD, "setup.cfg"), encoding="utf-8")
        declared = parser.get("options.package_data", "checkit")
        for needed in ("static/*", "wrapper/*"):
            self.assertIn(needed, declared)

    def test_the_stylesheets_are_present_to_be_packaged(self):
        for name in ("html.xsl", "latex.xsl", "pretext.xsl"):
            with self.subTest(stylesheet=name):
                self.assertTrue(os.path.isfile(
                    os.path.join(DASHBOARD, "checkit", "static", name)))


if __name__ == "__main__":
    unittest.main()
