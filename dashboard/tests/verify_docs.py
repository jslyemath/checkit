"""Check the guide's factual claims against the code.

Documentation drifts silently, and several claims here are the kind that read
fine while being wrong. These are the ones a reader would act on.
"""
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard"))

import checkit
from checkit import PUBLIC_SEEDS, BUNDLE_UNTIL

guide = {p.name: p.read_text(encoding="utf-8")
         for p in (ROOT / "guide").glob("*.md")}
guide["README.md"] = (ROOT / "README.md").read_text(encoding="utf-8")
everything = "\n".join(guide.values())

fails = []
def check(ok, label):
    print(("  ok   " if ok else "  FAIL ") + label)
    if not ok:
        fails.append(label)

print("version references")
check(f"v{checkit.VERSION}" in everything,
      f"install URL names the current version ({checkit.VERSION})")
old = re.findall(r"0\.2\.8\.\d+", everything)
check(all(v == checkit.VERSION for v in old),
      f"no stale version numbers (found {sorted(set(old))})")
print()

print("constants")
check(f"| {PUBLIC_SEEDS} |" in guide["cli.md"], f"PUBLIC_SEEDS ({PUBLIC_SEEDS}) documented")
check(f"| {BUNDLE_UNTIL} |" in guide["cli.md"], f"BUNDLE_UNTIL ({BUNDLE_UNTIL}) documented")
check(f"{BUNDLE_UNTIL - 1}" in everything, "the 400-999 tier is described")
print()

print("every CLI command and option appears")
help_main = subprocess.run([sys.executable, "-m", "checkit", "--help"],
                           capture_output=True, text=True, cwd=ROOT).stdout
commands = re.findall(r"^  ([a-z]+)\s", help_main, re.M)
for c in commands:
    check(f"`checkit {c}" in everything or f"checkit {c}" in everything,
          f"command: {c}")
for c in ("generate", "check", "new"):
    h = subprocess.run([sys.executable, "-m", "checkit", c, "--help"],
                       capture_output=True, text=True, cwd=ROOT).stdout
    for opt in sorted(set(re.findall(r"(--[a-z][a-z-]+)", h))):
        if opt in ("--help",):
            continue
        check(opt in everything, f"{c} option: {opt}")
print()

print("bank.xml elements the parser actually reads")
bank_src = (ROOT / "dashboard/checkit/bank.py").read_text(encoding="utf-8")
for tag in re.findall(r'CHECKIT_NS\}([a-z-]+)', bank_src):
    if tag in ("outcomes",):
        continue
    check(f"<{tag}>" in everything, f"documented: <{tag}>")
for tag in re.findall(r'has_flag\(ele, "([a-z-]+)"\)', bank_src):
    check(f"<{tag}/>" in everything, f"documented: <{tag}/>")
for tag in set(re.findall(r'optional_text\((?:ele|xml), "([a-z-]+)"\)', bank_src)):
    check(f"<{tag}>" in everything, f"documented: <{tag}>")
print()

print("SpaTeXt elements in parseDisplay")
html_xsl = (ROOT / "dashboard/checkit/static/html.xsl").read_text(encoding="utf-8")
select = re.search(r'parseDisplay">\s*<xsl:apply-templates select="([^"]+)"', html_xsl)
for name in re.findall(r"stx:([a-z-]+)", select.group(1)):
    check(f"<{name}" in everything, f"documented: <{name}>")
print()

print("things that must NOT be documented as platform features")
# These appear in some banks' own bank.xml and are read only by that bank's
# tooling. The guide may *mention* them -- it warns that CheckIt ignores them --
# but must never present them as supported.
for absent in ("color_map", "<category"):
    check(absent not in everything, f"not claimed: {absent}")
assoc = [l for l in everything.splitlines() if "<associate>" in l]
check(len(assoc) <= 1 and "yours, not the platform" in everything,
      "<associate> mentioned only in the not-a-feature warning")
check("pip install --upgrade checkit-dashboard" not in everything,
      "no bare PyPI install instruction")
check("twine upload" not in everything, "no PyPI upload instruction")
check("StevenClontz/checkit/wiki" not in everything, "no link to upstream's wiki")
print()

print("internal links resolve")
for name, text in guide.items():
    for link in re.findall(r"\]\(([a-zA-Z0-9_./-]+\.md)(?:#[^)]*)?\)", text):
        base = ROOT if name == "README.md" else ROOT / "guide"
        check((base / link).exists(), f"{name} -> {link}")
print()

print("RESULT:", "all claims verified" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
