# Bank format

A bank is a folder. This is everything the platform looks for in one, and every
place you can override its behaviour.

```
my-bank/
├── bank.xml               the manifest: what outcomes exist
├── bank_helpers.py        shared Python, importable from any generator
├── bank_helpers.sty       shared LaTeX macros for figures and print
├── tikz_preamble.tex      optional: replaces the figure-compilation preamble
├── requirements.txt
├── outcomes/
│   └── W1/
│       ├── generator.py   or generator.sage
│       └── template.xml
├── assets/                generated; commit or not, as you prefer
│   ├── bank.json
│   └── W1/generated/
│       ├── seeds.json     every version's data
│       ├── derived.json   seeds 50-399, pre-rendered
│       └── 0000/*.tikz    figures, and *.png if -i was used
└── docs/                  the publishable site; rebuilt by `checkit viewer`
```

---

## `bank.xml`

```xml
<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>MAT 100 — Example Bank</title>
    <slug>mat-100-bank</slug>
    <url>https://example.github.io/mat-100</url>

    <ai-prompt>
        The following is a practice exercise with its answer. Help me
        understand how to reach it without simply restating it.
    </ai-prompt>

    <outcomes>
        <outcome>
            <title>Converting between numeration systems</title>
            <slug>W1</slug>
            <path>outcomes/W1</path>
            <description>
                I can convert between ancient and modern numeration systems.
            </description>
            <ai-prompt>...</ai-prompt>
            <frozen/>
        </outcome>
    </outcomes>
</bank>
```

### Bank-level

| element | required | meaning |
|---|---|---|
| `<title>` | yes | shown as the site heading |
| `<slug>` | yes | short identifier |
| `<url>` | yes | where the bank is published; used as the default `--remote` in some tooling |
| `<ai-prompt>` | no | default prompt for "Copy for AI Chatbot"; an outcome may override |

`version="0.2"` on the root element is checked and must be present.

### Per outcome

| element | required | meaning |
|---|---|---|
| `<title>` | yes | the outcome's name |
| `<slug>` | yes | short identifier; the URL fragment, and the folder name under `assets/` |
| `<path>` | yes | folder holding `generator.py` and `template.xml`, relative to the bank root |
| `<description>` | yes | the learning outcome, shown under the title |
| `<ai-prompt>` | no | overrides the bank-level prompt for this outcome |
| `<frozen/>` | no | refuse to regenerate this outcome's seeds — see [Checking a build](checking.md#freezing-an-outcome) |

Optional elements are genuinely optional: a `bank.xml` written before one
existed still loads.

> **Anything else in your `bank.xml` is yours, not the platform's.** Some banks
> carry extra elements — colour maps, `<associate>` entries — read by their own
> tooling. CheckIt ignores them, and will keep ignoring them; do not expect the
> viewer or the exports to honour them.

---

## `outcomes/<slug>/generator.py`

Produces the data for one version. Covered in [Writing
generators](generators.md).

**The file extension picks the runtime**:

| filename | runs under |
|---|---|
| `generator.py` | the Python `checkit` is installed into |
| `generator.sage` | `sage` on your PATH |

Nothing else is needed to switch — no flag, no config. If both exist, `.py`
wins.

## `outcomes/<slug>/template.xml`

What the exercise *says*, in SpaTeXt, with the generator's data substituted.
See the [SpaTeXt reference](spatext.md).

---

## `bank_helpers.py`

Shared Python for your generators. Scaffolded by `checkit new`, nearly empty.

```python
# bank_helpers.py
def money(x):
    return f"\\${x:,.2f}"
```

```python
# outcomes/W1/generator.py
import bank_helpers as bh

class Generator(BaseGenerator):
    def data(self):
        return {"price": bh.money(19.5)}
```

The bank root is added to the import path when a generator runs, so a plain
`import bank_helpers` works from any outcome however deeply nested. That path
is added *after* the standard library, so do not name it after a module you
also want to import.

---

## `bank_helpers.sty`

The LaTeX counterpart. Scaffolded by `checkit new`, nearly empty.

**What belongs here**: commands and packages your *content* cannot compile
without. If a generator emits `\myNumeral{7}`, or an outcome sets Egyptian
numerals with `\usepackage{hieroglf}`, the definition goes here.

**What does not**: anything about how a page looks. `\geometry{margin=1in}`
compiles fine without and merely changes the result, which makes it styling and
the business of whatever produces the page.

That line is not tidiness. This file is loaded by two very different documents —
a borderless standalone building one figure, and (eventually) a printed
document — so page-level settings here either do nothing or break the figure
build.

Loaded automatically during figure compilation when present. Nothing loads it
for the web: the browser renders maths with KaTeX and never sees LaTeX macros.
Content that must *look* different per medium wants a SpaTeXt element instead —
see [`<glyphs>` and `<nobreak>`](spatext.md#per-medium-elements).

---

## `tikz_preamble.tex`

Replaces the preamble used to compile `.tikz` figures into PNGs. The default is:

```latex
\documentclass[tikz,border=4pt]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
```

Drop a `tikz_preamble.tex` in the bank root and it replaces that **wholesale** —
it carries its own `\documentclass`, so it is a complete preamble rather than an
addition. A bank that writes one takes full control, which includes loading
`bank_helpers` itself if figures use bank macros:

```latex
\documentclass[tikz,border=4pt]{standalone}
\usepackage{tkz-euclide}
\usepackage{bank_helpers}
```

Without a custom file, `bank_helpers.sty` is loaded automatically when it
exists.

---

## `assets/`

Written by `checkit generate`.

| | |
|---|---|
| `bank.json` | the manifest the viewer fetches; seeds 0–49 inlined with all three formats |
| `<slug>/generated/seeds.json` | every version's *data*, all 1000 seeds |
| `<slug>/generated/derived.json` | seeds 50–399 pre-rendered to HTML and LaTeX |
| `<slug>/generated/0000/*.tikz` | figure source, every seed |
| `<slug>/generated/0000/*.png` | rasterised figures, if `-i` was used |

`seeds.json` is the source of truth; the other two are derived from it.

## `docs/`

The publishable site, built by `checkit viewer`. **Deleted and rebuilt** each
time, so nothing hand-edited survives there.

It is a committed build artifact — nothing regenerates it when you push, so a
site is only as fresh as the last `checkit viewer` you committed. The viewer
shows its build date on the front page; if that date looks old, it *is* old.
