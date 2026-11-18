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

from . import BUNDLE_UNTIL, PUBLIC_SEEDS
from .xml import CHECKIT_NS  # noqa: F401  (kept for symmetry with bank.py)

# The two SpaTeXt-side checks below read every version a site publishes
# (seeds below BUNDLE_UNTIL), and the data check every version there is.
# They read the first 8 and 4: generators are handed PUBLIC_SEEDS and
# BUNDLE_UNTIL precisely so they can branch on them, and a fault in the
# instructor range was invisible (review, 2026-11-16). Affordable since
# stylesheets and templates are compiled once (2026-11-17).

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
# A bare brace, with no backslash for either pattern above to see. mat-106's
# W7 showed students "9{,}456 remainder 734" for weeks: a LaTeX thousands
# separator typed into plain text, literal on the web and swallowed as
# grouping in print (2026-11-17). An escaped brace is _CHAR_ESC's, so it is
# not counted twice.
_BRACE = re.compile(r"(?<!" + re.escape(BS) + r")[{}]")
# A leaked command with its argument, so the argument's braces are not
# reported a second time: `\text{MDCXLVIII}` is one leak, not three.
_CMD_WITH_ARG = re.compile(re.escape(BS) + r"[a-zA-Z]+(\{[^{}]*\})?")


def _prose_leaks(text):
    """Every leaked TeX token in visible text. One list, used by both the
    bank.json check and the bundle check: they kept separate copies, and
    a pattern added to one would have been missing from the other."""
    found = [m.group() for p in (_WORD_CMD, _CHAR_ESC) for m in p.finditer(text)]
    found += [m.group() for m in _BRACE.finditer(_CMD_WITH_ARG.sub(" ", text))]
    return found


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
            for token in _prose_leaks(_visible_text(html)):
                hits[(outcome["slug"], token)] += 1
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

def _nested_in_math(root):
    """The tags inside each <m> of `root` that has any, as "a,b" strings."""
    return [",".join(c.tag.split("}")[-1] for c in math)
            for math in root.iter(M) if len(math)]


def spatext_checks(bank, seeds=None):
    """Both SpaTeXt-side checks, from one rendering of each version.

    Rendering is the cost -- Mustache, then an XML parse -- and the two
    checks each rendered every version separately: about 25 of
    `checkit check`'s seconds on mat-106 for the same 29,000 trees twice.
    Every version, print-only ones included, since print is where
    something dropped is least likely to be noticed.
    """
    out = []
    nested, dropped = collections.Counter(), collections.Counter()
    for outcome in bank.outcomes():
        for exercise in outcome.exercises()[:seeds]:
            try:
                root = exercise.spatext_ele()
            except Exception as exc:                      # pragma: no cover
                out.append(Finding("spatext-error", outcome.slug, str(exc), 1))
                break
            for names in _nested_in_math(root):
                nested[(outcome.slug, names)] += 1
            for what in _dropped(root):
                dropped[(outcome.slug, what)] += 1
    for (slug, names), count in sorted(nested.items()):
        out.append(Finding("nested-in-m", slug,
                           "<m> contains <%s>; its content is dropped" % names, count))
    for (slug, what), count in sorted(dropped.items()):
        out.append(Finding("dropped", slug, what + "; not drawn", count))
    return out


def nested_elements_in_math(bank, seeds=None):
    """<m> elements containing other elements.

    html.xsl and latex.xsl both render <m> with normalize-space(text()), which
    concatenates only the DIRECT text children. Any element inside -- a nested
    <m> from spatext_math, a <glyphs> -- is silently discarded, and the prose
    between them survives, typeset as mathematics.

    This reads the SpaTeXt rather than the output, because by the time it is
    HTML the evidence has been deleted. It is the check that would have caught
    an outcome rendering "is a multiple of" with both numbers gone.
    """
    return [f for f in spatext_checks(bank, seeds) if f.check != "dropped"]


# What each element may hold, as html.xsl, latex.xsl and pretext.xsl select
# it -- the three agree on all of this. Every stylesheet begins by matching
# `*` and writing nothing ("kill undefined elements"), so an element anywhere
# else is silently dropped: no error, no warning, nothing on the page.
#
# Keep this in step with the stylesheets. A tag added to a stylesheet and not
# here is reported as dropped, which is the safe way round: loud, and fixed by
# adding it here.
_INLINE = {"m", "me", "q", "c", "em", "url", "image", "tikz-image",
           "glyphs", "nobreak"}
_HOLDS = {
    "knowl": {"title", "intro", "content", "outtro", "knowl"},
    "title": {"m", "q", "c"},
    "intro": {"p", "list"},
    "content": {"p", "list"},   # and <knowl>, outside any knowl; see below
    "outtro": {"p", "list"},
    "list": {"item"},
    "item": {"p", "list"},
    "p": _INLINE, "em": _INLINE, "q": _INLINE, "nobreak": _INLINE,
    "url": _INLINE,
    # Leaves. Their own text is read; anything inside is not. <m> and <me>
    # are left to nested_elements_in_math, which says more about them.
    "c": set(), "glyphs": set(), "image": set(), "tikz-image": set(),
}
# Where text written straight into the element, outside a <p>, is dropped.
_BLOCK = {"knowl", "intro", "content", "outtro", "list", "item"}


def _local(el):
    return el.tag.split("}")[-1] if isinstance(el.tag, str) else None


def _dropped(root):
    """Every piece of `root` no stylesheet will draw, as short descriptions."""
    found = []

    def walk(el, inside_knowl):
        name = _local(el)
        if name in ("m", "me"):
            return
        if name in _BLOCK:
            stray = [el.text] + [c.tail for c in el]
            if any(t and t.strip() for t in stray):
                found.append(f"text directly in <{name}>, outside a <p>")
        if name == "knowl":
            kids = [c for c in el if _local(c)]
            names = [_local(c) for c in kids]
            for one in ("title", "intro", "content"):
                if names.count(one) > 1:
                    found.append(f"a second <{one}> in a <knowl>")
            if "knowl" in names and "content" in names:
                found.append("a <knowl> with both <content> and parts; "
                             "the <content> is dropped")
            shown = [c for c in kids if _local(c) == "outtro"
                     and c.get("distractor") != "true"]
            if len(shown) > 1:
                found.append("a second <outtro>: drawn on the web, dropped in "
                             "print and PreTeXt")
        if name == "url" and el.get("href") is None:
            found.append("<url> without href")
        allowed = set(_HOLDS.get(name, set()))
        if name == "content" and not inside_knowl:
            allowed.add("knowl")
        for child in el:
            kid = _local(child)
            if kid is None:
                continue                      # a comment
            if kid not in allowed:
                found.append(f"<{kid}> inside <{name}>")
                continue
            walk(child, inside_knowl or name == "knowl")

    walk(root, False)
    return found


def dropped_by_stylesheets(bank, seeds=None):
    """SpaTeXt the stylesheets will silently not draw.

    Four renderers turn an exercise into something to look at: the student
    page (Svelte, walking the SpaTeXt itself) and html.xsl, latex.xsl and
    pretext.xsl. They disagree in places -- a knowl with both content and
    parts, several outtros, an element in a title -- and because every
    stylesheet turns an element it does not expect into nothing, a
    disagreement is invisible: the web page looks right and print has lost
    a paragraph (review, 2026-11-16). This reports every such element, so
    that a disagreement is at least loud. Making the renderers agree is
    on the roadmap; this is what says whether it matters to a bank.

    Read from the SpaTeXt, not the output: by the time it is HTML or LaTeX
    the evidence is gone. Every version; see `spatext_checks`, which
    `run_all` calls so that each version is rendered once for both.
    """
    return [f for f in spatext_checks(bank, seeds) if f.check != "nested-in-m"]


_MUSTACHE = re.compile(r"\{\{\{?\s*([#^/&]?)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\}\}")

# Retired blocks are left commented out rather than deleted, and their fields
# are naturally absent from the data. Mustache does substitute inside an XML
# comment -- which is how F2-E smuggles {{#section}} tags past the XML parser
# -- but the comment is then discarded by the stylesheets, so nothing there
# can render either way.
_XML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _references_with_sections(template):
    """Every {{name}} in the template, paired with the sections enclosing it.

    A name inside {{#outer}}...{{/outer}} does not have to be a top-level key:
    Mustache looks it up in the section's own value first. So the enclosing
    section names have to travel with the reference, or every nested field looks
    absent.

    Section tags are read from the template *including* its XML comments, which
    is where banks put them -- `<!-- {{#lines}} -->` is how a section survives
    an XML parser that would otherwise choke on it. Plain references inside a
    comment are still skipped, since the stylesheets discard the comment and
    nothing there can render.
    """
    commented = [(m.start(), m.end()) for m in _XML_COMMENT.finditer(template)]

    def inside_comment(pos):
        return any(start <= pos < end for start, end in commented)

    references, stack = [], []
    for match in _MUSTACHE.finditer(template):
        sigil, name = match.group(1), match.group(2)
        if sigil in ("#", "^"):
            stack.append(name)
        elif sigil == "/":
            if stack and stack[-1] == name:
                stack.pop()
            elif name in stack:                            # pragma: no cover
                # Crossed tags. Unwind to the one that closed rather than
                # leaving the stack wrong for everything after.
                while stack and stack.pop() != name:
                    pass
        elif name != "__seed__" and not inside_comment(match.start()):
            references.append((name, tuple(stack)))
    return references


def _visible_contexts(data, sections):
    """Every dict a name could resolve against inside `sections`, for lookup.

    Deliberately generous: a list section offers each of its items, and outer
    contexts stay in scope. This check exists to catch a name that is nowhere at
    all, so anything short of certain absence should not be reported.
    """
    contexts = [data]
    for section in sections:
        value = None
        for frame in reversed(contexts):
            if isinstance(frame, dict) and section in frame:
                value = frame[section]
                break
        if isinstance(value, dict):
            contexts.append(value)
        elif isinstance(value, list):
            contexts.extend(item for item in value if isinstance(item, dict))
    return contexts


def template_fields_without_data(bank, seeds=None):
    """Template fields the generator never supplies.

    Mustache renders an absent key as the empty string, so the sentence around
    it survives and the value vanishes: "explaining the  to an elementary
    school student?". Nothing fails, and the exercise is unanswerable.

    Section tags ({{#x}}, {{^x}}, {{/x}}) are not themselves reported -- an
    absent key there means "false", which is the whole point of them -- nor is
    `__seed__`, which the renderer injects.
    """
    out = []
    hits = collections.Counter()
    for outcome in bank.outcomes():
        try:
            template = outcome.template()
        except Exception:                                  # pragma: no cover
            continue
        referenced = _references_with_sections(template)
        if not referenced:
            continue
        for exercise in outcome.exercises()[:seeds]:
            for name, sections in referenced:
                contexts = _visible_contexts(exercise.data, sections)
                if not any(isinstance(c, dict) and name in c for c in contexts):
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

#: Every check that reads rendered output. bank.json and the bundles are
#: both run through exactly these, so a check added here covers both.
OUTPUT_CHECKS = (
    escaped_markup,
    raw_tex_in_prose,
    control_characters,
    relative_image_src,
    punctuation_in_inline_math,
    latex_structure,
)


def _bundles_as_bank_json(bank_path):
    """Every derived.json, shaped like bank.json, so OUTPUT_CHECKS can read it."""
    outcomes = []
    pattern = os.path.join(bank_path, "assets", "*", "generated", "derived.json")
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        outcomes.append({
            "slug": data.get("slug"),
            "exercises": [formats for _, formats in
                          sorted(data.get("seeds", {}).items(), key=lambda kv: int(kv[0]))],
        })
    return {"outcomes": outcomes}


def bundles(bank_path):
    """The same checks over derived.json.

    bank.json inlines only the public seeds, so a clean bank.json says nothing
    about the versions an assessment draws from. One bug lived 334 times in
    here and 48 times in bank.json.

    "The same checks" used to be three of the seven, re-implemented by hand:
    escaped markup, relative images, punctuation in maths and the
    inline-maths checks never looked at these versions (review, 2026-11-16).
    Now it is OUTPUT_CHECKS itself, each finding marked as coming from here.
    """
    doc = _bundles_as_bank_json(bank_path)
    return [f._replace(detail=f"{f.detail}, in versions {PUBLIC_SEEDS}-{BUNDLE_UNTIL - 1}")
            for check in OUTPUT_CHECKS for f in check(doc)]


# ---------------------------------------------------------------------------

def run_all(bank):
    """Every check, against a built bank. Returns a flat list of Finding."""
    path = os.path.join(bank.build_path(), "bank.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    findings = []
    for check in OUTPUT_CHECKS:
        findings += check(doc)
    findings += spatext_checks(bank)
    findings += template_fields_without_data(bank)
    findings += bundles(bank.abspath())
    return findings
