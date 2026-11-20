# CheckIt, and the tools built around it

@WORKING_RULES.md

The line above loads the house rules, which apply in all three repos and
begin with a duty: **check that student names are masked before doing
anything else.**

This file is the map of the whole project and of the platform. printit has
its own map (`../checkit-printit/CLAUDE.md`); the bank has a short one.

## Three repos, three jobs

| repo | what it is | its map |
|---|---|---|
| `Projects/checkit` | **the platform**, a fork of StevenClontz/checkit. `dashboard/` is the Python package (`checkit generate`, `viewer`, `check`); `viewer/` is the Svelte site students and instructors browse; `docs/demo/` is the demo site | this file |
| `Projects/checkit-printit` | **the print tool and the course around it**: print runs, rosters, seating, the Google Form, scanning marked papers back in, Progress, the gradebook round-trip, the vault -- and the local web app (`gui -c <course>`), which is part of printit, not of the platform | `../checkit-printit/CLAUDE.md` |
| `Projects/mat-106-checkit` | **the live bank**: 29 skills plus the Fundamentals Checkpoint (30 outcomes in `bank.xml`), publishes to `docs/` | its own `CLAUDE.md` |
| `Projects/mat-206-checkit` | **frozen. Do not modify or push.** To be rebuilt from scratch later | -- |
| `Projects/FundCheck` | not a repo. The pre-port FCP script and ~120 `.tex` files **with real student names** | -- |

**The boundary:** the platform knows nothing about printit. `grep -rn
printit dashboard/checkit/` returns nothing and should stay that way.
printit owns `printit.sty` and `printitfigures.sty`, installs them into a
bank's `printit/` folder, and declares them in `bank.xml` under
`<latex-support>`; the platform publishes whatever a bank declares.

This repo also holds the documents that span all three: `WORKING_RULES.md`,
`ROADMAP.md` and `CODEBASE_NOTES.md`.

## Which Python

There is no single environment.

```bash
# checkit's tests, and anything importing checkit (printit's venv has both, editable)
"C:/Users/slye/Projects/checkit-printit/.venv/Scripts/python.exe" -m pytest dashboard/tests -q

# mat-106 bank operations (checkit editable, pointing here)
cd "C:/Users/slye/Projects/mat-106-checkit" && ./venv/Scripts/python.exe -m checkit generate ...
```

An edit to `dashboard/` takes effect in both with no reinstall. printit
installs against a **released wheel** of the platform (0.2.9.1), so a
helper printit needs from here has to be in a release first -- which is
why `atomic_write` exists in both repos on purpose.

## The CLI

`checkit`: `new`, `generate`, `viewer`, `check`, `tui`.

`generate`:
- **`-r` / `--regenerate`** -- without it, existing seeds are reused, so a
  generator fix reaches nothing. It re-rolls every version: never mid-term
  on a live skill, and **republish the same day**.
- `-o` / `--outcome`, repeatable; `--thaw SLUG` for an outcome marked
  `<frozen/>`. Both ignore case.
- `-i` / `--images` with `--image-seeds N` rasterizes `.tikz` to PNG.
  Images go to 400 **only because `--image-seeds 400` is passed by hand**;
  nothing past 400 uses a PNG (print `\input`s the `.tikz`).
- `--remote URL` is required when the bank has images; any version's
  template or data naming `<image>`/`<tikz-image>` counts.

`check` runs every generator, then structural checks over **every
version**: `bank.json` and each bundle get the same `OUTPUT_CHECKS`, and
the SpaTeXt is read once per version for maths that drops content
(`nested-in-m`) and anything no stylesheet draws (`dropped`). About 45s on
mat-106.

## Seed tiers

- `0 .. 49` (`PUBLIC_SEEDS`) -- students; inlined in `bank.json`.
- `50 .. 399` (`BUNDLE_UNTIL`) -- instructors; per-outcome `derived.json`,
  and the `.tikz` of each figure, which the viewer's assessment builder
  pastes into its LaTeX.
- `400+` -- print only. Data in `seeds.json`, which is **not** published.
  `bank.json` drops their `data` too (0.2.9.1); it used to serve 17,400
  print-only exercises with their answers.

## How an exercise becomes something to look at

- **SpaTeXt** is the source. Four renderers turn it into output: the
  student page (Svelte, walking the SpaTeXt itself) and `html.xsl`,
  `latex.xsl`, `pretext.xsl` (instructor tabs, LMS export, print). They do
  not fully agree -- ROADMAP item 6 -- and every stylesheet turns an
  element it does not expect into nothing, which `checkit check` reports.
- **`latex.xsl` escapes prose**: text outside `<m>`, `<me>` and `@latex`
  prints as written. Raw LaTeX belongs inside `<m>`.
- **Stylesheets compile once per thread** (`exercise.stylesheet`) **and a
  template is parsed once per edit** (`Outcome.parsed_template`); anything
  standing in for an Outcome needs that method. mat-106's precompute: 40s
  to 6.
- **One picture, two surfaces.** A generator's `tikz_graphics()` returns
  TikZ; a `.tikz` is written per seed, rasterized for the web, and
  `\input` by print. `<tikz-image source="X">` is `<img src="X.png">` in
  HTML and `\input{X.tikz}` in LaTeX. Both are styled by
  `printitfigures.sty`, so web and print figures match. **A PNG is current
  when its hash matches** (`figure-keys.json`), so editing the preamble or
  the `.sty` redoes every figure.

## Three templating systems, deliberately

- **XSLT** -- the stylesheets above.
- **Mustache** `{{x}}` / `{{{x}}}` / `{{#s}}` -- a bank's `template.xml`,
  the viewer's assessment template, LMS exports.
- **Jinja** `\VAR{}` `\BLOCK{}` `\#{}` -- a skill's `textemplate.tex`,
  print only (delimiters from the `latex` package).

A template that documents its own syntax has that documentation parsed as
syntax; both Mustache and Jinja templates broke that way. Name fields in
prose.

## Platform footguns

- **Every file is UTF-8 and written whole** (`checkit.utils.atomic_write`).
  Never `open()` without `encoding=`, never `open(path, "w")` for state.
- **`<frozen/>` is enforced on the Outcome**, so every path respects it.
- **`-a` must be more than 50**: the viewer offers 50 versions and
  assessments draw from the ones after.
- **A stub Outcome in a test needs `parsed_template()`** -- nineteen tests
  failed for want of it.
- `dashboard.py` (the deprecated Jupyter UI) and the Python MathML path
  are upstream's and kept on purpose.
- The viewer's `PUBLIC_SEEDS` is a second copy of the Python one;
  `test_subset.py` asserts they match.

## Still to do

`ROADMAP.md`. Nothing open is listed here.
