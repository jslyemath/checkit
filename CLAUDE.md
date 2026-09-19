# Working in this project

Loaded automatically every session. Keep it short enough that it stays true;
the long-form history is in `CODEBASE_NOTES.md` (5,000+ lines, not auto-loaded
— find a section with `grep -n "^## " CODEBASE_NOTES.md`).

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

`checkit-printit`: `init`, `install`, `build`, `import`. `build --preview` writes nothing and reports what would print — read its "versions N distinct" line.

## Seed tiers

- `0 .. 49` (`PUBLIC_SEEDS`) — students; inlined in `bank.json`
- `50 .. 399` (`BUNDLE_UNTIL`) — instructors; per-outcome `derived.json`
- `400+` — print only; data in `seeds.json`, nothing precomputed or published

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
- Print output goes to `~/CheckItPrintIt/<course>/<title>/`, deliberately outside every repo.

## Checks that have failed silently here

Each of these shipped something wrong while reporting success:

- **A merge is not done when tests pass.** Diff the commit against what you meant to merge — the 0.2.9 merge kept ancestry and lost nine files' content, and every check looked at the working tree, where it was genuinely present.
- **A PDF existing is not a clean compile.** pdflatex recovers from errors and writes one anyway. Fixed in `wrapper/tikz.py`, but the habit generalises.
- **`command | tail` reports tail's exit code.** Redirect a build to a file instead, or a failure reads as success.
- **Counting seeds is not counting figures.** "400 seeds imaged" was true while nine figures were missing.
- Bash heredocs eat backslashes, and `sed` treats `\u` as an escape. Write LaTeX-bearing scripts as files, with raw strings.
