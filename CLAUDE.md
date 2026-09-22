# Working in this project

Loaded automatically every session. Keep it short enough that it stays true.

This is the **map**, not the record. The long-form history is
`CODEBASE_NOTES.md` (5,600+ lines, not auto-loaded — find a section with
`grep -n "^## " CODEBASE_NOTES.md`), and it has to be kept up: see "Three
documents" below.

## The repos

| path | what it is |
|---|---|
| `Projects/checkit` | the platform, a fork of StevenClontz/checkit. `dashboard/` is the Python package, `viewer/` the Svelte app, `docs/demo/` the demo site |
| `Projects/mat-106-checkit` | the live bank. 29 outcomes, publishes to `docs/` |
| `Projects/checkit-printit` | the print tool. Separate repo, separate install |
| `Projects/mat-206-checkit` | **frozen. Do not modify or push.** Being rebuilt from scratch later |
| `Projects/FundCheck` | not a git repo. The pre-port FCP script and ~120 `.tex` files **with real student names** |

## Which Python

There is no single environment. Use the right one:

```bash
# checkit's tests, and anything importing checkit
"C:/Users/slye/Projects/checkit-printit/.venv/Scripts/python.exe" -m pytest dashboard/tests -q

# mat-106 bank operations
cd "C:/Users/slye/Projects/mat-106-checkit" && ./venv/Scripts/python.exe -m checkit generate ...

# printit
"C:/Users/slye/Projects/checkit-printit/.venv/Scripts/python.exe" -m checkit_printit ...
```

mat-106's venv has checkit installed **editable**, pointing at `Projects/checkit/dashboard`. Edits to the platform take effect there with no reinstall.

## The CLI surface

`checkit`: `new`, `generate`, `viewer`, `check`, `tui`.

`generate` flags that matter:
- **`-r` / `--regenerate`** — without it, existing seeds are reused. A generator fix reaches nothing until you pass this. It re-rolls every version, so never mid-term on a live skill.
- `-o` / `--outcome` — repeatable
- `-i` / `--images` + `--image-seeds N` — rasterize `.tikz` to PNG
- `--remote URL` — required when the bank has images
- `--thaw SLUG` — regenerate an outcome marked `<frozen/>`

`checkit-printit` has grown a lot: `build`, `init`, `install`, plus
`course`, `roster`, `skills`, `record` and `form` groups. Its own
`CLAUDE.md` lists them all — read that before touching it.

## Seed tiers

- `0 .. 49` (`PUBLIC_SEEDS`) — students; inlined in `bank.json`
- `50 .. 399` (`BUNDLE_UNTIL`) — instructors; per-outcome `derived.json`
- `400+` — print only. Data lives in `seeds.json`, which is **not** published;
  as of 0.2.9.1 `bank.json` drops the `data` for these too. It used to carry
  it, so 17,400 print-only exercises were served publicly with their answers,
  and the viewer would render one from a hand-typed URL. Both are fixed; the
  fix only reaches a bank on its next `generate` and deploy.

Images are rasterized to 400, because nothing past that can consume one: the viewer shows 50, bundles stop at 400, LMS export runs 100–399, and **print uses no PNGs at all** — it `\input`s the `.tikz`, written for all 1000 seeds.

## One picture, two surfaces

A generator's `tikz_graphics()` returns TikZ source. CheckIt writes a `.tikz` per seed, rasterizes it to PNG for the web, and print `\input`s the same file. SpaTeXt's `<tikz-image source="X">` becomes `<img src="X.png">` in HTML and `\input{X.tikz}` in LaTeX.

Both surfaces style it with `printitfigures.sty`, loaded by the bank's `tikz_preamble.tex` and by `printit.sty`. That is what keeps a web figure and a printed one identical.

## Who owns the theme

checkit-printit owns `printit.sty` and `printitfigures.sty`, installs them to `<bank>/printit/`, and writes a `<latex-support>` declaration into `bank.xml`. **CheckIt holds no constant naming printit** — it publishes what the bank declares. `grep -rn printit dashboard/checkit/` returns nothing, and should stay that way.

`printit.sty` cannot load in a standalone figure (it wants page geometry, `\acadclass`, `\title`). That is why the picture half is a separate package.

## Three templating systems, deliberately

- **XSLT** — `dashboard/checkit/static/{html,latex,pretext}.xsl` turn SpaTeXt into each format
- **Mustache** `{{x}}` / `{{{x}}}` / `{{#section}}` — bank `template.xml`, the viewer's assessment template, LMS exports
- **Jinja** `\VAR{}` `\BLOCK{}` `\#{}` — per-outcome `textemplate.tex`, print only. Those delimiters come from the `latex` PyPI package, not from us.

A template that documents its own syntax will have that documentation parsed as syntax. Both the Mustache and Jinja templates broke this way. Name fields in prose.

## Standing constraints

- **mat-206: do not modify, do not push.**
- Real student names live in `mat-106-checkit/TeX Outputs/` (gitignored), `../FundCheck`, and every print run under `~/CheckItPrintIt`. Never commit them, never paste them into chat unless asked.
- Print output goes to `~/CheckItPrintIt/<course>/<title>/`, and course state
  to `~/CheckItPrintIt/courses/<name>/` — both deliberately outside every
  repo, because they hold names, student ids and email addresses.
- Never paste a student name into chat. Mask output that might contain one.

## Three documents, and which one you are supposed to write to

| | job | read it |
|---|---|---|
| `CLAUDE.md` (one per repo) | the **map**: what exists, which Python, the footguns | automatically, every session |
| `PRINT_TOOL_DESIGN.md` | the **plan** for printit: decisions, rationale, what is next | on request |
| `CODEBASE_NOTES.md` | the **history**: what changed and why, dated | `grep -n "^## " CODEBASE_NOTES.md` |

**A change with reasoning behind it gets a dated `##` section in
`CODEBASE_NOTES.md`. The commit message is not the record.** Put the reasoning
that would not survive being summarised: what was actually wrong, how it was
found, what was ruled out, and what was verified rather than assumed.

This rule already existed, in the first paragraph of `CODEBASE_NOTES.md`, and
was followed for weeks and then silently dropped the day `CLAUDE.md` was
added -- twenty-six commits, including a live data exposure whose only record
was a commit message. `CLAUDE.md` did not replace it; they do different jobs.
See "The fortnight the notes were not kept".

## Checks that have failed silently here

Each of these shipped something wrong while reporting success. They are not
hypothetical and several have recurred after being written down.

**Write patch scripts with the Write tool, never a heredoc.** A heredoc
mangles backslashes, so `\n` in a Python string becomes a real newline and the
find-and-replace matches nothing. This has cost time five times in a single
session. `sed` is worse: `\u` is an escape, which breaks every `\usepackage`.
Put `assert old in text` in the script so a missed match writes nothing.

**`command | tail` reports tail's exit code.** Redirect to a file, check `$?`
alone, then read the file. Done again this week despite being listed here.

**A test that passes proves nothing until you have watched it fail.** Break
the code deliberately and confirm the test notices. Doing that found four
vacuous tests in one session — and three of them were the test for the thing
most recently fixed, written while thinking about the fix rather than about
what could still be wrong.

**Run it on real data.** Three bugs this week lived in code whose tests all
passed and appeared only against the instructor's actual files.

**Verify the artifact, not the dry run.** `build --preview` and `build` draw
independently without a shared `--seed`, so checking the preview proved
nothing about what shipped.

**Do not declare something impossible without checking.** "A CLI cannot sign
in to Google" was asserted twice, wrong both times, and sent a design down a
worse path.

**A merge is not done when tests pass.** Diff the commit against what you
meant to merge — the 0.2.9 merge kept ancestry and lost nine files' content,
and every check looked at the working tree, where it was genuinely present.

**A PDF existing is not a clean compile.** pdflatex recovers from errors and
writes one anyway. Fixed in `wrapper/tikz.py`; the habit generalises.

**Counting seeds is not counting figures.** "400 seeds imaged" was true while
nine figures were missing.

**A fix applied to one path is not applied to the others.** Three times in
one day: a rename that caught `"-w"` but not ` -w ` or `` `-w` ``, a
`form attach` carrying its own copy of a helper that had just been fixed, and
a hand-deployment path that missed every improvement the automated one got.
When a change to shared behaviour does not show up, ask "is there a second
copy", not "did it deploy".

**Writing to `CLAUDE.md` is not writing to `CODEBASE_NOTES.md`.** Twenty-six
commits went unrecorded because the notes felt superseded by the map. They are
not; see the table above.

**`gh` defaults to a fork's parent.** Both clones now have
`gh repo set-default` pointing at `jslyemath/...`, but before that a release
command aimed itself at `StevenClontz/checkit`. Check `--repo` on anything
that writes.
