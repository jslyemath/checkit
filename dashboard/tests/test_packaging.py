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
import tempfile
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


class GenerateAmountGuard(unittest.TestCase):
    """`checkit generate -a N` with N below PUBLIC_SEEDS produces a bank the
    viewer mishandles in two ways that are both silent in the browser: the
    version picker offers versions that were never generated, and the assessment
    builder computes a negative seed range. The CLI refuses instead."""

    def test_amount_below_public_seeds_is_refused(self):
        import click
        from click.testing import CliRunner

        from checkit import PUBLIC_SEEDS
        from checkit.__main__ import generate

        result = CliRunner().invoke(generate, ["--amount", str(PUBLIC_SEEDS - 1)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--amount", result.output)
        self.assertIn(str(PUBLIC_SEEDS), result.output)


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


class BankHelpersSty(unittest.TestCase):
    """The .sty counterpart of bank_helpers.py.

    It exists so a bank has somewhere to put the macros its *content* needs --
    \babo, hieroglf -- separate from anything about how a page looks. Two
    things have to hold or it is decoration: `checkit new` must create it, so
    an author knows it is there; and figure compilation must load it, since a
    figure emitting a bank macro has to be able to compile it.
    """

    def test_it_ships_in_the_package(self):
        from checkit import static
        source = static.read_resource("bank_helpers.sty")
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        self.assertIn("ProvidesPackage{bank_helpers}", source)

    def test_checkit_new_creates_it(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "checkit", "__main__.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"bank_helpers.sty"', source,
                      "checkit new does not scaffold bank_helpers.sty")

    def test_figure_compilation_loads_it_when_present(self):
        from checkit.wrapper import tikz
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotIn("bank_helpers", tikz._load_preamble(tmp),
                             "a bank without the file should not load it")
            with open(os.path.join(tmp, "bank_helpers.sty"), "w") as f:
                f.write("\ProvidesPackage{bank_helpers}\n")
            self.assertIn("bank_helpers", tikz._load_preamble(tmp))

    def test_a_custom_tikz_preamble_still_wins(self):
        """It carries its own \documentclass, so it replaces rather than adds --
        which means a bank writing one takes responsibility for loading the
        helpers itself. The demo bank's does exactly that."""
        from checkit.wrapper import tikz
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "bank_helpers.sty"), "w") as f:
                f.write("\ProvidesPackage{bank_helpers}\n")
            with open(os.path.join(tmp, "tikz_preamble.tex"), "w") as f:
                f.write("\documentclass[tikz]{standalone}\n")
            self.assertNotIn("bank_helpers", tikz._load_preamble(tmp))
