# Tests

The first tests in this repo. They exist because of one specific hazard:
**the SpaTeXt transforms are implemented twice**, once in `lxml` for the
dashboard and once in the browser's `XSLTProcessor` for the viewer, and until
now nothing checked that the two agreed.

```bash
python -m unittest discover -s dashboard/tests -t dashboard/tests
```

## What is here

| file | what it does |
|---|---|
| `spatext_fixtures.py` | hand-written SpaTeXt covering the structural cases |
| `test_subset.py` | the automated suite (15 tests, ~0.2s) |
| `browser_harness.py` | generates a page that re-runs the checks in a real browser |

## Three choices worth knowing about

**Stdlib `unittest`, not pytest.** This repo has no test dependency and no
runner. Adding one should not be the price of adding the first test.

**Hermetic fixtures, not `demo-bank`.** A bank's `assets/**/generated` is
gitignored, so a fresh clone has no `seeds.json`; a bank-backed test would need
a full `checkit generate` before it could run. The fixtures need only `lxml`,
so the suite runs the moment the repo is cloned. They follow real template
shapes — see `demo-bank/outcomes/EX/EX1` for the nested-knowl case.

**The core test compares two implementations, not output against a golden
file.** `html.xsl` filters *during* the transform via its `subset` parameter;
`viewer/src/utils/index.ts` filters *after* it, removing elements by class.
The test performs both and asserts they match. That needs no stored snapshot
and stays meaningful as the stylesheets change.

## The invariants being protected

**Subset filtering**

- `subset` filtering agrees with the viewer's `solutions` filtering, for every
  fixture and every value
- omitting `subset` means `'all'` — the viewer never passes it, so the default
  is load-bearing and a change to it would alter browser output immediately
- the `<ol>` wrapper survives `subset='answer'`, so an instructor's answer key
  keeps its numbering
- `subset='statement'` and `subset='answer'` are not silently no-ops

**The MathML consumer**

- `consumer='basic'` keeps LaTeX delimiters; `'canvas'` and `'brightspace'`
  produce MathML and no delimiters
- a fraction becomes `<mfrac>`, not the same characters laid out flat
- display and inline maths are distinguished (`display="block"` / `"inline"`)
- every math span is converted, its LaTeX text removed, and its `data-latex`
  attribute kept so the source stays recoverable

**The remote base URL**

- an exercise with images refuses to render HTML without `remote=`
- `remote` is prepended to `@source`, tolerates trailing slashes, and applies
  under every subset and consumer
- `remote=''` still yields the old root-relative paths

**Both copies**

- the dashboard and viewer copies of all three stylesheets are byte-identical
- `PUBLIC_SEEDS` has the same value in `checkit/__init__.py` and in
  `viewer/src/utils/index.ts` — it has to exist twice because the browser
  cannot import from Python, and a drift would be quiet: the version picker
  would offer versions the preview never generated, or assessments would draw
  from seeds a student can open in the viewer
- `Exercise` refuses parameters it cannot honour rather than ignoring them

The suite is mutation-checked. Each of these was introduced and confirmed to
turn the suite red: changing the `subset` default, dropping the outtro guard,
guarding the whole `xsl:choose` (which would lose the `<ol>`), leaving the LaTeX
text beside the MathML, rendering display maths as inline, skipping the MathML
conversion, dropping the missing-`remote` check, and not stripping a trailing
slash from `remote`.

## The browser harness

```bash
python dashboard/tests/browser_harness.py subset_harness.html
```

Serve it over `http://` and read the last line. It runs a real `XSLTProcessor`
and a real DOM removal, then compares both against `lxml`'s output — catching
anything the Python transcription of the viewer's filter gets wrong.

Two limits. **Chromium alone is not enough**: the document-vs-element bug this
codebase already hit was invisible in Chromium and reproduced only in Firefox
(see the note above `outcomeToStxDocument`), so run it in both when it matters.
And **it expires**: Chrome removes XSLT in 158 on 2026-11-17. After that the
harness reports that the engine is gone and there is nothing left to compare
against. The `unittest` suite does not depend on it and keeps working.

There is also a third, frozen copy of each stylesheet inside
`checkit/static/viewer.zip`, inlined at Vite build time. It is a build artifact
rather than a hand-maintained file, which is why editing
`viewer/src/spatext/xsl/` changes nothing in a browser until `update_viewer.py`
runs. `test_dashboard_and_viewer_copies_are_identical` cannot see it.
