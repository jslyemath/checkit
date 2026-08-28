"""Structural checks on a built bank, and on its generators.

Every one of these exists because a real build shipped the fault it catches
while everything else looked healthy. They are deliberately structural: they
answer "will this render as something other than what it says", not "is this
good mathematics".

Two things they are not:

* not a substitute for looking at the page -- three of these were written after
  a human spot-check found what the automated checks had passed;
* not typographic -- a line breaking in an ugly place is invisible here.

Each check returns a list of Finding. `run_all` is what `checkit check` calls.
"""

import collections
import glob
import json
import os
import re

from .xml import CHECKIT_NS  # noqa: F401  (kept for symmetry with bank.py)

BS = chr(92)

SPATEXT_NS = "https://spatext.clontz.org"
M = "{%s}m" % SPATEXT_NS

Finding = collections.namedtuple("Finding", "check slug detail count")


# ---------------------------------------------------------------------------
# HTML-side checks
# ---------------------------------------------------------------------------

_MATH_SPAN = re.compile(r'<span class="math[^"]*"[^>]*>.*?</span>', re.S)
_TAGS = re.compile(r"<[^>]+>", re.S)
_WORD_CMD = re.compile(re.escape(BS) + r"[a-zA-Z]{2,}")
# Single-character escapes matter as much as commands: an earlier version of
# this check required two or more letters and reported a confident clean while
# an outcome showed students "27.6\%" and "\$770.13" in 300 places.
_CHAR_ESC = re.compile(re.escape(BS) + r"[%$&_#{}]")


def _visible_text(html):
    """The text a reader sees: tags gone, and maths spans removed first.

    Maths legitimately contains backslashes, so it has to come out before the
    search rather than be filtered afterwards.
    """
    return _TAGS.sub(" ", _MATH_SPAN.sub(" ", html))


def raw_tex_in_prose(bank_json):
    """TeX that escaped its maths context and renders as literal text."""
    out = []
    hits = collections.Counter()
    for outcome in bank_json["outcomes"]:
        for exercise in outcome["exercises"]:
            html = exercise.get("html")
            if not html:
                continue
            text = _visible_text(html)
            for pattern in (_WORD_CMD, _CHAR_ESC):
                for match in pattern.finditer(text):
                    hits[(outcome["slug"], match.group())] += 1
    for (slug, token), count in sorted(hits.items()):
        out.append(Finding("raw-tex", slug, "%r renders literally" % token, count))
    return out


_ESCAPED_MARKUP = re.compile(r"&lt;\s*(m|glyphs|nobreak|em)\b", re.I)


def escaped_markup(bank_json):
    """Markup injected through {{double braces}}, which Mustache escapes.

    The student sees "&lt;m&gt;" instead of mathematics.
    """
    out = []
    hits = collections.Counter()
    for outcome in bank_json["outcomes"]:
        for exercise in outcome["exercises"]:
            for fmt in ("html", "latex", "pretext"):
                value = exercise.get(fmt)
                if value and _ESCAPED_MARKUP.search(value):
                    hits[(outcome["slug"], fmt)] += 1
    for (slug, fmt), count in sorted(hits.items()):
        out.append(Finding("escaped-markup", slug,
                           "escaped markup in %s; the template needs triple braces" % fmt,
                           count))
    return out


_CONTROL = {"\t": "\\t", "\v": "\\v", "\f": "\\f",
            "\b": "\\b", "\a": "\\a", "\x00": "\\0", "\r": "\\r"}
_CONTROL_RE = re.compile("[" + "".join(re.escape(c) for c in _CONTROL) + "]")


def control_characters(bank_json):
    """Non-raw Python literals eating LaTeX commands.

    "\\textpmhg" in a non-raw string is a TAB followed by "extpmhg". \\n is
    excluded because it is legitimate in generated LaTeX; the rest never are.
    """
    out = []
    hits = collections.Counter()
    for outcome in bank_json["outcomes"]:
        for exercise in outcome["exercises"]:
            for fmt in ("html", "latex", "pretext"):
                value = exercise.get(fmt)
                if not value:
                    continue
                for match in _CONTROL_RE.finditer(value):
                    hits[(outcome["slug"], fmt, _CONTROL[match.group()])] += 1
    for (slug, fmt, name), count in sorted(hits.items()):
        out.append(Finding("control-char", slug,
                           "%s in %s; a non-raw string literal" % (name, fmt), count))
    return out


_REL_IMG = re.compile(r'<img[^>]+src="(?!https?://)', re.I)


def relative_image_src(bank_json):
    """Root-relative <img src>, which 404s wherever the HTML is displayed."""
    out = []
    hits = collections.Counter()
    for outcome in bank_json["outcomes"]:
        for exercise in outcome["exercises"]:
            html = exercise.get("html")
            if html and _REL_IMG.search(html):
                hits[outcome["slug"]] += 1
    for slug, count in sorted(hits.items()):
        out.append(Finding("relative-img", slug, "root-relative <img src>; pass --remote", count))
    return out


# ---------------------------------------------------------------------------
# SpaTeXt-side check: the one the HTML cannot show
# ---------------------------------------------------------------------------

def nested_elements_in_math(bank, seeds=8):
    """<m> elements containing other elements.

    html.xsl and latex.xsl both render <m> with normalize-space(text()), which
    concatenates only the DIRECT text children. Any element inside -- a nested
    <m> from spatext_math, a <glyphs> -- is silently discarded, and the prose
    between them survives, typeset as mathematics.

    This reads the SpaTeXt rather than the output, because by the time it is
    HTML the evidence has been deleted. It is the check that would have caught
    an outcome rendering "is a multiple of" with both numbers gone.
    """
    out = []
    hits = collections.Counter()
    for outcome in bank.outcomes():
        for exercise in outcome.exercises()[:seeds]:
            try:
                root = exercise.spatext_ele()
            except Exception as exc:                      # pragma: no cover
                out.append(Finding("spatext-error", outcome.slug, str(exc), 1))
                break
            for math in root.iter(M):
                children = list(math)
                if children:
                    names = ",".join(c.tag.split("}")[-1] for c in children)
                    hits[(outcome.slug, names)] += 1
    for (slug, names), count in sorted(hits.items()):
        out.append(Finding("nested-in-m", slug,
                           "<m> contains <%s>; its content is dropped" % names, count))
    return out


_MUSTACHE = re.compile(r"\{\{\{?\s*([#^/&]?)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\}\}")

# Retired blocks are left commented out rather than deleted, and their fields
# are naturally absent from the data. Mustache does substitute inside an XML
# comment -- which is how F2-E smuggles {{#section}} tags past the XML parser
# -- but the comment is then discarded by the stylesheets, so nothing there
# can render either way.
_XML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def template_fields_without_data(bank, seeds=4):
    """Template fields the generator never supplies.

    Mustache renders an absent key as the empty string, so the sentence around
    it survives and the value vanishes: "explaining the  to an elementary
    school student?". Nothing fails, and the exercise is unanswerable.

    Section tags ({{#x}}, {{^x}}, {{/x}}) are excluded -- an absent key there
    means "false", which is the whole point of them -- as is `__seed__`, which
    the renderer injects.
    """
    out = []
    hits = collections.Counter()
    for outcome in bank.outcomes():
        try:
            template = outcome.template()
        except Exception:                                  # pragma: no cover
            continue
        referenced = {
            name for sigil, name in _MUSTACHE.findall(_XML_COMMENT.sub(" ", template))
            if sigil not in ("#", "^", "/") and name != "__seed__"
        }
        if not referenced:
            continue
        for exercise in outcome.exercises()[:seeds]:
            missing = referenced - set(exercise.data.keys())
            for name in missing:
                hits[(outcome.slug, name)] += 1
    for (slug, name), count in sorted(hits.items()):
        out.append(Finding("missing-data", slug,
                           "template uses {{%s}}, which the generator never sets; "
                           "it renders as nothing" % name, count))
    return out


# ---------------------------------------------------------------------------
# Print-side checks: a different stylesheet, with its own ways to fail
# ---------------------------------------------------------------------------

def brace_balance(s):
    """Grouping depth, ignoring escaped braces. Negative means it closed too
    early, which is as broken as never closing."""
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == BS and i + 1 < len(s):
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                return -1
        i += 1
    return depth


_INLINE_MATH = re.compile(re.escape(BS) + r"\((.*?)" + re.escape(BS) + r"\)", re.S)

# Deliberately short. \text{...}, \mbox{...} and \textbf{...} are all *legal*
# inside math mode and all appear on purpose here -- W1 sets Roman numerals
# with \text{}, and the outcome-title element emits \(\textbf{W1}\). Flagging
# them produced 976 findings against a correct bank, which is how a check
# teaches people to ignore it.
#
# What actually broke was `\(\mbox{\)`: an unbalanced brace, which the balance
# check above catches on its own. So this list holds only what cannot be
# legal.
_ILLEGAL_IN_MATH = (BS + "par",)


def latex_structure(bank_json):
    """Documents that will not compile, and maths that leaked text-mode."""
    out = []
    unbalanced = collections.Counter()
    inner = collections.Counter()
    for outcome in bank_json["outcomes"]:
        for exercise in outcome["exercises"]:
            latex = exercise.get("latex")
            if not latex:
                continue
            if brace_balance(latex) != 0:
                unbalanced[outcome["slug"]] += 1
            for match in _INLINE_MATH.finditer(latex):
                body = match.group(1)
                if brace_balance(body) != 0:
                    inner[(outcome["slug"], "unbalanced braces")] += 1
                if "$" in body.replace(BS + "$", ""):
                    inner[(outcome["slug"], "unescaped $ inside maths")] += 1
                for command in _ILLEGAL_IN_MATH:
                    if command in body:
                        inner[(outcome["slug"], "%s inside maths" % command)] += 1
    for slug, count in sorted(unbalanced.items()):
        out.append(Finding("latex-braces", slug,
                           "unbalanced braces; this document will not compile", count))
    for (slug, what), count in sorted(inner.items()):
        out.append(Finding("latex-maths", slug, what, count))
    return out


_MONEY_PUNCT = re.compile(r'data-latex="[^"]*[.,]"')


def punctuation_in_inline_math(bank_json):
    """Sentence punctuation pulled inside inline maths.

    A greedy money pattern turned "worth \\$982.69." into "<m>\\$982.69.</m>",
    setting the full stop in italics. Display maths is exempt: punctuation
    inside a displayed equation is correct typesetting.
    """
    out = []
    hits = collections.Counter()
    pattern = re.compile(r'<span class="math inline-math" data-latex="([^"]*[.,])"')
    for outcome in bank_json["outcomes"]:
        for exercise in outcome["exercises"]:
            html = exercise.get("html")
            if html:
                for _ in pattern.finditer(html):
                    hits[outcome["slug"]] += 1
    for slug, count in sorted(hits.items()):
        out.append(Finding("math-punctuation", slug,
                           "inline maths ends in . or , -- punctuation inside the maths",
                           count))
    return out


# ---------------------------------------------------------------------------
# Bundles: what print and the LMS export actually read
# ---------------------------------------------------------------------------

def bundles(bank_path):
    """The same checks over derived.json.

    bank.json inlines only the public seeds, so a clean bank.json says nothing
    about the versions an assessment draws from. One bug lived 334 times in
    here and 48 times in bank.json.
    """
    out = []
    hits = collections.Counter()
    pattern = os.path.join(bank_path, "assets", "*", "generated", "derived.json")
    for path in glob.glob(pattern):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        slug = data.get("slug")
        for _, formats in data.get("seeds", {}).items():
            for fmt, value in formats.items():
                if not isinstance(value, str):
                    continue
                for match in _CONTROL_RE.finditer(value):
                    hits[(slug, "control %s" % _CONTROL[match.group()])] += 1
                if fmt == "html":
                    text = _visible_text(value)
                    for p in (_WORD_CMD, _CHAR_ESC):
                        for match in p.finditer(text):
                            hits[(slug, "raw %r" % match.group())] += 1
                if fmt == "latex" and brace_balance(value) != 0:
                    hits[(slug, "unbalanced braces")] += 1
    for (slug, what), count in sorted(hits.items()):
        out.append(Finding("bundle", slug, what, count))
    return out


# ---------------------------------------------------------------------------

def run_all(bank):
    """Every check, against a built bank. Returns a flat list of Finding."""
    path = os.path.join(bank.build_path(), "bank.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    findings = []
    findings += escaped_markup(doc)
    findings += raw_tex_in_prose(doc)
    findings += control_characters(doc)
    findings += relative_image_src(doc)
    findings += punctuation_in_inline_math(doc)
    findings += latex_structure(doc)
    findings += nested_elements_in_math(bank)
    findings += template_fields_without_data(bank)
    findings += bundles(bank.abspath())
    return findings
