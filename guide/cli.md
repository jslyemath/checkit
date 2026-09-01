# CLI reference

Every command and option. Run any of them with `--help` for the same text
inline.

```
checkit new       scaffold a new bank
checkit generate  run the generators and render every version
checkit viewer    build the publishable site from what generate produced
checkit check     structural checks on a built bank and its generators
checkit tui       a terminal UI over the above
```

`python -m checkit ...` works identically and is what to use if the `checkit`
script is not on your PATH.

---

## `checkit new [DIRECTORY]`

Scaffolds a bank. Default directory is `new-checkit-bank`.

Creates:

| | |
|---|---|
| `bank.xml` | the manifest — see [Bank format](bank-format.md) |
| `outcomes/EX1/generator.py` | a worked example generator |
| `outcomes/EX1/template.xml` | its template |
| `bank_helpers.py` | shared Python, importable from any generator |
| `bank_helpers.sty` | shared LaTeX macros for print and figures |
| `requirements.txt` | pinned at the wheel URL of the version that made it |
| `README.md`, `.gitignore`, `.devcontainer/` | |

The generated `requirements.txt` deliberately does **not** say
`checkit-dashboard == <version>`: that resolves on PyPI to the upstream project,
which is different code sharing a version number.

---

## `checkit generate`

Runs each outcome's generator across the seed range and renders every version.
Writes `assets/<slug>/generated/seeds.json` and `assets/bank.json`.

### `-a`, `--amount N` (default 1000)

How many versions to generate per outcome. Refused below `PUBLIC_SEEDS` (50),
because the viewer's version picker always offers 50 and a smaller bank leaves
it pointing at seeds that do not exist — which fails silently in the browser.

See [Constants](#constants) for what the number means.

### `-r`, `--regenerate`

Force regeneration of seeds that already exist. Without it, an outcome with a
`seeds.json` is loaded rather than re-run.

**Generation is reproducible**: the same seed yields the same data. So `-r` on
an *unchanged* generator rewrites byte-identical output and changes nothing.
What `-r` actually does is pick up **generator edits** — which is exactly why
`<frozen/>` exists. See [Checking a build](checking.md#freezing-an-outcome).

### `-i`, `--images`

Rasterise figures to PNG. Without it, `.tikz` source is still written for every
seed, so LaTeX and print output are unaffected — only the browser's PNGs are
skipped.

### `--image-seeds N`

Rasterise PNGs for only the first N seeds. `.tikz` is still written for all of
them.

A cap below 50 leaves broken images for students, since the viewer shows 50
versions. Use it for quick previews, not for a real build.

### `-o`, `--outcome SLUG` (default `ALL`)

Regenerate only that outcome. Everything else is loaded from disk and
re-rendered, so `bank.json` still contains the whole bank.

Refused if no outcome has that slug — regenerating nothing looks exactly like
success otherwise.

### `--remote URL`

Absolute URL of the directory containing `assets/`, e.g.
`https://example.org/my-bank`.

**Required when the bank has figures.** Precomputed HTML has to carry absolute
`<img src>` values, because that HTML is read outside the site — in LMS exports
and the AI payload — where a root-relative path 404s. `generate` refuses up
front rather than several minutes into a build.

### `--thaw SLUG`

Regenerate an outcome marked `<frozen/>` in `bank.xml`. Repeatable.

Refused if the slug is unknown, or if it is not actually frozen — believing an
outcome is protected when it is not is the failure this prevents. There is no
blanket `--force`, deliberately.

### `--no-precompute`

Skip rendering HTML/LaTeX/PreTeXt at build time. Faster, but the viewer needs
those once browsers drop XSLT (Chrome 158, November 2026). Also removes any
stale bundle, so `bank.json` and the files beside it cannot disagree.

---

## `checkit viewer`

Builds `docs/` from what `generate` produced: extracts the compiled viewer and
copies `assets/` beside it.

**This is the second half of publishing, and forgetting it is silent.**
`generate` writes `assets/`; only `viewer` copies it into `docs/`. A bank whose
site looks stale has usually had one without the other.

`docs/` is deleted and rebuilt each time. Anything you put there by hand is
lost — see [Publishing](getting-started.md#publishing).

`seeds.json` and `.tikz` are deliberately not copied: the viewer never fetches
them, and publishing them doubled the repo size.

---

## `checkit check`

Structural checks. Exits non-zero if anything is found, so it works in CI.

```
checkit check                  # generators, then the built bank
checkit check --no-built       # generators only; needs no build
checkit check --no-generators  # the built bank only
```

Both halves are on by default. `--generators` and `--built` exist as the
explicit positive forms, so a CI script can say what it means rather than
relying on the default.

Full description of what each check catches, and what it deliberately does not,
in [Checking a build](checking.md).

---

## `checkit tui`

Opens a Textual terminal UI over the commands above. Provided by `trogon`;
useful for discovering options without reading this page.

---

## Constants

Three numbers decide what exists and what is published. Two are currently
constants in `checkit/__init__.py` rather than options.

| | value | meaning |
|---|---|---|
| `PUBLIC_SEEDS` | 50 | how many versions a student can browse |
| `BUNDLE_UNTIL` | 400 | where publishing stops |
| `--amount` | 1000 | how many versions exist at all |

That gives three tiers:

| seeds | where they live | published? |
|---|---|---|
| 0 – 49 | inlined in `bank.json`, all three formats | **yes** |
| 50 – 399 | `derived.json`, HTML + LaTeX | **yes** |
| 400 – 999 | `seeds.json` only, data with no rendered formats | **no** |

`checkit viewer` copies `assets/` into `docs/` while ignoring `seeds.json`, so
the top tier exists in your bank and nowhere else. That is the pool a print
tool draws from: reproducible, and not published.

Raising `--amount` grows the unpublished tier. Changing `PUBLIC_SEEDS` or
`BUNDLE_UNTIL` currently means editing the platform — they are duplicated in the
viewer's TypeScript, and a test enforces that the two agree.
