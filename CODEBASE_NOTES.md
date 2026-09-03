# CheckIt Codebase Notes

This document is as close to a complete, self-contained reference for the CheckIt codebase as possible. Every class, function, file, and design decision is explained here in enough detail that someone with no access to the source files can answer any question about how the system works. It started by looking at the original CheckIt by StevenClontz. Now, it also details changes made to this fork, maintained by jslyemath. Note that it is maintained alongside the code but may lag; when in doubt, the actual source code is authoritative. Please update this document appropriately whenever making changes to the codebase.

---

## 1. Project Overview

**CheckIt** is an open-source platform for authoring, generating, and distributing randomized mathematical exercises. Its primary audience is mathematics instructors who want to create exercise banks where each problem can be generated in hundreds or thousands of distinct-but-equivalent variants — same learning objective, different numbers.

### Who it's for

- **Instructors** who want to create large pools of graded exercises for formative assessment, homework, or exams.
- **Students** who use the generated viewer to practice with randomized versions of exercises.
- **LMS administrators** who import the exercises into Canvas, D2L Brightspace, or Moodle.

### The big-picture architecture

There are three major components:

1. **The Dashboard** (Python package `checkit-dashboard`, lives in `dashboard/`): A command-line tool and library. Given a *bank* directory authored by an instructor, it invokes SageMath to generate exercise data, runs XSLT transformations, and writes a `bank.json` file plus a complete static HTML viewer.

2. **The Viewer** (Svelte/TypeScript single-page application, lives in `viewer/`): A browser-based interface that reads `bank.json`, renders exercises using KaTeX for math, allows students to page through versions 1–20, and gives instructors tools to build PDF assessments and export to LMSes.

3. **A Bank** (a directory the instructor creates, example in `demo-bank/`): Contains a `bank.xml` manifest, an `outcomes/` directory tree, and for each outcome a `generator.py` file (plain Python; `generator.sage` selects the optional SageMath runtime instead) plus a `template.xml` file (SpaTeXt XML with Mustache placeholders). A bank may also hold `bank_helpers.py` at its root, importable from every generator.

The intermediate representation between Python generation and browser display is called **SpaTeXt** (Spatial Text) — a small, well-defined XML vocabulary rooted in a `<knowl>` element, using the namespace `https://spatext.clontz.org`. Three XSLT stylesheets transform SpaTeXt into HTML, LaTeX, and PreTeXt. These stylesheets exist **once**, in `dashboard/checkit/static/`. They used to exist twice, with a second copy compiled into the browser viewer, kept in sync by hand across six files; the viewer stopped transforming SpaTeXt in August 2026 and that copy was deleted. See "Browsers are removing XSLT".

### High-level data flow

```
bank.xml + generator.py + template.xml
         |
         | python -m checkit generate
         v
    SageMath runs wrapper.sage
         |
         | for each seed 0..999:
         |   calls Generator().data()
         |   calls json_ready() on all values
         v
    assets/<slug>/generated/seeds.json
         |
         | python -m checkit viewer
         v
    docs/ (static site: viewer HTML/JS + assets/)
         |
         | user opens docs/index.html in browser
         v
    Browser fetches assets/bank.json
    Mustache renders template + exercise data => SpaTeXt XML
    XSLT transforms SpaTeXt => HTML
    KaTeX renders math
```

---

## 2. Repository Map

```
checkit/                             (repo root)
├── CODEBASE_NOTES.md                this file
├── README.md                        one-paragraph project description + install command
├── LICENSE                          MIT License, Copyright 2022 Steven Clontz
├── build_docs.py                    dev script: regenerates demo bank + builds docs site
├── checkit.code-workspace           VS Code workspace file (not functional code)
├── .python-version                  names a pyenv/conda environment called "checkit"
├── .gitignore                       ignores build artifacts and generated files
│
├── dashboard/                       the Python package
│   ├── pyproject.toml               PEP 517 build config (setuptools + wheel)
│   ├── setup.cfg                    package metadata, deps, entry points
│   ├── setup.py                     minimal shim for editable installs
│   ├── update_viewer.py             dev script: builds viewer and zips it into the package
│   ├── tests/                       unittest suite (see "Tests")
│   └── checkit/                     the actual Python package
│       ├── __init__.py              VERSION, PUBLIC_SEEDS, and the precompute format lists
│       ├── __main__.py              CLI entry point (click + trogon)
│       ├── bank.py                  Bank class
│       ├── dashboard.py             deprecated Jupyter widget dashboard
│       ├── exercise.py              Exercise class + XSLT rendering
│       ├── outcome.py               Outcome class
│       ├── checks.py                structural checks on a built bank
│       ├── smoke.py                 runs generators in-process, for tracebacks
│       ├── utils.py                 working_directory() context manager
│       ├── xml.py                   XML namespace constants
│       ├── static/                  files bundled inside the installed package
│       │   ├── __init__.py          read_resource() and open_resource() helpers
│       │   ├── bank.xml             boilerplate bank manifest for `checkit new`
│       │   ├── template.xml         boilerplate SpaTeXt template for `checkit new`
│       │   ├── generator.py         boilerplate generator for `checkit new`
│       │   ├── bank_helpers.py      boilerplate shared-helpers module for `checkit new`
│       │   ├── html.xsl             XSLT: SpaTeXt -> HTML (used server-side)
│       │   ├── latex.xsl            XSLT: SpaTeXt -> LaTeX (used server-side)
│       │   ├── pretext.xsl          XSLT: SpaTeXt -> PreTeXt XML (used server-side)
│       │   ├── devcontainer.json    boilerplate devcontainer config for `checkit new`
│       │   ├── setup.sh             boilerplate conda setup script for `checkit new`
│       │   ├── README.md            boilerplate README for new banks
│       │   ├── gitignore.txt        boilerplate .gitignore for new banks
│       │   └── viewer.zip           pre-built viewer SPA (regenerated by update_viewer.py)
│       └── wrapper/                 SageMath execution harness + image compilation
│           ├── __init__.py          sage() function — launches wrapper.sage as subprocess
│           ├── wrapper.sage         SageMath script: CheckIt helpers + generation loop
│           └── tikz.py              compiles per-seed .tikz files to PNG (pdflatex + pdftoppm)
│
├── demo-bank/                       example bank that documents all features
│   ├── bank.xml                     manifest listing 8 outcomes
│   ├── assets/                      manually placed image files (IMG2 images)
│   │   └── IMG2/                    contains 1.png, 2.png, 3.png (digit images)
│   ├── bank_helpers.py              shared helpers, importable from any generator
│   └── outcomes/                    one subfolder per learning outcome
│       ├── EX/
│       │   ├── EX1/                 Line Slopes outcome
│       │   │   ├── generator.py
│       │   │   └── template.xml
│       │   ├── EX2/                 Product Rule outcome
│       │   │   ├── generator.py
│       │   │   └── template.xml
│       │   └── EX3/                 Tasks/Subtasks demo outcome
│       │       ├── generator.py
│       │       └── template.xml
│       ├── IMG/
│       │   ├── IMG1/                Generating Images outcome
│       │   │   ├── generator.py
│       │   │   └── template.xml
│       │   └── IMG2/                Manual Images outcome
│       │       ├── generator.py
│       │       └── template.xml
│       ├── MX/
│       │   └── MX1/                 Matrix Example outcome
│       │       ├── generator.py
│       │       └── template.xml
│       ├── TIKZ/                    TikZ image-generation test outcome (tkz-euclide)
│       │   ├── generator.py
│       │   └── template.xml
│       ├── XML/                     XML Entities demo outcome
│       │   ├── generator.py
│       │   └── template.xml
│       ├── CURATED/                 hand-written problems keyed to self.seed
│       │   ├── generator.py
│       │   └── template.xml
│       └── WORDS/                   math embedded in a generated sentence
│           ├── generator.py
│           └── template.xml
│
└── viewer/                          Svelte/TypeScript SPA
    ├── index.html                   HTML shell; sets window.bankJsonUrl
    ├── package.json                 npm deps and build scripts
    ├── vite.config.ts               Vite build config
    ├── tsconfig.json                TypeScript config
    ├── svelte.config.js             Svelte preprocessor config
    ├── public/
    │   └── manifest.json            PWA manifest
    └── src/
        ├── main.ts                  mounts App.svelte into #app div
        ├── App.svelte               root component: fetches bank.json, sets up router
        ├── types.ts                 TypeScript type definitions
        ├── global.d.ts              global type ambient declarations
        ├── utils/
        │   └── index.ts             core rendering utilities (outcomeToStx, etc.)
        ├── stores/
        │   ├── banks.ts             Svelte writable store holding loaded Bank object
        │   ├── codecell.ts          boolean store: is code cell iframe visible?
        │   └── instructor.ts        instructor mode flag + assessment outcome slugs
        ├── routes/
        │   ├── index.ts             route table mapping URL patterns to components
        │   ├── Home.svelte          immediately redirects to /bank/
        │   ├── Bank.svelte          layout wrapper showing bank title + outcome dropdown
        │   ├── Outcome.svelte       exercise viewer: version selector + Exercise component
        │   ├── OutcomeRedirect.svelte  redirects /bank/:slug/ to /bank/:slug/1/
        │   ├── Assessment.svelte    PDF assessment builder (instructor only)
        │   ├── Export.svelte        LMS export to Canvas/Brightspace/Moodle
        │   └── NotFound.svelte      404 page
        ├── components/
        │   ├── Exercise.svelte      displays one exercise with tab-mode selector
        │   ├── CodeCell.svelte      dismissible iframe for checkit.clontz.org/codecell/
        │   ├── Nav.svelte           Bootstrap navbar with instructor toggle
        │   ├── Front.svelte         (imported but unused in current routing)
        │   ├── Jumbotron.svelte     hero section component
        │   ├── Sorter.svelte        drag-drop list using svelte-dragdroplist
        │   └── dropdowns/
        │       └── Outcome.svelte   ButtonDropdown listing all outcomes
        ├── spatext/                 SpaTeXt rendering components
        │   ├── Elements/
        │   │   ├── Knowl.svelte     renders a <knowl> element with show/hide answer
        │   │   ├── KnowlContent.svelte  delegates child node rendering to ContentNodes
        │   │   ├── Paragraph.svelte <p> element -> <p> with ParagraphNodes inside
        │   │   ├── Math.svelte      calls katex.renderToString for one math expression
        │   │   ├── Title.svelte     <title> element using TitleNodes
        │   │   └── List.svelte      <list>/<item> -> <ul>/<li> with ContentNodes
        │   ├── NodeList/
        │   │   ├── ContentNodes.svelte  dispatches block-level nodes (p, list, knowl)
        │   │   ├── ParagraphNodes.svelte  dispatches inline nodes (m, me, em, c, q, url, image, tikz-image)
        │   │   └── TitleNodes.svelte  inline nodes allowed inside a title (m, c, em, q)
        │   (there is no xsl/ here any more: the viewer stopped transforming
        │    SpaTeXt in Aug 2026 and reads precomputed formats instead)
        └── templates/
            ├── assessmentTemplate.tex   LaTeX document template for PDF assessments
            ├── canvasManifest.xml       IMS Common Cartridge manifest template
            ├── canvasOutcome.xml        QTI question bank XML template for Canvas
            ├── brightspaceManifest.xml  IMS manifest for D2L Brightspace
            ├── brightspaceBank.xml      QTI question db XML for Brightspace
            └── moodleBank.xml           Moodle XML question bank template
```

---

## 3. Detailed Walkthrough of Every Python File

### `dashboard/checkit/__init__.py`

```python
VERSION = '0.2.8.4'
PUBLIC_SEEDS = 50
INLINE_FORMATS = ("html", "latex", "pretext")
BUNDLE_FORMATS = ("html", "latex")
BUNDLE_FILENAME = "derived.json"
```
(comments elided; each constant carries a long one explaining its failure mode)

Exports `VERSION`, `PUBLIC_SEEDS`, and the precompute coverage lists (`INLINE_FORMATS`, `BUNDLE_FORMATS`, `BUNDLE_FILENAME`).

`VERSION` is read by `setup.cfg` (`version = attr: checkit.VERSION`), so it becomes the wheel's version and filename, and by `__main__.py` when writing a new bank's `requirements.txt`. It is a fourth-component fork version — **`0.2.8.4` as of 2026-08-27, not `0.2.8`** — see Appendix A for why sharing upstream's number is actively dangerous, and why the obvious `0.2.8+slye.1` does not work. Bump it whenever a bank could tell the difference: a new SpaTeXt element is a hard dependency, since the stylesheets drop an unknown element and its contents silently. The footer in `App.svelte` still says v0.2.8, which is the upstream release this forked from.

---

### `dashboard/checkit/__main__.py`

This file is the CLI entry point. When you run `python -m checkit` or just `checkit` (after `pip install`), Python runs this file.

**Imports:**
- `click` — the CLI framework
- `trogon` — wraps click apps with an optional interactive TUI (terminal UI)
- `os` — for `makedirs`
- `. import static, VERSION, bank` — the package's own modules

**`@tui()` decorator:** Provided by `trogon`. When the user runs `checkit tui`, it opens a rich terminal UI that lets them fill in options interactively. Without the decorator, `checkit` behaves as a normal `click` group.

**`main()` function:**
The `click.group` root. Has `short_help="CheckIt command line interface"`. No logic itself — it's the group container.

**`new(directory)` — `checkit new [DIRECTORY]`:**
- `directory` defaults to `'new-checkit-bank'`
- Creates `<directory>/` (warns if it exists)
- Creates `<directory>/outcomes/EX1/` and copies `template.xml` and `generator.py` from the bundled static resources
- Creates `<directory>/.devcontainer/` and copies `setup.sh` and `devcontainer.json`
- Copies `bank.xml`, `README.md` and `bank_helpers.py` into the root
- Copies `gitignore.txt` as `.gitignore`
- Writes `requirements.txt` pointing at **this fork's release wheel URL**, with a comment explaining why. It deliberately does *not* write `checkit-dashboard == {VERSION}`: that resolves on PyPI, where the name belongs to upstream. See "Packaging and distribution".
- Prints a success message

**`generate(amount, regenerate, images, image_seeds, outcome)` — `checkit generate`:**
Options:
- `-a`/`--amount` (default 1000): number of seeds to generate
- `-r`/`--regenerate` (flag): if set, regenerates even if seeds.json already exists
- `-i`/`--images` (flag): if set, also generates PNG graphics
- `--image-seeds` (int, default None / no short flag): render images for only the first N seeds of each outcome, while still generating full seed *data* for all of them. Intended for quick local previews; a low value produces broken images for the viewer (`PUBLIC_SEEDS`, currently 50) and LMS export (seeds 100–999). See §12 "Limiting image rendering with `image_seeds`".
- `-o`/`--outcome` (default "ALL"): name of a specific outcome slug to generate; "ALL" generates everything

Logic:
1. Creates a `Bank()` (reads `bank.xml` from the current working directory)
2. If `outcome != "ALL"`, filters `b._outcomes` to only the one with the matching slug (case-insensitive)
3. Calls `b.generate_exercises(regenerate=..., images=..., amount=..., image_seeds=...)`
4. Calls `b.write_json()` to produce `assets/bank.json`

**`viewer()` — `checkit viewer`:**
Calls `bank.Bank().build_viewer()`, which unpacks the bundled `viewer.zip` into a `docs/` directory and copies the `assets/` folder there.

---

### `dashboard/checkit/bank.py`

Defines the `Bank` class, which represents an entire exercise bank loaded from disk.

**Imports:** `lxml.etree`, `os`, `json`, `datetime`, `zipfile`, `shutil`, `pathlib.Path`, `.static`, `.outcome.Outcome`, `.xml.CHECKIT_NS`

**`Bank.__init__(self, path=".")`**

- `self._abspath = os.path.abspath(path)` — stores the absolute path to the bank root
- Parses `bank.xml` via `lxml.etree.parse(...)`. Raises an exception if the `version` attribute on `<bank>` is not `"0.2"`.
- Reads `<title>`, `<slug>`, `<url>` text from the XML (all in the `https://checkit.clontz.org` namespace, accessed via the `CHECKIT_NS` prefix string `"{https://checkit.clontz.org}"`).
- Iterates over all `<outcome>` elements inside `<outcomes>`, constructing one `Outcome` object per entry with title, slug, path, description, and a back-reference to `self`.
- Calls `o.load_exercises(strict=False)` for every outcome. `strict=False` means if `seeds.json` doesn't exist yet, the outcome silently has no exercises rather than raising an error.

**`Bank.abspath(self)`**
Returns `self._abspath`. Used by `Outcome` to construct its own absolute path.

**`Bank.outcomes(self)`**
Returns `self._outcomes` list.

**`Bank.generate_exercises(self, regenerate=False, images=False, amount=1_000, image_seeds=None)`**
Iterates `self.outcomes()`, prints a progress message, and calls `o.generate_exercises(...)` for each one, passing `image_seeds` through unchanged.

**`Bank.build_path(self)`**
Returns (and creates if needed) `<bank_root>/assets/`. This is where all generated data is written.

**`Bank.to_dict(self, regenerate=False)`**
Returns a Python dict with keys:
- `"title"` — bank title string
- `"slug"` — bank slug string
- `"url"` — bank URL string
- `"generated_on"` — current UTC ISO timestamp
- `"outcomes"` — list of dicts, one per outcome (see `Outcome.to_dict`)

**`Bank.write_json(self, regenerate=False)`**
Calls `self.to_dict(...)` and dumps it as JSON to `assets/bank.json`.

**`Bank.build_viewer(self)`**
1. Deletes `docs/` directory if it exists
2. Creates it fresh
3. Extracts the bundled `viewer.zip` (from `checkit.static`) into `docs/`
4. Copies `assets/` into `docs/assets/` (with `dirs_exist_ok=True`)

The result is a fully self-contained static site.

**`Bank.generated_on(self)`**
Reads `assets/bank.json` and returns its `"generated_on"` field. Returns `"(never generated)"` on any error.

---

### `dashboard/checkit/outcome.py`

Defines the `Outcome` class, representing one learning outcome within a bank.

**Imports:** `.exercise.Exercise`, `os`, `json`, `random`, `html.escape`, `.wrapper.sage`, `.wrapper.tikz.compile_tikz_for_outcome`

**`Outcome.__init__(self, title, slug, path, description, bank)`**
Stores all five arguments as instance attributes. `path` is relative to the bank root (e.g., `"outcomes/EX/EX1"`), stored as `self.relpath`.

**`Outcome.abspath(self)`**
Returns `os.path.join(self.bank.abspath(), self.relpath)`. The full filesystem path to the outcome directory.

**`Outcome.full_title(self, max_length=None)`**
Returns `"<slug>: <title>"`. If `max_length` is given and the string is too long, truncates with `"…"`.

**`Outcome.template_filepath(self)`**
Returns the full path to `<outcome_dir>/template.xml`.

**`Outcome.template(self)`**
Reads and returns the raw text of `template.xml`.

**`Outcome.generator_path(self)`**
Returns the full path to the outcome's generator, trying `GENERATOR_FILENAMES` in order — `generator.py` first, then `generator.sage`. **The extension is what selects the runtime** (see "Generator runtimes"). If neither exists it returns the `generator.py` path, so the `FileNotFoundError` raised downstream names an expected location.

**`Outcome.to_dict(self, regenerate=False)`**
Calls `self.generate_exercises(regenerate)` to ensure data is fresh, then returns:
```python
{
    "title": self.title,
    "slug": self.slug,
    "description": self.description,
    "template": self.template(),       # raw XML string
    "exercises": [e.to_dict() for e in self.exercises()],  # list of {seed, data}
}
```

**`Outcome.preview_exercises(self)`**
Used by the (deprecated) Jupyter dashboard for "fresh preview". Calls `run_generator(self, preview_json, preview=True, images=True)` to generate `PUBLIC_SEEDS` seeds, then `compile_tikz_for_outcome(self, image_seeds=PUBLIC_SEEDS)` to turn any generated `.tikz` files into PNGs, reads them, and returns a list of `Exercise` objects. Using the same constant for both matches preview mode's seed count — without it a preview taken after a 1000-seed build would walk and recompile every seed directory in the outcome.

**`Outcome.html_preview(self, pregenerated=False)`**
Used by the Jupyter dashboard. If `pregenerated=True`, picks a random already-generated exercise; otherwise calls `preview_exercises()`. Returns a long HTML string showing the rendered exercise, its JSON data, SpaTeXt XML, HTML, LaTeX, and PreTeXt.

**`Outcome.build_path(self)`**
Returns (creating if needed) `<bank>/assets/<slug>/generated/`. All generated files for this outcome go here.

**`Outcome.seeds_json_path(self)`**
Returns `<build_path>/seeds.json`.

**`Outcome.generate_exercises(self, regenerate=False, images=False, amount=1_000, image_seeds=None)`**
- If `regenerate=False`, tries `self.load_exercises()`. If that succeeds (seeds.json exists and is valid), returns early.
- Otherwise calls `sage(self, self.seeds_json_path(), preview=False, images=images, amount=amount, image_seeds=image_seeds)` — this invokes the SageMath subprocess.
- If `images=True`, then calls `compile_tikz_for_outcome(self, image_seeds=image_seeds)` to rasterize the `.tikz` files the generator wrote into PNGs, honoring the same cap. (`.tikz` files themselves are written by `wrapper.sage` regardless of `images`; this step is only the PNG half.)
- Then calls `self.load_exercises(reload=True)` to read the newly written file.

**`Outcome.load_exercises(self, reload=False, strict=True)`**
- If `reload=False` and `self._exercises` already exists, returns immediately.
- Reads `seeds.json`, parses JSON, creates an `Exercise` for each entry.
- If the file doesn't exist and `strict=True`, raises `RuntimeError`. If `strict=False`, silently does nothing.

**`Outcome.generated_on(self)`**
Returns `self._generated_on` (set when exercises are loaded) or `"(never generated)"`.

**`Outcome.exercises(self, all=True, amount=300, randomized=False)`**
- If `all=True` (default), returns the full `self._exercises` list.
- If `all=False` and `randomized=False`, returns the first `amount` exercises.
- If `all=False` and `randomized=True`, returns `amount` randomly sampled exercises (indices sorted so order matches original sequence).
- Raises `RuntimeError` if exercises haven't been loaded/generated yet.

---

### `dashboard/checkit/exercise.py`

Defines the `Exercise` class, which represents one specific generated variant of an exercise (identified by its seed number and data dictionary).

**Imports:** `lxml.etree`, `latex2mathml.converter.convert`, `pystache`, `.static.read_resource`

**`tex_to_mathml(tex)`** — module-level helper.
Calls `latex2mathml`'s `convert()` to turn a LaTeX math string into a MathML XML string, then parses it into an `lxml` element. (This function is defined but not currently called anywhere in the main code paths — the browser uses KaTeX instead.)

**`Exercise.__init__(self, data, seed, outcome)`**
Stores `data` (a dict of JSON-serializable values like `{"slope": "3", "equation": "3x+2y=5"}`), `seed` (integer), and `outcome` (back-reference to the `Outcome`).

**`Exercise.spatext_ele(self)`**
This is the core rendering method. Steps:
1. Creates a `pystache.Renderer()`.
2. Calls `renderer.render_path(template_filepath, data)` — reads the `template.xml` file and replaces all `{{variable}}` placeholders with the string values from `self.data`. The result is a string of SpaTeXt XML.
3. Parses that string into an `lxml` element with `etree.fromstring(bytes(xml_string, encoding='utf-8'))`.
4. If parsing fails (`XMLSyntaxError`), re-raises with line numbers shown for debugging.
5. Strips XML comments with `etree.strip_tags(ele, etree.Comment)`.
6. Returns the root element.

**`Exercise.spatext(self)`**
Calls `self.spatext_ele()` and serializes the result to a pretty-printed UTF-8 string.

**`Exercise.html_ele(self, subset='all', consumer='basic')`**
1. Loads `html.xsl` from the static package via `read_resource("html.xsl")`.
2. Creates an `lxml.etree.XSLT` transformer.
3. Transforms the SpaTeXt element, passing `subset` and `consumer` as XSLT string parameters (both currently unused in the stylesheets but reserved for future subsetting features).
4. Returns the root element of the resulting HTML tree.

**`Exercise.html(self, subset='all', consumer='basic')`**
Calls `self.html_ele(...)` and serializes to a UTF-8 string.

**`Exercise.pretext_ele(self, subset='all', consumer='basic')`**
Same pattern as `html_ele` but uses `pretext.xsl`.

**`Exercise.pretext(self, subset='all', consumer='basic')`**
Serializes the PreTeXt element to string.

**`Exercise.latex(self)`**
Loads `latex.xsl`, transforms `spatext_ele()`, and returns the text content as a string. (The LaTeX XSLT outputs plain text, so `str(transform(...))` works directly.)

**`Exercise.to_dict(self)`**
Returns `{"seed": self.seed, "data": self.data}`. This is what ends up in `seeds.json` and `bank.json`.

---

### `dashboard/checkit/utils.py`

A single utility function:

**`working_directory(path)`** — context manager
Saves the current working directory, changes to `path`, yields (allowing the `with` block to execute), then restores the original directory even if an exception is raised. Used in `wrapper/__init__.py` to `cd` to the bank root before invoking SageMath, ensuring that `load(generator_path)` inside SageMath resolves relative imports correctly.

---

### `dashboard/checkit/xml.py`

Two constants:

```python
CHECKIT_NS = "{https://checkit.clontz.org}"
SPATEXT_NS = "{https://spatext.clontz.org}"
```

`lxml` uses Clark notation for namespace-qualified names: `{namespace_uri}localname`. So `f"{CHECKIT_NS}title"` is the lxml tag name for `<title xmlns="https://checkit.clontz.org">`. `SPATEXT_NS` is defined but not used in the current Python code (the XSLT stylesheets handle the SpaTeXt namespace internally).

---

### `dashboard/checkit/static/__init__.py`

```python
import importlib.resources

def read_resource(resource_name):
    return importlib.resources.read_text("checkit.static", resource_name)

def open_resource(resource_name):
    return importlib.resources.open_binary("checkit.static", resource_name)
```

These two functions use Python's `importlib.resources` API to read files that were bundled inside the installed package (anything in `dashboard/checkit/static/`). `read_resource` returns a string (for `.xsl`, `.xml`, `.sage`, `.txt` files). `open_resource` returns a binary file handle (used for `viewer.zip`).

---

### `dashboard/checkit/wrapper/__init__.py`

Defines `run_generator()`, which launches the generation subprocess, and the
`RUNTIMES` table that decides *which* subprocess. The generator's file extension
selects the runtime -- `generator.py` runs under `sys.executable` with
`wrapper.py`, `generator.sage` runs under `sage` with `wrapper.sage`. See
"Generator runtimes" near the end of this document.

(Formerly named `sage()`. Renamed because a function named `sage()` that may
launch Python is actively misleading.)

**`run_generator(outcome, output_path, preview=True, images=False, amount=1_000, random=False, image_seeds=None)`**

Parameters:
- `outcome` — an `Outcome` instance; provides `outcome.generator_path()` and `outcome.bank.abspath()`
- `output_path` — full path where `seeds.json` will be written
- `preview` — if True, forces `amount=20` and `random_s="no"`
- `images` — if True, adds `"images"` to the subprocess command
- `amount` — how many seeds to generate
- `random` — if True, uses random seeds instead of sequential 0,1,2,...
- `image_seeds` — if not None and `images` is set, appends the cap as a further argument after `"images"` (becomes `sys.argv[6]` in wrapper.sage), limiting image rendering to the first N seeds

Logic:
1. Computes `amount_s` and `random_s` strings based on flags
2. Raises `FileNotFoundError` if the generator doesn't exist
3. Uses `importlib.resources.path("checkit.wrapper", "wrapper.sage")` to get the path to the bundled wrapper script (as a context manager, because `importlib.resources` may extract it to a temp location for non-directory packages)
4. Creates a temporary directory
5. Copies `wrapper.sage` into it
6. Uses `working_directory(outcome.bank.abspath())` to `cd` to the bank root
7. Runs: `sage /tmp/xxx/wrapper.sage <generator_path> <output_path> <amount> <random_s> [images [image_seeds]]` — the `images` token is only present when `images=True`, and the `image_seeds` count is only appended after it when `image_seeds is not None`
8. `subprocess.run(cmds, check=True)` — raises `CalledProcessError` if Sage exits non-zero

---

### `dashboard/checkit/dashboard.py`

This file is **deprecated** as of version 0.2.7. It implements a Jupyter widget-based dashboard that was the original interface before the CLI was introduced. It prints a deprecation warning on import:

```python
print("""
Jupyter dashboard is DEPRECATED - can use as-is, but we recommend
using Codespaces/CLI as of 0.2.7
""")
```

**`modifiedOutput`** — subclass of `ipywidgets.Output` with a patched `__exit__` to work around a bug in ipywidgets (GitHub issue #3208). This prevents the widget output area from locking up when the code inside the `with output:` block raises an exception.

**`run(bank=None)`**
Creates the top-level Jupyter UI:
- A `Dropdown` with `Author/edit outcomes` and `Manage bank` options
- An `Output` area for the sub-menu
- Calls `change_submenu(submenu, bank)` as the observer

**`change_submenu(submenu, bank)`**
Returns an observer callback. When the dropdown changes:
- If `'outcome'` → calls `outcome_submenu(bank)`
- If `'bank'` → calls `bank_submenu(bank)`

**`outcome_submenu(bank)`**
Renders a sub-UI with:
- A `Dropdown` of all outcomes
- Four buttons: "Fresh preview", "View random seed", "Generate seeds", "Gen seeds+graphics"
- An output area showing description + last generated date
- A preview area

Callbacks: `preview()` calls `o.html_preview(pregenerated=False)`, `seed()` calls `o.html_preview(pregenerated=True)`, `build()` calls `o.generate_exercises(regenerate=True)`, `images()` calls `o.generate_exercises(regenerate=True, images=True)`.

**`bank_submenu(bank)`**
Renders a sub-UI with two buttons: "Bank from cache" and "Regenerated bank". Clicking either calls `bank.write_json()` then `bank.build_viewer()`.

---

### `dashboard/update_viewer.py`

A development script (not part of the installed package). Run as `python update_viewer.py` from inside `dashboard/`.

**`main()`**
1. Changes to `../demo-bank/` and runs `python -m checkit generate -r -i --image-seeds 20` to regenerate all demo exercises. The `-i` is load-bearing: without it the demo bank is rebuilt with no images at all, and `build_docs.py` then publishes that over `docs/demo`, **deleting** previously published PNGs (this is what commit `d36c6a3` did). The cap holds the run down — the viewer only shows `PUBLIC_SEEDS` seeds, and `.tikz` source is written for every seed regardless, so LaTeX output is unaffected.
2. Changes to `../viewer/` and runs `npm run build`
3. Copies the Vite build output (`viewer/dist/`) to a temp directory
4. Removes `assets/bank.json` from the copy (the viewer is meant to load bank.json from wherever it's deployed, not bundle a specific one)
5. Calls `shutil.make_archive(..., 'zip', ...)` to zip the temp directory, saving to `dashboard/checkit/static/viewer.zip`

The resulting `viewer.zip` is bundled inside the installed Python package and extracted by `Bank.build_viewer()`.

---

### `build_docs.py`

Another development script at the repo root. Run to regenerate the docs site.

1. Changes to `dashboard/` and calls `dashboard.update_viewer.main()` — rebuilds viewer.zip
2. Changes to `demo-bank/` and calls `bank.write_json()` and `bank.build_viewer()` — generates `demo-bank/docs/`
3. Removes `docs/demo/` if it exists
4. Copies `demo-bank/docs/` to `docs/demo/`

Note that step 3 is a `shutil.rmtree` — `docs/demo/` is **replaced**, not merged. Whatever the regenerated `demo-bank/assets/` happens to contain is the entire published site. That is why step 1's `-i` flag matters: a regeneration without images produces an assets tree with none, and step 4 then publishes that emptiness over the committed PNGs. Commit `d36c6a3` deleted every published IMG1 image exactly this way.

---

## 4. Detailed Walkthrough of the Generator Runtimes

There are two, chosen by a generator's file extension (see "Generator runtimes"
near the end of this document). **`wrapper/wrapper.py` is the default**;
`wrapper/wrapper.sage` is retained for banks that need SageMath. The demo bank is
entirely `.py`, so nothing here exercises the Sage path any more.

SageMath (`.sage`) files look like Python but are preprocessed by SageMath before execution. Key differences -- each of which is a silent-failure hazard when porting a generator to `.py`:
- `^` is exponentiation (Python's `**`; in Python `^` is bitwise XOR)
- `a == b` builds a symbolic equation (in Python it compares and returns a bool -- use `Eq(a, b)`)
- `1/3` is an exact rational (in Python it is a float -- use `Rational(1, 3)`)
- Many mathematical objects like `var`, `randrange`, `choice`, `shuffle`, `ZZ`, `QQ`, `SR`, `matrix`, etc. are available as global names. `wrapper.py` supplies its own equivalents explicitly via `GENERATOR_NAMESPACE`.
- `set_random_seed(n)` makes all subsequent random operations deterministic with seed `n` (`wrapper.py` maps this onto `random.seed`)

### `dashboard/checkit/wrapper/wrapper.sage`

This is the most important `.sage` file — it's the harness that runs every generator.

#### Class: `CheckIt`

A collection of static helper methods made available to every `Generator` author. Authors call these as `CheckIt.method_name(...)`.

**`CheckIt.vars(*latex_names, random_order=True)`**

Purpose: Create symbolic SageMath variables whose names in expressions appear in random order (to prevent students from always recognizing "it's the first variable").

How it works:
1. Generates a random 6-digit `stamp` integer
2. Creates a list of indices `[0, 1, ..., n-1]` and shuffles if `random_order=True`
3. Picks a random lowercase letter `random_letter`
4. For each `latex_name` string and its shuffled index `i`, creates a Sage variable with internal name `<random_letter>_mi_var_<stamp>_<i>` but with `latex_name=name` so it displays correctly in LaTeX
5. Returns a generator of these variables

Example usage: `x, y = CheckIt.vars("x", "y")`. The variables display as `x` and `y` in LaTeX, but their internal Sage ordering is randomized so that `x + y` might render as `y + x` depending on the seed.

**`CheckIt.shuffled_equation(*terms)`**

Purpose: Produce an equation equivalent to `sum(terms) = 0` but with terms randomly distributed to both sides, and the whole equation possibly multiplied by -1.

How it works:
1. Starts with `0 == 0`
2. For each `term`, randomly either adds `(term == 0)` (putting it on the left) or `(0 == -term)` (putting it on the right)
3. Multiplies the final equation by `choice([-1, 1])` to randomly flip it

This ensures students see the equation in genuinely different forms rather than always `ax + b = c`.

**`CheckIt.shuffled_inequality(*terms, strict=True)`**

Purpose: Same idea as `shuffled_equation` but creates `sum(terms) > 0` or `< 0` (strict) or `>= 0` / `<= 0` (non-strict), with random direction and random side assignment of terms.

**`CheckIt.latex_system_from_matrix(matrix, variables="x", alpha_mode=False, variable_list=None)`**

Purpose: Convert an augmented matrix (with a vertical bar dividing the coefficient columns from the right-hand-side column) into LaTeX markup for a system of equations.

How it works:
1. If the matrix has no column subdivisions, augments with a zero vector on the right
2. Determines the number of variables from the subdivision position
3. Builds the variable list: `variable_list` first, then `x, y, z, w, v` if `alpha_mode=True`, then `x_1, x_2, ...` as fallback
4. Constructs a `\begin{matrix}...\end{matrix}` LaTeX string, one row per equation, using `&` column separators for alignment
5. For each coefficient: writes `+ coeff*var`, `- |coeff|*var`, or nothing (if zero), tracking `previous_terms` to decide whether to emit a `+` sign
6. Writes `= rhs` at the end of each row

The result is valid LaTeX for a properly aligned system of equations.

**`CheckIt.latex_solution_set_from_matrix(matrix)`**

Purpose: Solve an augmented linear system and return its solution set as a LaTeX set-builder expression.

How it works:
1. Augments with zero vector if needed
2. Checks if the last column is a pivot column (inconsistent system); if so, returns `\{\}` (empty set)
3. Computes the right kernel of the coefficient submatrix in "pivot" basis
4. Uses free variables `a, b, c, d, e, f, g, h, i, j` (up to 10 free variables)
5. Computes `span` as a linear combination of kernel basis vectors with free variables
6. Computes `offset` as the particular solution from the RREF
7. Returns LaTeX like `\left\{ \begin{pmatrix} \ldots \end{pmatrix} \,\middle|\, a, b \in \mathbb{R} \right\}`

**`CheckIt.simple_random_matrix_of_rank(rank, rows=1, columns=1, augmented=False)`**

Purpose: Generate a pedagogically reasonable matrix of a given rank, suitable for linear algebra exercises.

How it works:
1. Computes `extra_rows = max(0, rows-rank)` and `extra_columns = max(0, columns-rank)`
2. Creates an "echelonizable" matrix with `random_matrix(QQ, rank+extra_rows, rank, algorithm='echelonizable', rank=rank, upper_bound=6)` — this gives integer entries in RREF with values in [-5,5]
3. Randomly chooses insertion points (`inserts`) for dependent columns
4. With 50% probability, forces the last column to be dependent (a common pedagogical scenario)
5. Inserts dependent columns (random linear combinations of previous columns) to reach the desired column count
6. If `augmented=True`, marks the last column as the augmentation with `A.subdivide([],[columns-1])`

#### Function: `provide_data(func)`

A decorator used to wrap the `graphics()` method in the base class and in generators. It transforms a function that takes `data` as a plain argument into a method that ignores `self` and instead calls `func(self.get_data())`.

```python
def provide_data(func):
    return lambda self: func(self.get_data())
```

So when a generator writes:
```python
@provide_data
def graphics(data):
    return {"plot": plot(data["line"])}
```
The method, when called as `generator.graphics()`, automatically receives the current `data` dict.

#### Class: `BaseGenerator`

Every generator must define a `Generator` class that extends `BaseGenerator`. This base class handles seed management so authors don't have to.

**`__init__(self)`**
Sets `self.__data = None` and `self.__seed = None` (double-underscored = name-mangled, truly private), plus `self.variant = None` (the shuffle-bag–assigned problem type; see below).

**`data(self)`**
Default implementation returns `{}`. Subclasses override this to return the actual exercise data dict. Note: this is a pure function — it should generate fresh random data every time it's called (using Sage's `randrange`, `choice`, etc., which are seeded by `set_random_seed`).

**`graphics(data)`**
Default decorated with `@provide_data`, returns `None`. Subclasses override this to return `{filename: sage_graphics_object}` (each saved as `<filename>.png`).

**`tikz_graphics(data)`**
Default decorated with `@provide_data`, returns `None`. Subclasses override this to return `{name: <tikz source string>}`. The wrapper writes each as a `<name>.tikz` file; `wrapper/tikz.py`'s `compile_tikz_for_outcome()` later compiles those to `<name>.png`. See §12 "Image generation backends" and the TIKZ demo generator below.

**`roll_data(self, seed=None, variant=None)`**
If `seed` is None, calls `set_random_seed()` (seeds from system entropy) and picks a random seed in [0,999]. Otherwise uses the given seed. Stores `seed` in `self.__seed` and `variant` in `self.variant`, then calls `set_random_seed(seed)` to make all random operations deterministic, and finally calls `self.data()`, storing the result in `self.__data`.

**`get_data(self)`**
Returns `self.__data` with `"__seed__"` injected as a zero-padded 4-digit string. The `__seed__` key is special — it lets templates reference `{{__seed__}}` to construct image paths like `assets/IMG1/generated/{{__seed__}}/plot.png`. If a variant was assigned and is a primitive (`str`/`int`/`bool`), `"__variant__"` is also injected so templates can show it and the spread is easy to verify in `seeds.json`.

#### Evenly spreading problem types: `variants` and `build_variant_bag`

When an outcome has a limited, hand-authored set of *problem types* (e.g. 20–50 distinct word-problem formats, or whole hand-built exercises), choosing the type inside `data()` with `choice([...])` makes identical types cluster back-to-back, because each seed draws independently. To fix this, a generator may declare a class attribute:

```python
class Generator(BaseGenerator):
    variants = ["derivative", "rate of change"]   # any list of labels, even dicts
    def data(self):
        kind = self.variant   # assigned by the wrapper, not rolled here
        ...
```

**`variants`** — defaults to `None` (feature off; legacy behavior). When set to a non-empty list, the wrapper assigns each seed one label via an even *shuffle-bag* and exposes it as `self.variant`.

**`build_variant_bag(self, amount)`** — returns a length-`amount` list of labels. Each "chunk" is a freshly shuffled full permutation of `self.variants`, so counts are as even as possible. If a new chunk's first label equals the previous chunk's last label, the chunk is re-shuffled (up to 20 tries) to prevent a repeat across the boundary. The bag is built under a fixed RNG seed (`set_random_seed(0)`), so the order is reproducible and the first-N prefix is stable across different `amount` values. For 12 seeds and 4 types you get e.g. `B C A D | A D C B | D A B C`.

Numbers inside each exercise are still randomized per-seed exactly as before — only the *type* is now assigned externally. Backward compatible: generators that don't declare `variants` are unaffected.

#### Function: `json_ready(obj)`

Recursively converts SageMath objects to JSON-serializable Python strings.

```python
def json_ready(obj):
    if isinstance(obj, str) or isinstance(obj, bool):
        return obj
    elif isinstance(obj, list):
        return [json_ready(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: json_ready(obj[key]) for key in obj.keys()}
    else:
        return str(latex(obj))
```

This is critical: a Sage expression like `3*x + 2` would not survive JSON serialization, but `str(latex(3*x + 2))` produces `"3 x + 2"` which is a string that both JSON and the Mustache template engine can handle. Every value in the generator's `data()` dict goes through this conversion.

#### Main execution block

The script is called as:
```
sage wrapper.sage <generator_path> <output_path> <amount> [random|no] [images [image_amount]]
```
`image_amount` (`sys.argv[6]`) is optional and only meaningful when `images` is present; it caps image rendering to the first N seeds. It defaults to `amount` (render images for every seed) when omitted.

Steps:
1. Parses command-line arguments from `sys.argv`, including `image_amount = int(sys.argv[6]) if (gen_images and len(sys.argv) >= 7) else amount`
2. Calls `load(generator_path)` — SageMath's `load()` function executes the generator file in the current namespace, making its `Generator` class available
3. Creates a `Generator()` instance
4. If the generator declares `variants`, calls `generator.build_variant_bag(amount)` once to get the length-`amount` list of type labels (otherwise `variant_bag` is `None`)
5. Loops `amount` times (printing `Generating seed {i}` every 50 seeds as a progress indicator):
   - If `random` mode: picks a random seed in [0,999]
   - Otherwise: seed = loop index i
   - Picks `variant = variant_bag[i]` if a bag exists, else `None`
   - Calls `generator.roll_data(seed=seed_int, variant=variant)` to generate the data
   - Calls `generator.get_data()` and wraps with `json_ready()` to get serializable data
   - Unconditionally calls `generator.tikz_graphics()`; if non-None, creates the seed directory and writes each value as a `<name>.tikz` file (these are compiled to PNG afterward by `tikz.py`, back in the Python layer — not by SageMath). Deliberately outside both gates: the source is a few hundred bytes of text and the LaTeX output `\input{}`s it, so print must have it for every seed.
   - If `gen_images and i < image_amount` (so the cap limits which seeds get *rasterized*):
     - Calls `generator.graphics()`; if non-None, creates the seed directory and saves each value as `<filename>.png`
   - Appends `{"seed": seed_int, "data": data}` to `seeds` list
6. Writes the full JSON: `{"seeds": [...], "generated_on": "...ISO timestamp..."}` to `output_path`

---

### `demo-bank/outcomes/EX/EX1/generator.py`

This generator illustrates how to use Sage's symbolic algebra to create a two-part problem about line slopes.

```python
class Generator(BaseGenerator):
    def data(self):
        x, y = var("x y")

        # Generate random line with slope -B/A
        A = randrange(1, 10) * choice([-1, 1])
        B = A
        while A == B:
            B = randrange(1, 10) * choice([-1, 1])
        C = randrange(-9, 10)
        line1 = {
            'equation': (A*x + B*y == C),
            'slope': -A/B,
        }

        # Generate random line with slope m
        m = randrange(1, 10) * choice([-1, 1])
        b = randrange(-9, 10)
        line2 = {
            'equation': (y == m*x + b),
            'slope': m,
        }

        lines = [line1, line2]
        shuffle(lines)

        return {
            "lines": lines,
            "alt_prompt": choice([True, False]),
        }
```

Key Sage features: `var("x y")` creates symbolic variables. `(A*x + B*y == C)` creates a Sage symbolic equation. `-A/B` computes an exact rational slope. The `lines` list is shuffled so the two equations appear in random order in the exercise. The `alt_prompt` boolean selects between two different wording choices in the template (via Mustache's `{{#alt_prompt}}...{{/alt_prompt}}` syntax).

After `json_ready()`, `line['equation']` becomes a LaTeX string like `"3 x + 5 y = 7"` and `line['slope']` becomes a LaTeX string like `"-\\frac{3}{5}"`.

---

### `demo-bank/outcomes/EX/EX2/generator.py`

Demonstrates product rule derivative exercises, and is the worked example of the `variants` shuffle-bag feature.

```python
class Generator(BaseGenerator):
    variants = ["derivative", "rate of change"]

    def data(self):
        x = var("x")
        factors = [
            x^randrange(2, 10),
            e^x,
            cos(x),
            sin(x),
            log(x),
        ]
        shuffle(factors)
        f = choice([-1, 1]) * randrange(2, 5) * factors[0] * factors[1]
        variant = self.variant   # assigned by the shuffle-bag, not rolled here
        return {
            "f": f,
            "dfdx": f.diff(),
            "d_synonym": variant,
        }
```

`f.diff()` is Sage's symbolic differentiation. `e^x` is the natural exponential in Sage (not Python's `e**x`). After `json_ready()`, `f` becomes a LaTeX string like `"3 x^{4} \cos\left(x\right)"` and `dfdx` becomes the LaTeX for its derivative. The problem wording (`d_synonym`) comes from `self.variant`: rather than each seed independently rolling `choice(["derivative", "rate of change"])`, the wrapper hands out the two wordings in an even, shuffled spread, so they no longer clump back-to-back.

---

### `demo-bank/outcomes/EX/EX3/generator.py`

Minimal generator for demonstrating nested task/subtask structure:

```python
class Generator(BaseGenerator):
    def data(self):
        return {
            "first": {
                "first": randrange(10),
                "second": randrange(10),
                "third": randrange(10),
            },
            "second": randrange(10),
        }
```

The `"first"` key holds a nested dict, which Mustache uses with `{{#first}}...{{/first}}` section syntax to render the nested template block with access to `{{first}}`, `{{second}}`, and `{{third}}` keys.

---

### `demo-bank/outcomes/MX/MX1/generator.py`

Demonstrates `CheckIt.simple_random_matrix_of_rank` and `CheckIt.latex_system_from_matrix`:

```python
class Generator(BaseGenerator):
    def data(self):
        rows = randrange(3, 5)
        columns = 8 - rows
        max_number_of_pivots = min(rows, columns - 1)
        number_of_pivots = randrange(2, max_number_of_pivots + 1)
        A = CheckIt.simple_random_matrix_of_rank(number_of_pivots, rows=rows, columns=columns)
        A.subdivide([], [columns - 1])
        xs = choice([
            [var("x_" + str(i+1)) for i in range(0, columns-1)],
            [var("x"), var("y"), var("z"), var("zw", latex_name="w")][0:columns-1],
        ])
        return {
            "system": CheckIt.latex_system_from_matrix(A, variable_list=xs),
            "matrix": A,
        }
```

`A.subdivide([], [columns-1])` marks the last column as the augmentation column. `latex_system_from_matrix` returns a raw LaTeX string (already a string, not a Sage object), so `json_ready()` leaves it unchanged. `A` (the Sage matrix) goes through `json_ready()` → `str(latex(A))` to produce LaTeX for an augmented matrix with a vertical bar.

---

### `demo-bank/outcomes/IMG/IMG1/generator.py`

Demonstrates generated graphics:

```python
class Generator(BaseGenerator):
    def data(self):
        x = var("x")
        m = randrange(-9, 10)
        b = randrange(-9, 10)
        line = m*x + b
        findfunction_line = {"line": line, "slope": m, "intercept": b}
        m = randrange(-9, 10)
        b = randrange(-9, 10)
        line = m*x + b
        todraw_line = {"line": line, "slope": m, "intercept": b}
        return {
            "findfunction_line": findfunction_line,
            "todraw_line": todraw_line,
        }

    @provide_data
    def graphics(data):
        return {
            "find": plot(data["findfunction_line"]["line"]),
            "draw": plot(data["todraw_line"]["line"]),
        }
```

The `@provide_data` decorator means `graphics()` receives the processed `data` dict (with `__seed__` injected). Sage's `plot()` function creates a SageMath graphics object. In `wrapper.sage`, these are saved as `<build_path>/<seed:04d>/find.png` and `<build_path>/<seed:04d>/draw.png`. The template then references them via `{{__seed__}}`.

---

### `demo-bank/outcomes/IMG/IMG2/generator.py`

Demonstrates manually-placed images:

```python
class Generator(BaseGenerator):
    def data(self):
        image_version = f"{randrange(1, 4)}"
        return {"digit": image_version}
```

Randomly selects `"1"`, `"2"`, or `"3"` — corresponding to pre-existing files `demo-bank/assets/IMG2/1.png`, `demo-bank/assets/IMG2/2.png`, `demo-bank/assets/IMG2/3.png` (placed there manually). The template references `source="assets/IMG2/{{digit}}.png"`.

---

### `demo-bank/outcomes/XML/generator.py`

Demonstrates XML entity usage (`&amp;`, `&gt;`) and Mustache boolean sections:

```python
class Generator(BaseGenerator):
    def data(self):
        x = var('x')
        ints = list(IntegerRange(-9, 0)) + list(IntegerRange(1, 10))
        shuffle(ints)
        fs = list('fghjklmn')
        shuffle(fs)

        continuous = True
        left = ints[0]*x + ints[1]
        right = ints[2]*x + ints[1]   # same constant => continuous at 0
        functions = [{'left': left, 'right': right, 'continuous': continuous, 'f': fs[0]}]

        continuous = False
        left = ints[3]*x + ints[4]
        right = ints[5]*x + ints[6]   # different constants => discontinuous at 0
        functions += [{'left': left, 'right': right, 'continuous': continuous, 'f': fs[1]}]

        shuffle(functions)
        return {"functions": functions}
```

`IntegerRange(-9, 0)` is a Sage range object (like Python `range` but inclusive of Sage integers). `list('fghjklmn')` creates `['f','g','h','j','k','l','m','n']`. Note that the first function is continuous because it shares the constant `ints[1]` on both sides (so `f(0^-)` = `ints[1]` = `f(0^+)`).

---

### `demo-bank/outcomes/TIKZ/generator.py`

Demonstrates the TikZ image backend (the `tikz_graphics()` method) using `tkz-euclide`:

```python
class Generator(BaseGenerator):
    def data(self):
        ax, ay = randrange(0, 3), randrange(0, 3)
        bx, by = randrange(4, 7), randrange(0, 3)
        cx, cy = randrange(1, 6), randrange(4, 7)
        return {
            "ax": ax, "ay": ay,
            "bx": bx, "by": by,
            "cx": cx, "cy": cy,
        }

    @provide_data
    def tikz_graphics(data):
        ax, ay = data["ax"], data["ay"]
        bx, by = data["bx"], data["by"]
        cx, cy = data["cx"], data["cy"]
        tikz = (
            r"\begin{tikzpicture}" "\n"
            r"\tkzDefPoint(" + str(ax) + "," + str(ay) + r"){A}" "\n"
            ...
            r"\tkzDrawCircle[circum](O,A)" "\n"
            r"\tkzDrawPolygon(A,B,C)" "\n"
            ...
            r"\end{tikzpicture}"
        )
        return {"triangle": tikz}
```

`data()` picks three random points; `tikz_graphics()` builds a TikZ picture string drawing the triangle and its circumscribed circle, returning `{"triangle": <source>}`. Unlike `graphics()` (which returns Sage plot objects), `tikz_graphics()` returns **raw LaTeX/TikZ source strings**. The wrapper writes the source to `<build_path>/<seed:04d>/triangle.tikz`, and `wrapper/tikz.py`'s `compile_tikz_for_outcome()` then compiles it to `triangle.png` (pdflatex → pdftoppm). The template references it via `<tikz-image source="assets/TIKZ/generated/{{__seed__}}/triangle">` (note: no `.png` extension — the XSLT appends it; see §5). Because this outcome relies on `tkz-euclide`, it requires a current TeX Live (see the Codespace/devcontainer notes at the end).

### `demo-bank/outcomes/CURATED/generator.py`

Demonstrates **`self.seed`** and **`bank_helpers.py`**, and exists for the case where a skill cannot be randomized algorithmically and the problems must be written by hand.

```python
import bank_helpers as bh

CURATED = [ (r"<m>7 + 0 = 7</m>", "additive identity"), ... ]   # 20 of them

class Generator(BaseGenerator):
    def data(self):
        if self.seed < len(CURATED):
            statement, prop = CURATED[self.seed]   # one per public seed
        else:
            statement, prop = choice(CURATED)      # random above
```

Seeds below `len(CURATED)` serve the hand-written problems in a fixed order; higher seeds, including the ones printed assessments draw from, choose freely. Note the demo's list holds twenty problems while the viewer now exposes `PUBLIC_SEEDS` (50), so its later public versions repeat — a real bank using this pattern would write one problem per public seed. Before `self.seed` existed this had to be faked through some other parameter, since `get_data()` only reveals `__seed__` *after* `data()` has run.

Note the `r"..."` prefixes: a LaTeX literal in a `.py` file needs a raw string, or `` in `rac` becomes a formfeed. Python emits a `SyntaxWarning` for this, but it is easy to miss.

### `demo-bank/outcomes/WORDS/generator.py`

Demonstrates **math embedded inside a generated sentence**, for word problems where the generator — not the template — decides the sentence shape, so the template cannot know where the math will fall.

```python
sentence = (f"{buyer} bought <m>{count}</m> {item}s at <m>{bh.money(unit)}</m> "
            f"each and paid an extra <m>{bh.money(extra)}</m> in tax. ...")
```

The template injects it with Mustache's **triple brace**, `{{{sentence}}}`, which does not escape. The parsed SpaTeXt therefore contains real `<m>` elements, indistinguishable from ones a template author wrote, and every output format handles it normally:

```
LaTeX    After paying \(\$6.00\) in tax, Devon spent \(\$30.00\) on eight notebooks...
HTML     After paying <span class="math inline-math" data-latex="\$6.00">...
PreTeXt  After paying <m>\$6.00</m> in tax, Devon spent <m>\$30.00</m>...
```

**This is why SpaTeXt needs no inline-delimiter support.** A generator that must serve both a web renderer and a LaTeX one emits `<m>` as the single canonical form; a consumer that wants raw LaTeX converts `<m>x</m>` to `\(x\)` on its own side.

The one rule: the emitted string must be **valid XML**. Bare `&` and `<` inside the math have to be written `&amp;` and `&lt;` — see the `XML` outcome, which exists to document exactly that.

---

## 5. Detailed Walkthrough of Every XSLT File

SpaTeXt uses three XSLT 1.0 stylesheets, and they live in exactly one place: `dashboard/checkit/static/`, used server-side by `lxml`.

> **This used to be two copies.** A second, byte-identical set lived in `viewer/src/spatext/xsl/` and ran in the browser via `XSLTProcessor`, kept in sync by hand — which meant adding a SpaTeXt element required coordinated edits in six files, and which caused the document-vs-element bug. Browsers are removing `XSLTProcessor` (Chrome stable 2026-11-17), so in August 2026 the transforms moved to build time: the dashboard renders each exercise ahead of time and the viewer reads the result. The browser copy is gone. See "Browsers are removing XSLT" for the whole migration.

### The SpaTeXt XML Vocabulary

Before explaining the stylesheets, here is the complete SpaTeXt element reference. All elements are in the namespace `https://spatext.clontz.org`.

**`<knowl mode="exercise">`** — The root element (or a nested exercise part). `mode="exercise"` on the outermost knowl signals it's an exercise (affects PreTeXt output). A knowl without `mode` renders as a theorem/block in PreTeXt.

Children of `<knowl>`:
- `<title>` — optional heading text
- `<intro>` — introductory content (paragraphs/lists) before the question(s)
- `<content>` — the question content. Present for single-part exercises.
- Nested `<knowl>` elements — for multi-part exercises. A knowl with child knowls uses them as parts and ignores `<content>`.
- `<outtro>` — the answer/solution, shown/hidden by the viewer

**`<p>`** — A paragraph. May contain text and inline elements.

**`<m>`** — Inline math. Content is raw LaTeX. `<m mode="display">` renders as display math.

**`<me>`** — Display math (shorthand for `<m mode="display">`).

**`<em>`** — Emphasis (renders bold in LaTeX, `<em>` in HTML).

**`<c>`** — Code/monospace text.

**`<q>`** — Quotation (adds `"..."` in HTML, `` ``...'' `` in LaTeX).

**`<url href="...">`** — Hyperlink. Content is the link text; if empty, the href itself is used as display text.

**`<image source="..." description="...">`** — An image. `source` is the relative path. In the viewer, a `remote` attribute is programmatically added with the base URL, making the effective `src` = `remote/source`.

**`<tikz-image source="..." description="...">`** — A TikZ-generated image (fork addition; see §12 "Image generation backends"). `source` is the relative path to the compiled figure **without** the `.png` extension (e.g., `assets/TIKZ/generated/{{__seed__}}/triangle`); the XSLT appends the appropriate suffix per output format. The three stylesheets render it differently: HTML/PreTeXt point at the compiled `<source>.png`, while LaTeX `\input{<source>.tikz}`s the original TikZ source so print/PDF needs no PNG at all. The HTML rule prefixes `src` with the element's `@remote` attribute when present.

`<tikz-image>` is wired into every rendering path the same way `<image>` is — but getting there required fixing two bugs that left it half-implemented:

1. **Dead XSLT rules (all three stylesheets, both copies):** the `stx:tikz-image` template existed, but the `parseDisplay` template — which lists exactly which inline children of a `<p>` to process — only selected `…|stx:url|stx:image`, *not* `stx:tikz-image`. In XSLT, `apply-templates` with an explicit `select` processes only the listed nodes, so a `<tikz-image>` inside a paragraph was silently skipped and its rule never fired. The element therefore rendered as nothing in **every** output (HTML, LaTeX, PreTeXt — server-side and in the viewer's export tabs). Fixed by adding `|stx:tikz-image` to the `parseDisplay` select in all six files. (Six because the stylesheets were duplicated at the time; there are three now, and this trap costs half as much as a result.)
2. **Interactive Svelte path:** `outcomeToStx` (in `utils/index.ts`) stamped `@remote` only on `image` tags, and `ParagraphNodes.svelte` dispatched only `m/me/c/em/q/image/url`, so `<tikz-image>` was dropped in the default interactive **display** mode. Fixed by extending the remote-stamping query to `"image, tikz-image"` and adding a `tikz-image` case to `ParagraphNodes.svelte` (its `src` reuses the image helper and appends `.png`).

Because `viewer.zip` is a gitignored build artifact, the viewer-side fixes only reach end users after `update_viewer.py` (or `build_docs.py`) regenerates it.

**`<glyphs font="..." latex="...">`** (added 2026-08-22) — Characters whose
screen and print forms differ *irreducibly*. mat-106's Egyptian and Babylonian
numerals are Unicode on screen but LaTeX macros in print — the characters
themselves differ, so no font wrapper bridges them and the element carries both.
`html.xsl` emits a span sized inline (not by class: this HTML is also read in the
LMS exports and the AI payload, where no site stylesheet travels with it);
`latex.xsl` prefers the `latex` attribute and otherwise maps `@font` to a
command, **falling through to plain text for an unknown font** rather than
emitting an undefined macro that would fail the whole document; `pretext.xsl`
emits the characters plainly. Reads `text()`, so it holds characters, not markup.

**`<nobreak>`** (added 2026-08-27) — Content that must not be broken across
lines. `latex.xsl` renders it `\mbox{...}`, `html.xsl` a `white-space: nowrap`
span, `pretext.xsl` passes the content through. It exists because W4's equations
are long enough that LaTeX broke them at the operators, which is wrong for a
question asking which property an equation exemplifies.

Unlike every other element here, `<nobreak>` **wraps other elements**, so all
three rules call `parseDisplay` rather than reading `text()`. Reading text nodes
would discard the `<m>` elements it exists to hold together — which is the same
bug it was introduced to fix, and the reason `<m>` itself must never wrap
anything (see "The `<m>` wrapper a converted generator leaves behind").

> **Where the line is.** An element earns a place in SpaTeXt if it asserts
> something about *meaning* that each medium honours differently — "these
> characters are Egyptian", "these belong together". It does not if it asserts
> something about *appearance* — `<pagebreak>`, `<vspace>`. Appearance belongs to
> a print theme; see "Print-specific appearance, without a second source of
> truth".

**`<list>`** — An unordered list.

**`<item>`** — A list item inside `<list>`. May contain `<p>` and nested `<list>`.

---

**Adding an element touches four files, and three of them fail silently.**
The three stylesheets and `viewer/src/spatext/NodeList/ParagraphNodes.svelte`,
which builds DOM from SpaTeXt directly and never sees the XSLT. In each
stylesheet it is *two* edits: the rule, and naming the element in the
`parseDisplay` select. `apply-templates` with an explicit `select` processes
only what is listed, so a rule that is never selected renders nothing, in every
format, without an error — see the `tikz-image` post-mortem above. `test_subset.py`
asserts both halves for `<glyphs>` and `<nobreak>`; copy that pattern.

Because `viewer.zip` is a gitignored build artifact, the viewer half only
reaches users after `update_viewer.py` regenerates it, and a bank only sees a
new element after the platform version carrying it is installed — the "kill
undefined elements" rule drops an unknown element *and its contents*.

---

### `html.xsl`

**Output method:** HTML

**Root template (`match="/"`):** Wraps all output in `<div class="stx">`.

**`match="*"` (kill rule):** Any element not matched by a more specific rule is silently dropped. This means unknown elements in the input are ignored rather than causing errors.

**`match="text()"` (whitespace normalization):** Uses the trick `translate(normalize-space(concat('&#x7F;', ., '&#x7F;')), '&#x7F;', '')` to normalize interior whitespace while preserving a single leading/trailing space if the original text had one. The DEL character (U+007F) acts as a sentinel.

**`match="stx:knowl"`:**
```
<div class="stx-knowl">
  [title if present]
  [intro if present]
  [if has child knowls: <ol><li> each child knowl </li></ol>
   else: <div class="stx-content">...</div>]
  [outtro if present]
</div>
```

**`match="stx:title"`:** `<h3 class="stx-title">` with inline content (text, `<m>`, `<q>`, `<c>`).

**`match="stx:intro"`:** `<div class="stx-intro">` containing `<p>` and `<list>` children.

**`match="stx:content"`:**
- If inside a parent `<knowl>`: `<div class="stx-content">` with only `<p>` and `<list>` children
- At top level: also allows nested `<knowl>` children
This distinction prevents double-nesting of knowls.

**`match="stx:outtro"`:** `<div class="stx-outtro">` containing `<p>` and `<list>` children.

**`match="stx:list"`:** `<ul class="stx-list">` with `<li>` for each `<item>`.

**`match="stx:p"`:** `<p>` element, calling the named `parseDisplay` template for inline content.

**`parseDisplay` template:** Applies templates to all inline children: text nodes, `<m>`, `<me>`, `<q>`, `<c>`, `<em>`, `<url>`, `<image>`, `<tikz-image>`. This explicit `select` list is the gatekeeper for inline rendering — an inline element rule only fires if the element is named here (see the `<tikz-image>` note in the SpaTeXt vocabulary above).

**`match="stx:m"`:**
```html
<span class="math inline-math" data-latex="<normalized text>">
  \(<normalized text>\)
</span>
```
The `data-latex` attribute stores the raw LaTeX for programmatic re-processing (e.g., by `parseMath()` in the viewer utilities). The `\(` and `\)` delimiters are the visible fallback text.

**`match="stx:m[@mode='display']|stx:me"`:**
```html
<span class="math display-math" data-latex="<normalized text>">
  \[<normalized text>\]
</span>
```

**`match="stx:em"`:** `<em>` with inline content.

**`match="stx:c"`:** `<code>` with normalized text.

**`match="stx:q"`:** `"` + inline content + `"`.

**`match="stx:image"`:**
```html
<img src="<remote>/<source>" alt="<description>"/>
```

**`match="stx:tikz-image"`:**
```html
<img src="<remote>/<source>.png" alt="<description>"/>
```
Same as `stx:image` but appends `.png` to `source` (the template stores the path without an extension).

**`match="stx:url[@href]"`:** If the element has text content, renders `<a href="...">text</a>`. If empty, renders `<a href="...">href value</a>`.

---

### `latex.xsl`

**Output method:** text (plain string output)

**Root template:** Emits a LaTeX preamble block that defines `\stxKnowl`, `\stxOuttro`, and `\stxTitle` commands, then a line `\renewcommand{\stxOuttro}[1]{}` that hides answers by default (instructor can comment this line out to show answers):
```latex
%%%%% SpaTeXt Commands %%%%%
\providecommand{\stxKnowl}{}\renewcommand{\stxKnowl}[1]{#1}
\providecommand{\stxOuttro}{}\renewcommand{\stxOuttro}[1]{#1}
\providecommand{\stxTitle}{}\renewcommand{\stxTitle}[1]{#1}
% Comment next line to show outtros
\renewcommand{\stxOuttro}[1]{}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%
```

**`match="stx:knowl"`:**
```latex
\stxKnowl{
[title if present]
[intro if present]
[if has child knowls: \begin{enumerate} \item [each child] \end{enumerate}
 else: [content]]
[outtro wrapped in \stxOuttro{...}]
}
```

**`match="stx:title"`:** `\stxTitle{inline content}\n\n`

**`match="stx:outtro"`:** `\stxOuttro{\n[paragraphs]\n}`

**`match="stx:list"`:** `\begin{itemize}\n\item [each item]\n\end{itemize}`

**`match="stx:p"`:** inline content followed by two newlines (blank line = paragraph break in LaTeX)

**`match="stx:m"`:** `\(normalized text\)`

**`match="stx:m[@mode='display']|stx:me"`:** `\[normalized text\]`

**`match="stx:em"`:** `\textbf{content}` (bold, not italic, is the LaTeX equivalent)

**`match="stx:c"`:** `\texttt{normalized text}`

**`match="stx:q"`:** ` ``content'' ` (LaTeX opening and closing quotes)

**`match="stx:image"`:** `\includegraphics{source_attribute}`

**`match="stx:tikz-image"`:** `\input{<source>.tikz}` — pulls in the original TikZ source rather than a rasterized PNG, so the figure is typeset natively at print quality. (This is why a low `image_seeds` cap never breaks print/PDF output: it needs no PNG.)

**`match="stx:url[@href]"`:**
- Has text: `\href{href}{content}`
- Empty: `\url{href}`

---

### `pretext.xsl`

**Output method:** XML (indented)

**Root template:** Wraps output in `<pretext>`.

**`match="stx:knowl"`:**
- If nested inside another knowl: calls `knowl-content` template (bare content, no wrapping element)
- If `mode="exercise"`: `<exercise>` wrapping
- Otherwise: `<theorem>` wrapping

**Named template `knowl-content`:**
- Applies `<title>` → PreTeXt `<title>`
- Applies `<intro>` → `<introduction>`
- If has child knowls: `<task>` wrapping each child in its own `<task>`
- Otherwise: `<statement>` containing `<content>`
- Applies `<outtro>`:
  - If inside an exercise (`ancestor::stx:knowl[@mode='exercise']`): `<answer>`
  - Otherwise: `<conclusion>`

**`match="stx:intro"`:** `<introduction>` with `<p>` and `<list>` children.

**`match="stx:content"`:** Like HTML — inside a knowl renders only `<p>` and `<list>`; at top level also allows `<knowl>`.

**`match="stx:m"`:** `<m>normalized text</m>` — PreTeXt math element.

**`match="stx:m[@mode='display']|stx:me"`:** `<me>normalized text</me>`

**`match="stx:em"`:** `<em>` (PreTeXt uses same tag)

**`match="stx:c"`:** `<c>` (PreTeXt code element)

**`match="stx:q"`:** `<q>` (PreTeXt quote element)

**`match="stx:image"`:** `<image source="..." description="..."/>`

**`match="stx:tikz-image"`:** `<image source="<source>.png" description="..."/>` — like `stx:image` but appends `.png` to `source`.

**`match="stx:url[@href]"`:** `<url href="...">content</url>`

---

## 6. Detailed Walkthrough of the Svelte/TypeScript Viewer

### Technology Stack

- **Svelte 3.49** — component framework with reactive `$:` declarations
- **TypeScript 4.5** — compiled via `svelte-preprocess`
- **Vite 2.9** — dev server and build tool; in dev mode uses custom HMR port 443 (for GitHub Codespaces proxy)
- **svelte-spa-router 3.2** — hash-based client-side routing (URLs like `#/bank/EX1/1/`)
- **sveltestrap 5.9** — Bootstrap 5 components wrapped for Svelte
- **Bootstrap 5.1.3** — CSS framework
- **KaTeX 0.15.6** — fast client-side LaTeX math rendering
- **Mustache 4.2** — Mustache template rendering
- **jszip 3.10** — ZIP file creation in the browser (for LMS export)
- **file-saver 2.0.5** — triggers file download in the browser
- **svelte-dragdroplist** — drag-and-drop list component for the assessment builder

### Entry Point: `index.html` and `main.ts`

`index.html` is the HTML shell. It contains:
```html
<div id="app"></div>
<script>
  bankJsonUrl = './assets/bank.json';
</script>
<script type="module" src="/src/main.ts"></script>
```

The `bankJsonUrl` global variable tells the app where to fetch the bank data. This is set as a plain global (no `var`/`let`/`const`) so it can be overridden by whoever deploys the viewer.

`main.ts` mounts the `App` Svelte component onto `#app`.

### `App.svelte`

The root component.

- Imports Bootstrap CSS and KaTeX CSS globally
- On mount (`onMount`), fetches `window['bankJsonUrl']` (the injected URL), parses JSON, and writes the result to the `bank` store
- Renders `<Nav/>` unless the URL querystring is `"embed"` (for iframe embedding)
- Renders `<CodeCell/>` always (it manages its own visibility)
- While loading: shows a spinner with "Loading ☑️It..."
- After loading: renders `<Router {routes}/>` and a footer with version number

### TypeScript Types (`types.ts`)

```typescript
type Bank = {
    title: string;
    url: string;
    slug: string;
    generated_on: string;
    outcomes: Array<Outcome>;
}
type Outcome = {
    title: string;
    slug: string;
    description: string;
    template: string;      // raw SpaTeXt XML with Mustache placeholders
    exercises: Array<Exercise>;
}
type Exercise = {
    seed: number;
    data: Object;          // arbitrary key/value pairs from the generator
}
type Params = {
    outcomeSlug: string;
    exerciseVersion: string;  // "1"-based version string from URL
}
type Assessment = {
    exercises: AssessmentExercise[]
    latex: string
}
```

### Svelte Stores

Three reactive stores manage global state:

**`stores/banks.ts`:**
```typescript
export const bank = writable<Bank>(undefined);
```
The entire loaded bank, set once in `App.svelte` after fetching. All components read from this.

**`stores/codecell.ts`:**
```typescript
export const isOpen = writable<Boolean>(false);
```
Whether the CodeCell iframe is visible. Toggled by `toggleCodeCell()`.

**`stores/instructor.ts`:**
```typescript
export const instructorEnabled = writable<boolean>(false);
export const assessmentOutcomeSlugs = writable<string[]>([]);
```
Both are persisted to `localStorage` (keyed by `location.pathname + "#instructorEnabled"` etc.) and restored on page load. This means if you enable instructor mode on a specific bank, it stays enabled on your next visit. The `assessmentOutcomeSlugs` array remembers which outcomes you've added to your assessment in progress.

### Routing (`routes/index.ts`)

Uses hash routing — the URL path for routing is the part after `#`:

| URL pattern | Component | Description |
|---|---|---|
| `#/` | Home.svelte | Immediately redirects to `#/bank/` |
| `#/bank/` | Bank.svelte | Bank home page |
| `#/bank/:outcomeSlug/` | OutcomeRedirect.svelte | Redirects to `#/bank/:outcomeSlug/1/` |
| `#/bank/:outcomeSlug/:exerciseVersion/` | Outcome.svelte | Exercise viewer |
| `#/assessment/` | Assessment.svelte | Assessment builder |
| `#/export/` | Export.svelte | LMS export |
| `*` | NotFound.svelte | 404 |

### Core Utilities (`utils/index.ts`)

**`outcomeToStxDocument(outcome, seed)`** and **`outcomeToStx(outcome, seed)`**
Converts an outcome + seed index to SpaTeXt — as a **Document** and as its root **Element** respectively.
1. Calls `Mustache.render(outcome.template, outcome.exercises[seed]['data'])` — renders the Mustache template with the exercise data
2. If Mustache fails, substitutes a knowl with an error message
3. Parses the resulting XML string via `DOMParser`
4. If XML parsing fails (e.g., malformed XML from bad generator output), substitutes an error knowl
5. Finds all `<image>` and `<tikz-image>` elements (`querySelectorAll("image, tikz-image")`) and sets their `remote` attribute to the current page's origin + pathname (so relative image paths work correctly when the viewer is served from a subdirectory)
6. `outcomeToStxDocument` returns the Document; `outcomeToStx` returns its `documentElement`

> **Which one to call, and why it matters.** Anything feeding `XSLTProcessor` must pass the **Document**; only the Svelte display path (`Knowl.svelte`, which walks an Element) takes the Element.
>
> All three stylesheets emit their wrapper from `<xsl:template match="/">`, and `/` matches the *document node*. Hand `transformToDocument()` an Element and that template never fires, so the wrapper is never emitted. Measured in Firefox:
>
> ```
> source = document -> <div class="stx">ROOT<div class="stx-knowl">…</div></div>
> source = element  -> <div class="stx-knowl">…</div>          (no wrapper)
> ```
>
> Chrome resolves an element source to its owner document and matches `/` anyway, so this was invisible there for years while being broken in Firefox. The symptom was `outcomeToHtml()`'s wrapper lookup returning null and `.outerHTML` throwing "can't access property outerHTML, l is null", which took down every caller — and, because the throw happened while *building* the payload, presented as a clipboard bug in the "Copy for AI Chatbot" button.

**`outcomeToHtml(outcome, seed, mathMode, solutions)`**
1. Calls `outcomeToStxDocument` to get the SpaTeXt document
2. Creates an `XSLTProcessor`, loads `html.xsl`, transforms the document
3. If `mathMode == 'canvas'` or `'brightspace'`: renders all `[data-latex]` spans using KaTeX with MathML output (for LMS compatibility where KaTeX CSS may not be loaded)
4. If `solutions == 'hide'`: removes all `.stx-outtro` elements
5. If `solutions == 'only'`: removes `.stx-intro` and `.stx-content` elements
6. Returns the outer HTML string

**`outcomeToLatex(outcome, seed)`**
Uses `XSLTProcessor` with `latex.xsl` to produce a LaTeX string for the exercise.

**`outcomeToPtx(outcome, seed)`**
Uses `XSLTProcessor` with `pretext.xsl` to produce a PreTeXt XML string.

**`parseMath(html)`**
Takes an HTML string containing `\(inline\)` and `\[display\]` math delimiters and replaces them with fully rendered KaTeX HTML using regex substitution. Used for re-rendering exported HTML content.

**`decodeXmlString(s)`**
Decodes `&apos;`, `&quot;`, `&gt;`, `&lt;`, `&amp;` XML entities. Used before passing strings to KaTeX (which expects raw LaTeX, not XML-escaped LaTeX).

**`getOutcomeFromSlug(bank, slug)`**
Simple array find: `bank.outcomes.find(o => o.slug === slug)`.

**`sample(array)`**
Picks a uniformly random element from an array.

**`getRandomAssessmentFromSlugs(bank, slugs)`**
Builds an `Assessment` object:
1. For each slug, finds the outcome and picks a random seed from `[PUBLIC_SEEDS, exercises.length)` (skipping the publicly visible versions, so a student cannot look up the printed one)
2. Generates LaTeX for each exercise and concatenates with `\newpage` between them
3. Renders the full `assessmentTemplate.tex` using Mustache with a `version` (timestamp) and an `exercises` array
4. Returns `{exercises: [...], latex: "full document LaTeX string"}`

### Route Components

**`Bank.svelte`** — Layout wrapper, not a standalone route. Accepts `params` prop. Shows the bank title, an outcome dropdown, and (if no specific outcome) the bank URL and generation date. Used as a slot wrapper by `Outcome.svelte`.

**`Outcome.svelte`** — The main exercise viewer.
- Finds the outcome from `params.outcomeSlug`
- Converts `params.exerciseVersion` (1-based string) to a 0-based `seed` index via `versionStringToInt`
- Version selector: a `<select>` bound to `seed`, with `«` and `»` buttons, clamped to [0,19]
- When `seed` changes, pushes a new URL so the browser history is updated
- Shows outcome description
- If instructor mode: shows `+`/`-` buttons for including this outcome in the assessment, with a count
- Renders `<Exercise {outcome} {seed}/>`

**`Exercise.svelte`** — Renders one exercise in the selected mode.
- Modes: `display`, `edit`, `embed`, `html`, `latex`, `pretext`
- Mode tabs only shown in instructor mode and when not embedded
- `display` mode: renders `<Knowl knowl={outcomeToStx(outcome, seed)}/>` — the full Svelte component tree
- `edit` mode: two columns — left has editable `<textarea>` bound to `outcome.template` and a readonly JSON textarea showing the data; right shows the live rendered exercise (reflects edits in real time)
- `html` mode: `<textarea readonly>` with the raw HTML string
- `latex` mode: `<textarea readonly>` with the LaTeX string
- `pretext` mode: `<textarea readonly>` with the PreTeXt XML
- `embed` mode: `<textarea readonly>` with an iframe HTML snippet pointing to the current URL + `?embed`

**`Assessment.svelte`** — Assessment builder.
- Forces `instructorEnabled = true` on mount
- Left column: outcome dropdown to add outcomes, with a sortable/removable list (via `<Sorter>`)
- Right column: "Generate" button → calls `getRandomAssessmentFromSlugs`; "Export" dropdown → Overleaf or clipboard
- After generating: shows LaTeX source textarea and a preview of all exercises using `<Exercise statementOnly>`
- `openInOverleaf()`: submits a POST form to `https://www.overleaf.com/docs` with the LaTeX in the `snip` field

**`Export.svelte`** — LMS export.
- Selects outcomes via a multi-select list
- Selects LMS: Canvas / D2L Brightspace / Moodle
- For Canvas: selects question type (essay / file upload / true-false)
- On "Export": generates 900 exercises per outcome (seeds 100–999), renders question HTML and answer HTML using `outcomeToHtml` with appropriate math mode and solutions filter, fills in LMS-specific XML templates, packages into a ZIP or single XML file, and saves to disk via FileSaver

The LMS templates use Mustache. The generated files follow IMS QTI standards understood by each LMS.

### SpaTeXt Component Tree

The Svelte components under `spatext/` provide a rich interactive rendering of SpaTeXt XML that the static HTML + KaTeX path cannot match (specifically the show/hide answer toggle).

**`Knowl.svelte`** — The central component.

Receives a DOM `Element` object with tag `knowl`.

Determines context:
- `isInExercise(p)` — recursively checks if a knowl ancestor has `mode="exercise"`. If yes, outtro is labeled "answer", parts are labeled "Task", and the whole block is labeled "Exercise". If no, uses generic labels.
- `isTopKnowl` — true if this knowl has no knowl parent. Top-level knowls get a black-bordered box; nested knowls are unstyled.
- `numbering(p)` — recursively computes a hierarchical number like "1.2" based on a knowl's position among its siblings. Returns `""` for top-level knowls.

Renders:
- If numbered: `<h5>Task 1.2.</h5>` (or Exercise/Part depending on context)
- If top-level: `<h3>Exercise.</h3>` (or `Exercise: <title>` if there's a title)
- `<div class:top-knowl={isTopKnowl}>` containing:
  - `<KnowlContent content=intro/>` if intro exists
  - If has `<content>` children: `<KnowlContent content=content/>`
  - If has child `<knowl>` elements: `<ol>` with `<li class="sub-knowl">` for each, each containing a recursive `<svelte:self knowl={subKnowl}/>`
  - If has `<outtro>`: a "▶ Show answer" toggle link; if `showOuttro=true`, also shows `<KnowlContent content=outtro/>`

**`KnowlContent.svelte`** — Thin wrapper: calls `<ContentNodes nodes={content.childNodes} allowKnowls={false}/>`.

**`ContentNodes.svelte`** — Dispatches block-level nodes:
- `<p>` → `<Paragraph>`
- `<list>` → `<List>`
- `<knowl>` → `<Knowl>` (only if `allowKnowls=true`)
- Other element types: ignored
- Non-element nodes: ignored

**`Paragraph.svelte`** — `<p><ParagraphNodes nodes={paragraph.childNodes}/></p>`

**`ParagraphNodes.svelte`** — Dispatches inline nodes:
- Text node → raw text content
- `<m>` → `<Math latex displayMode={mode=="display"}>`
- `<me>` → `<Math latex displayMode>`
- `<c>` → `<code>`
- `<em>` → `<em>` containing recursive `<svelte:self>`
- `<q>` → `"` + recursive `<svelte:self>` + `"`
- `<image>` → `<img style="max-width:100%" src={...} alt={...}>`. The `src` is computed as `remote + "/" + source` if a `remote` attribute exists, otherwise just `source`.
- `<tikz-image>` → same as `<image>`, but the `src` helper appends `.png` (the template stores the figure path without an extension). Mirrors the `stx:tikz-image` HTML XSLT rule so the interactive display and the html export tab agree.
- `<url>` → `<a href={...}>`. If text content is empty, shows the href; otherwise shows `<svelte:self nodes={child nodes}>`.
- Other elements: ignored

**`Math.svelte`** — One-liner: `{@html katex.renderToString(latex, {throwOnError:false, displayMode})}`. The `throwOnError:false` option means invalid LaTeX shows a red error message inline rather than throwing.

**`List.svelte`** — `<ul>` with `<li>` for each `<item>`. Uses `<ContentNodes>` for each item's children.

**`Title.svelte`** — `<TitleNodes nodes={title.childNodes}/>`.

**`TitleNodes.svelte`** — Like ParagraphNodes but only handles text, `<m>`, `<c>`, `<em>`, `<q>` (not `<image>`, `<url>`, `<me>`).

### Nav Component

`Nav.svelte` renders a Bootstrap navbar (dark blue, primary color):
- Brand link "☑️It" → checkit.clontz.org
- "Bank Home" link → `#/bank/`
- "Code Cell" link → calls `toggleCodeCell()`
- Instructor checkbox → clicking toggles `$instructorEnabled`
- If instructor mode: "LMS Export" and "Assessment Builder" links (shown/hidden responsively for small screens)

### CodeCell Component

A dismissible `<div role="alert">` containing an `<iframe>` pointing to `https://checkit.clontz.org/codecell/`. This provides a small SageMath/Jupyter code cell embedded in the viewer, useful for students who want to verify computations. The iframe is only added to the DOM after `loaded` becomes true (triggered by `isOpen` becoming true), to avoid loading it unnecessarily.

### Sorter Component

Wraps `svelte-dragdroplist`. Receives an `array` prop and a `display` function. Converts the array to the dragdroplist format (`{text, item, id}`), exposes drag-and-drop reordering, and optionally shows ×-remove buttons. The `array` binding is two-way — sorting in the UI updates the parent's array.

---

## 7. Data Flow: `python -m checkit generate`

Here is the complete step-by-step trace of everything that happens when you run `python -m checkit generate` from inside a bank directory.

### Step 1: CLI invocation

Python runs `dashboard/checkit/__main__.py`. Click parses `generate` as the subcommand. Default options: `amount=1000`, `regenerate=False`, `images=False`, `outcome="ALL"`.

### Step 2: `Bank()` construction

```python
b = bank.Bank()
```

`Bank.__init__(path=".")`:
- `self._abspath = os.path.abspath(".")` — e.g., `/home/user/my-bank`
- Reads `/home/user/my-bank/bank.xml` with lxml
- Checks `version="0.2"`
- Reads `<title>`, `<slug>`, `<url>`
- For each `<outcome>` element in the XML:
  - Creates `Outcome(title, slug, path, description, bank_ref)`
  - Calls `o.load_exercises(strict=False)` — tries to read existing `assets/<slug>/generated/seeds.json`. If it exists, populates `_exercises`. If not, does nothing.

At this point, `b._outcomes` is a list of `Outcome` objects, some possibly with existing exercises loaded, some without.

### Step 3: Filtering (if applicable)

If `outcome != "ALL"`:
```python
b._outcomes = [o for o in b._outcomes if o.slug.lower() == outcome.lower()]
```

### Step 4: `generate_exercises`

```python
b.generate_exercises(regenerate=False, images=False, amount=1000)
```

Iterates each outcome, prints `"Generating 1000 exercises for outcome <slug>"`, then calls `o.generate_exercises(regenerate=False, images=False, amount=1000)`.

**Inside `Outcome.generate_exercises`:**

Since `regenerate=False`, tries `self.load_exercises()`. If `_exercises` already exists (set during `Bank.__init__`), returns immediately — generation is skipped. If exercises don't exist:
```python
sage(self, self.seeds_json_path(), preview=False, images=False, amount=1000)
```

**Inside `wrapper/__init__.py`'s `sage()`:**

1. Computes `amount_s = "1000"`, `random_s = "no"`
2. Gets the path to `wrapper.sage` via `importlib.resources.path("checkit.wrapper", "wrapper.sage")`
3. Picks the runtime from the generator's extension (`RUNTIMES`), and copies the matching wrapper (`wrapper.py` here) to a temp directory
4. Uses `working_directory(outcome.bank.abspath())` to change to the bank root
5. Runs:
   ```
   <sys.executable> /tmp/xxx/wrapper.py /home/user/my-bank/outcomes/EX1/generator.py
        /home/user/my-bank/assets/EX1/generated/seeds.json 1000 no
   ```
   (a `generator.sage` would instead run `sage /tmp/xxx/wrapper.sage ...`)

### Step 5: Generator execution

The wrapper runs. The script:

1. Reads `sys.argv`:
   - `generator_path = "outcomes/EX1/generator.py"` (relative to bank root, since we cd'd there)
   - `seeds_path = "/home/user/my-bank/assets/EX1/generated/seeds.json"`
   - `amount = 1000`
   - `random = False`
   - `gen_images = False`

2. Calls `load_generator("outcomes/EX1/generator.py")` — appends the generator's folder and the bank root to `sys.path` (so `import bank_helpers` works), then executes the generator file in a namespace built from `GENERATOR_NAMESPACE`, which supplies `BaseGenerator`, `CheckIt`, `provide_data` and the math names. (`wrapper.sage` instead uses Sage's `load()`, since Sage puts those names in scope for free.)

3. Creates `generator = Generator()`.

4. Loops `i` from `0` to `999`:
   - `seed_int = i`
   - `generator.roll_data(seed=i)` → calls `set_random_seed(i)`, then `self.data()`
   - `self.data()` runs the generator's logic (e.g., calls `randrange`, `var`, etc.)
   - `generator.get_data()` returns `{...all data keys..., "__seed__": "0000"}`
   - `json_ready(data)` walks the dict recursively:
     - For Sage objects (like `3*x + 2*y`): `str(latex(obj))` → `"3 x + 2 y"`
     - For strings/bools: pass through unchanged
     - For lists/dicts: recurse
   - Appends `{"seed": 0, "data": {"slope": "3 x", "__seed__": "0000", ...}}` to `seeds`

5. Writes to `seeds.json`:
   ```json
   {
     "seeds": [
       {"seed": 0, "data": {"slope": "3", "equation": "3 x + 5 y = 7", "__seed__": "0000"}},
       {"seed": 1, "data": {"slope": "-2", "equation": "x - 2 y = 4", "__seed__": "0001"}},
       ...
     ],
     "generated_on": "2024-01-15T14:23:45.123456+00:00"
   }
   ```

### Step 6: Loading exercises back

After `sage()` returns, `load_exercises(reload=True)` reads the JSON file and creates `Exercise` objects:
```python
self._exercises = [Exercise(d["data"], d["seed"], self) for d in seed_list]
```

### Step 7: `write_json`

```python
b.write_json()
```

Calls `b.to_dict()`, which calls `o.to_dict()` for each outcome, which:
- Reads `self.template()` (the raw XML string)
- Returns `{"title": ..., "slug": ..., "description": ..., "template": "<xml>...", "exercises": [{"seed":0,"data":{...}}, ...]}`

The final `bank.json` looks like:
```json
{
  "title": "Demo Bank",
  "slug": "demo-bank",
  "url": "https://checkit.clontz.org",
  "generated_on": "2024-01-15T14:23:45+00:00",
  "outcomes": [
    {
      "title": "Line Slopes",
      "slug": "EX1",
      "description": "Identify the slope...",
      "template": "<?xml version='1.0' encoding='UTF-8'?>\n<knowl mode=\"exercise\" ...",
      "exercises": [
        {"seed": 0, "data": {"lines": [...], "alt_prompt": "False", "__seed__": "0000"}},
        ...
      ]
    },
    ...
  ]
}
```

This file is written to `assets/bank.json`.

### Step 8 (optional): `checkit viewer`

Running `python -m checkit viewer` calls `bank.Bank().build_viewer()`:
1. Deletes and recreates `docs/`
2. Extracts `viewer.zip` into `docs/` — this gives `docs/index.html`, `docs/assets/index.js`, etc.
3. Copies `assets/` (containing `bank.json` and any generated images) to `docs/assets/`

The user can now open `docs/index.html` locally, or serve `docs/` as a static website.

**`docs/` is a committed build artifact, and nothing regenerates it at deploy
time.** Publishing is therefore two commands, and forgetting the second is
silent — `generate` writes `assets/`, only `viewer` copies it into `docs/`.

**"Generated on" in the viewer is trustworthy; trust it.** `Bank.svelte` renders
`bank.json`'s `generated_on`, stamped by `to_dict()` at `write_json()` time. If
the published site shows an old date, the published site *is* old — it is not a
stamping bug. In August 2026 the date read five days stale because commit
`602d5a9` had committed an already-built tree rather than rebuilding: `git show
--stat` showed it as pure renames (`docs/assets/G1/*` → `R1/*`, `Bin` with no
byte changes) plus files whose mtimes predated the commit by five days. The
commit date is not the content date.

Cheap way to tell them apart before rebuilding anything:

```
git log -1 --format=%cd -- docs/assets/bank.json   # when it was committed
python -c "import json;print(json.load(open('docs/assets/bank.json'))['generated_on'])"
```

---

## 8. The Bank Format

A bank is a directory with the following structure:

```
my-bank/
├── bank.xml
├── outcomes/
│   ├── SLUG1/
│   │   ├── generator.py
│   │   └── template.xml
│   └── SLUG2/
│       ├── generator.py
│       └── template.xml
└── assets/          (created by `checkit generate`)
    ├── bank.json
    └── SLUG1/
        └── generated/
            └── seeds.json
```

Optionally, manually-created assets can live in `assets/` (e.g., pre-made images for `IMG2`-style outcomes).

### `bank.xml`

Full example:
```xml
<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>My Exercise Bank</title>
    <slug>my-exercise-bank</slug>
    <url>https://example.com/my-bank</url>
    <outcomes>
        <outcome>
            <title>Line Slopes</title>
            <slug>EX1</slug>
            <path>outcomes/EX1</path>
            <description>
Identify the slope of a line from its equation.
            </description>
        </outcome>
        <outcome>
            <title>Derivatives</title>
            <slug>EX2</slug>
            <path>outcomes/EX2</path>
            <description>
Apply differentiation rules.
            </description>
        </outcome>
    </outcomes>
</bank>
```

Required attributes and elements:
- `xmlns="https://checkit.clontz.org"` — the CheckIt namespace
- `version="0.2"` — must be exactly this string
- `<title>` — displayed in the viewer header
- `<slug>` — used in URLs and file naming (no spaces)
- `<url>` — the bank's home URL (shown on the bank home page)
- Each `<outcome>`:
  - `<title>` — displayed in the viewer
  - `<slug>` — unique identifier used in URLs and `assets/<slug>/` directory naming
  - `<path>` — path relative to the bank root pointing to the outcome directory
  - `<description>` — shown on the outcome page

Alongside `bank.xml`, a bank may hold **`bank_helpers.py`** at its root — shared functions any generator can `import bank_helpers`. Scaffolded by `checkit new`; see "Generator runtimes" for how it is put on the import path.

Optional elements:
- `<ai-prompt>` — free prose prepended to the payload of the viewer's "Copy for AI Chatbot" button (see §12). Valid at bank level and inside any `<outcome>`; the outcome's value wins, then the bank's, then a generic built-in default. Parsed by `xml.optional_text()`, which dedents and strips, so the body can be indented to match the surrounding XML or not.

The `<path>` element allows arbitrary directory organization. The demo bank uses `outcomes/EX/EX1` (nested), while the boilerplate uses `outcomes/EX1` (flat).

**On adding optional elements:** use `xml.optional_text()` rather than `.find(...).text`. Banks authored against an older CheckIt won't have the element, and `.find()` returns `None` — so the required-element style (`ele.find(...).text`) raises `AttributeError` and refuses to open the bank at all. Every optional element must degrade to `None` and let the consumer fall back.

### `generator.py` (or `generator.sage`)

The file extension selects the runtime: `generator.py` runs under plain Python + SymPy, `generator.sage` under SageMath. `.py` is the default and the one `checkit new` scaffolds.

Every generator file must define a `Generator` class that extends `BaseGenerator`. The minimum viable generator:

```python
class Generator(BaseGenerator):
    def data(self):
        return {
            "x": randrange(-9, 10),
            "y": randrange(-9, 10),
        }
```

The `data()` method is called with the random seed already set via `set_random_seed(n)`. It must return a Python dict whose values are either:
- Strings (passed through as-is)
- Booleans (passed through as-is; used for Mustache conditional sections)
- SageMath symbolic expressions (converted to LaTeX strings by `json_ready`)
- Python integers/floats (also converted via `str(latex(n))`)
- Lists of any of the above (recursively processed)
- Dicts of any of the above (recursively processed)

The `data()` method must **not** store any state — it is called fresh for each seed and must be a pure function of the random state.

The generator also has access to:
- `CheckIt` — the helper class (see Section 9)
- All SageMath globals: `var`, `randrange`, `choice`, `shuffle`, `matrix`, `QQ`, `ZZ`, `SR`, `latex`, `plot`, etc.
- `provide_data` — decorator for the `graphics()` method

Optional graphics method:
```python
@provide_data
def graphics(data):
    return {
        "filename_without_extension": sage_graphics_object,
    }
```

When `checkit generate -i` is run, this returns a dict of filenames to Sage plot objects. Each is saved as `assets/<slug>/generated/<seed:04d>/<filename>.png`. Templates can then reference them as `assets/<slug>/generated/{{__seed__}}/filename.png`.

### `template.xml`

A template is a valid SpaTeXt XML document where Mustache `{{variable}}` placeholders have been added inside element text content. The root element must be `<knowl>` in the SpaTeXt namespace.

Full example (the EX2 product rule template):
```xml
<?xml version='1.0' encoding='UTF-8'?>
<knowl mode="exercise" xmlns="https://spatext.clontz.org" version="0.2">
    <content>
        <p>
Explain how to find the {{d_synonym}} <m>f'(x)</m>.
        </p>
        <p>
            <m mode="display">
f(x)={{f}}
            </m>
        </p>
    </content>
    <outtro>
        <p>
            <m mode="display">
f'(x)={{dfdx}}
            </m>
        </p>
    </outtro>
</knowl>
```

Mustache features used in templates:
- `{{variable}}` — simple substitution (value must be a string or LaTeX)
- `{{#boolean}}...{{/boolean}}` — conditional block rendered only if the value is truthy
- `{{^boolean}}...{{/boolean}}` — inverted conditional (rendered only if falsy)
- `{{#list}}...{{/list}}` — iterates over a list; inside the block, `{{key}}` refers to keys in each list item's dict
- `<!-- {{#variable}} -->` — Mustache sections inside XML comments (to prevent the template from being invalid XML before rendering)
- `{{__seed__}}` — special key injected by `BaseGenerator.get_data()` for image paths

**Critical constraint:** After Mustache rendering, the resulting string must be valid XML. This means:
- LaTeX strings containing `<`, `>`, `&` must use XML entities: `&lt;`, `&gt;`, `&amp;`
- The EX3 template demonstrates this with `\begin{cases}{{left}} &amp; x \leq 0`

### Complete Working Example

Here is a minimal but complete bank that generates "add two fractions" problems:

**`bank.xml`:**
```xml
<?xml version='1.0' encoding='UTF-8'?>
<bank xmlns="https://checkit.clontz.org" version="0.2">
    <title>Fractions Bank</title>
    <slug>fractions-bank</slug>
    <url>https://example.com</url>
    <outcomes>
        <outcome>
            <title>Add Fractions</title>
            <slug>FR1</slug>
            <path>outcomes/FR1</path>
            <description>Add two fractions with different denominators.</description>
        </outcome>
    </outcomes>
</bank>
```

**`outcomes/FR1/generator.py`:**
```python
class Generator(BaseGenerator):
    def data(self):
        from math import gcd
        a = randrange(1, 8)
        b = randrange(2, 9)
        c = randrange(1, 8)
        d = b
        while d == b:
            d = randrange(2, 9)
        # answer: a/b + c/d = (a*d + c*b) / (b*d)
        num = a*d + c*b
        den = b*d
        g = gcd(num, den)
        return {
            "a": a, "b": b, "c": c, "d": d,
            "num": num // g, "den": den // g,
        }
```

Note: `a`, `b`, etc. are plain Python integers, so `json_ready()` will call `str(latex(a))` which gives `"3"`, `"7"`, etc.

**`outcomes/FR1/template.xml`:**
```xml
<?xml version='1.0' encoding='UTF-8'?>
<knowl mode="exercise" xmlns="https://spatext.clontz.org" version="0.2">
    <content>
        <p>
Compute <m>\dfrac{{{a}}}{{{b}}} + \dfrac{{{c}}}{{{d}}}</m>.
        </p>
    </content>
    <outtro>
        <p>
            <m>\dfrac{{{num}}}{{{den}}}</m>
        </p>
    </outtro>
</knowl>
```

Note the triple braces `{{{a}}}` — Mustache uses `{{{...}}}` for unescaped HTML output. Since the values are just numbers, `{{a}}` and `{{{a}}}` produce the same result here, but it's good practice for math content where `{{a}}` would HTML-escape LaTeX special characters.

---

## 9. The CheckIt SageMath Module

The `CheckIt` class is available to all generator authors without any import. Here is complete documentation of every method with examples.

> **This class now exists in both runtimes** — here for `wrapper.sage`, and re-implemented against SymPy in `wrapper/wrapper.py`. The public method names and signatures are identical on purpose; a change to one belongs in both. See "Generator runtimes" near the end of this document.
>
> Note `vars()`'s name-shuffling is **not** a Sage workaround: SymPy orders the terms of a sum by symbol name too, so the helper is needed in both. By contrast `var("zw", latex_name="w")` *was* Sage-specific and is gone — SymPy has no display-name override, and the helper that used it takes an explicitly ordered list anyway.

### `CheckIt.vars(*latex_names, random_order=True)`

**What it does:** Creates Sage symbolic variables that display as the given LaTeX names, but whose internal order in algebraic expressions is randomized.

**Why it's needed:** In Sage, `x + y` always displays as `x + y` if `x` was created before `y`. Using random internal names makes expressions like `3a - 2b` appear as `3a - 2b` for some seeds and `-2b + 3a` for others, preventing students from always recognizing the same pattern.

**Usage:**
```python
x, y, z = CheckIt.vars("x", "y", "z")
# Now x, y, z display as x, y, z in LaTeX
# But their internal Sage ordering is shuffled, so expressions look different each seed
```

**Return:** A Python generator of Sage variables (use tuple unpacking).

### `CheckIt.shuffled_equation(*terms)`

**What it does:** Creates a Sage equation equivalent to `sum(terms) = 0` where each term is randomly assigned to the left or right side, and the whole equation is possibly negated.

**Usage:**
```python
x, y, z = CheckIt.vars("x", "y", "z")
eq = CheckIt.shuffled_equation(3*x, -2*y, 5)
# Could produce: 3x = 2y - 5, or -5 + 2y = 3x, or 3x - 2y + 5 = 0, etc.
```

**Return:** A Sage symbolic equation.

### `CheckIt.shuffled_inequality(*terms, strict=True)`

**What it does:** Creates a Sage inequality equivalent to `sum(terms) > 0` (strict) or `>= 0` (non-strict), with random side assignment and random direction.

**Usage:**
```python
x, y = CheckIt.vars("x", "y")
ineq = CheckIt.shuffled_inequality(2*x, -3*y, 1)
# Could produce: 2x > 3y - 1, or -1 + 3y <= 2x, etc.
```

**Return:** A Sage symbolic inequality.

### `CheckIt.latex_system_from_matrix(matrix, variables="x", alpha_mode=False, variable_list=None)`

**What it does:** Converts a Sage augmented matrix into a LaTeX string representing the corresponding system of equations, with proper `+`/`-` signs and alignment.

**Parameters:**
- `matrix` — a Sage matrix. Should be subdivided (with column subdivision) to mark where the augmentation bar is. If not subdivided, a zero-vector augmentation is added.
- `variables="x"` — base name for fallback variables (produces `x_1, x_2, ...`)
- `alpha_mode=False` — if True, uses `x, y, z, w, v` instead of subscripted names
- `variable_list=None` — explicit list of Sage variables (highest priority)

**Usage:**
```python
A = matrix([[2, 3, 5], [1, -1, 2]])
A.subdivide([], [2])  # augment after column 2
system = CheckIt.latex_system_from_matrix(A, alpha_mode=True)
# Returns "\begin{matrix}\n2 x & + & 3 y & = & 5\\\\ \nx & - & y & = & 2\\\\\n\end{matrix}"
```

**Return:** A raw LaTeX string (already a string, not a Sage object — `json_ready` will not call `latex()` on it).

### `CheckIt.latex_solution_set_from_matrix(matrix)`

**What it does:** Solves an augmented linear system and returns a LaTeX set-builder expression for its solution set.

**Usage:**
```python
A = matrix([[1, 2, 3, 4], [0, 0, 1, 2]])
A.subdivide([], [3])
sol = CheckIt.latex_solution_set_from_matrix(A)
# Returns something like: \left\{ \begin{pmatrix} ... \end{pmatrix} \,\middle|\, a \in\mathbb R \right\}
```

**Return:** A raw LaTeX string.

**Edge case:** Returns `\{\}` for inconsistent systems.

### `CheckIt.simple_random_matrix_of_rank(rank, rows=1, columns=1, augmented=False)`

**What it does:** Generates a random matrix with the given rank, with integer entries bounded by 6, designed to have "nice" pedagogical properties.

**Parameters:**
- `rank` — the desired rank (number of pivot columns)
- `rows` — total number of rows (must be >= rank)
- `columns` — total number of columns (must be >= rank)
- `augmented` — if True, subdivides the last column as an augmentation column

**Usage:**
```python
A = CheckIt.simple_random_matrix_of_rank(2, rows=3, columns=4, augmented=True)
# A 3x4 augmented matrix with rank 2, entries in [-5,5]
```

**Return:** A Sage matrix with integer entries.

**Notes:**
- The algorithm ensures the matrix has exactly the requested rank (not accidentally higher/lower)
- Pedagogically it often makes the last column dependent (50% probability when `extra_columns > 0`), which is good for teaching inconsistency detection
- Integer RREF is guaranteed, which avoids ugly fractions in the original matrix

### Helper: `provide_data`

Not a class method but a module-level decorator. Applied to `graphics()` to receive the `data` dict directly:

```python
@provide_data
def graphics(data):
    # data is the dict returned by self.data() plus {"__seed__": "NNNN"}
    return {"plot": plot(data["f"])}
```

Without the decorator, the method signature would be `def graphics(self)` and you'd have to call `self.get_data()` manually.

---

## 10. Configuration and Entry Points

### CLI Setup

The CLI is defined in `__main__.py` using Click. The package is configured in `setup.cfg` with:
```
[options.entry_points]
console_scripts =
    checkit = checkit.__main__:main
```
(This entry point is implicit via Click's `__main__` detection — when you `pip install checkit-dashboard`, you get a `checkit` command that runs `checkit.__main__:main`.)

Running `python -m checkit` also works because `__main__.py` is the module's `__main__` file.

### All Available Commands

**`checkit new [DIRECTORY]`**
```
Options: none
Argument: DIRECTORY (default: new-checkit-bank)
Effect: Creates boilerplate bank directory structure
Code: __main__.py:new()
```

**`checkit generate`**
```
Options:
  -a / --amount INTEGER    Number of exercises to generate (default: 1000)
  -r / --regenerate        Force regeneration even if seeds.json exists
  -i / --images            Also generate PNG image files
  -o / --outcome TEXT      Specific outcome slug to generate (default: ALL)
Effect: Runs each outcome's generator, writes assets/bank.json.
        Plain Python by default; SageMath only for a generator.sage.
Code: __main__.py:generate() -> bank.Bank.generate_exercises() ->
      outcome.Outcome.generate_exercises() -> wrapper/__init__.py:sage() ->
      subprocess running wrapper/wrapper.sage
```

**`checkit viewer`**
```
Options: none
Effect: Extracts viewer.zip into docs/, copies assets/ to docs/assets/
Code: __main__.py:viewer() -> bank.Bank.build_viewer()
```

**`checkit check`**
```
Options: --generators/--no-generators   run every generator in-process
         --built/--no-built             check the built bank.json and bundles
Effect: Structural checks; exits non-zero on findings. See "Checking a build".
Code: __main__.py:check() -> checks.run_all() and smoke.run_generators()
```

**`checkit tui`**
```
Effect: Opens an interactive terminal UI for the above commands
Code: Provided by trogon; no custom code needed beyond @tui() decorator
```

### Bank.json Location

The generated `bank.json` always goes to `assets/bank.json` relative to the bank root. After running `checkit viewer`, it's copied to `docs/assets/bank.json`.

### Index.html Injection

The viewer's `index.html` has:
```html
<script>
  bankJsonUrl = './assets/bank.json';
</script>
```
This global variable is read in `App.svelte` as `window['bankJsonUrl']`. When deploying the viewer in non-standard ways, you can change this URL to point to a different location.

---

## 11. Dependencies

### Python Dependencies (`setup.cfg`)

> **SageMath is deliberately absent from this list, and always has been.** It cannot be pip-installed. As of 2026-08-04 it is also no longer needed: the default runtime is plain Python + SymPy, and `sage` is invoked only for a `generator.sage`. See "Generator runtimes" near the end of this document.

**`sympy`** — the default generator runtime's math backend. Used by `wrapper/wrapper.py` for symbolic expressions, `latex()` output and exact matrix work. Added to `install_requires` 2026-08-04.

**`matplotlib`** — an *optional extra* (`pip install checkit-dashboard[plots]`), deliberately not in `install_requires`: only banks whose generators call `plot()` need it, and `tikz_graphics()` needs no Python plotting library at all. `plot()` raises a clear message when it is missing.

**`ipywidgets`** — Jupyter widget framework. Used only in `dashboard.py` (deprecated). Provides `widgets.Output`, `widgets.Dropdown`, `widgets.Button`, `widgets.HBox`, etc.

**`lxml`** — XML parsing and XSLT processing. Used in `bank.py` (parse bank.xml), `exercise.py` (parse/serialize SpaTeXt, run XSLT transforms). `lxml.etree.XSLT` is a fast libxslt wrapper.

**`latex2mathml`** — Converts LaTeX math strings to MathML XML. Imported in `exercise.py` for the `tex_to_mathml()` helper function. Currently unused in the main code paths (the browser renders math client-side with KaTeX), but available for server-side MathML generation.

**`pystache`** — Python implementation of the Mustache templating language. Used in `exercise.py`'s `Exercise.spatext_ele()` to render `template.xml` with exercise data.

**`click`** — CLI framework. Used in `__main__.py` for command parsing, argument handling, and help text generation.

**`trogon`** — Adds an interactive TUI to any click app via the `@tui()` decorator. Running `checkit tui` opens it.

**Dev extras (`dev`):** `build`, `twine` (for PyPI publishing), `ipykernel` (for Jupyter support).

**System dependency (not in pypi):** SageMath must be installed and the `sage` command must be available in PATH. This is not specified in `setup.cfg` because it's not a pip-installable package.

### JavaScript Dependencies (`viewer/package.json`)

**`bootstrap 5.1.3`** — CSS framework providing grid layout, buttons, navbar, forms, alerts, etc.

**`file-saver 2.0.5`** — `FileSaver.saveAs(blob, filename)` to trigger browser file downloads. Used in `Export.svelte`.

**`jszip 3.10.0`** — Creates ZIP files in the browser. Used in `Export.svelte` to package Canvas/Brightspace export files.

**`katex 0.15.6`** — Fast LaTeX math rendering in the browser. Used in `Math.svelte` (`katex.renderToString()`), in `utils/index.ts` (`katex.render()` for LMS export, `katex.renderToString()` in `parseMath()`).

**`mustache 4.2.0`** — Client-side Mustache rendering. Used in `utils/index.ts` to render SpaTeXt from template + data, and to fill LMS export templates and the assessment PDF template.

**`svelte-dragdroplist 1.1.1`** — Drag-and-drop list component. Used in `Sorter.svelte` for the assessment outcome ordering.

**`svelte-spa-router 3.2.0`** — Hash-based SPA router for Svelte. Provides `Router`, `push`, `querystring`.

**`sveltestrap 5.9.0`** — Bootstrap 5 components wrapped as Svelte components (`Container`, `Row`, `Col`, `Button`, `Nav`, `Navbar`, etc.).

**Dev dependencies:** `@sveltejs/vite-plugin-svelte`, `svelte`, `svelte-check`, `svelte-preprocess`, `tslib`, `typescript`, `vite`.

---

## 12. How to Make Common Modifications

### Changing Output Formats

The output formats are defined entirely by the three XSLT stylesheets, and since August 2026 there is **one copy** of each, in `dashboard/checkit/static/`.

To change how a SpaTeXt element renders in HTML:
1. Locate the `<xsl:template match="stx:element_name">` rule in `html.xsl`
2. Modify it
3. Run `python -m unittest discover -s dashboard/tests -t dashboard/tests`
4. Regenerate any bank you want to see the change in — the viewer reads
   precomputed output, so an edit to a stylesheet does nothing until
   `checkit generate` runs again

Note step 4 is new and easy to forget: the browser no longer transforms
anything, so stylesheet edits reach a published site only through regeneration.

To add a new SpaTeXt element (e.g., `<stx:alert>`):
1. Add `<xsl:template match="stx:alert">` to all three stylesheets (html, latex, pretext) in both locations
2. For the interactive Svelte rendering, add handling in `ParagraphNodes.svelte` or `ContentNodes.svelte` depending on whether it's inline or block-level
3. Rebuild the viewer

### Adding a New CLI Command

1. Open `dashboard/checkit/__main__.py`
2. Add a new function decorated with `@main.command(...)` and `@click.option(...)` as needed. Example:
```python
@main.command(short_help="validate bank structure")
def validate():
    """Check that all generator and template files are well-formed."""
    b = bank.Bank()
    for o in b.outcomes():
        # validation logic...
        print(f"OK: {o.slug}")
```
3. The function is automatically discoverable by click as a subcommand
4. No other wiring is needed — `checkit validate` will work immediately after install

### Creating a Visual Editing and PDF Document Generating Frontend via Python Frameworks and/or Godot

**Python web framework approach (e.g., FastAPI or Flask):**

The most direct approach uses the existing `Bank`, `Outcome`, and `Exercise` classes:
- `Bank()` reads the bank from disk
- `Exercise.spatext_ele()` renders any `(outcome, seed)` pair to SpaTeXt
- `Exercise.html()` renders to HTML
- `Exercise.latex()` renders to LaTeX
- `Exercise.pretext()` renders to PreTeXt

A FastAPI server could expose endpoints like `GET /bank/{slug}/{seed}/html` returning the HTML for one exercise, and a PDF generation endpoint that calls `Exercise.latex()` for selected exercises, wraps them in the assessment template from `viewer/src/templates/assessmentTemplate.tex`, and invokes `pdflatex` or `latexmk`.

Key files to look at:
- `dashboard/checkit/bank.py` — `Bank` and its `to_dict()` method
- `dashboard/checkit/outcome.py` — `Outcome.exercises()` to get the exercise list
- `dashboard/checkit/exercise.py` — `Exercise.latex()` for PDF content
- `viewer/src/templates/assessmentTemplate.tex` — the LaTeX document template to wrap exercises in

**Godot approach:**

Godot can render HTML via its `WebBrowser` node (or an HTTPRequest node fetching from a local server). The workflow would be:
1. Run the FastAPI server locally
2. Use Godot's `HTTPRequest` node to fetch `bank.json`
3. Parse JSON with Godot's built-in JSON class
4. For each outcome/seed, fetch the rendered HTML from the FastAPI server
5. Display it in a `RichTextLabel` or a custom web view
For PDF generation, have Godot send a request to a FastAPI endpoint that generates the PDF server-side and returns it as bytes.

### Changing How Exercises Are Rendered

**In the viewer (browser rendering):**
The Svelte component chain is:
`Outcome.svelte` → `Exercise.svelte` → `Knowl.svelte` → `KnowlContent.svelte` → `ContentNodes.svelte` → `Paragraph.svelte`/`List.svelte` → `ParagraphNodes.svelte` → `Math.svelte`

To change how math is rendered, modify `Math.svelte`. To change the show/hide answer behavior, modify `Knowl.svelte`. To change how paragraphs are rendered, modify `Paragraph.svelte` and `ParagraphNodes.svelte`.

**In the static HTML output (lxml rendering):**
Modify `dashboard/checkit/static/html.xsl` and rebuild `viewer.zip` with `update_viewer.py`.

**In the assessment PDF:**
Modify `viewer/src/templates/assessmentTemplate.tex`. The template uses Mustache. The `{{{latex}}}` placeholder is each exercise's LaTeX output (note triple braces for unescaped HTML, which in Mustache also bypasses HTML escaping — necessary here since LaTeX contains characters like `\`, `{`, `}`).

### Letting a bank declare its own LaTeX preamble (not implemented)

> **Read "The split worth committing to" first.** That section places this
> question: a bank declaring \usepackage{...} is stating a
> *dependency* -- its content does not compile without \textpmhg --
> not choosing a style, which is why it belongs to the bank rather than to a
> print theme. What follows is the mechanics of getting it there, which are
> the hard part.

Wanted because `assessmentTemplate.tex` is currently the *platform's* file, identical for every bank, so a bank's LaTeX package requirements (e.g. `tkz-euclide`) have to be hardcoded into it for everyone. Worth understanding why this is a project rather than a one-liner:

`utils/index.ts` pulls the template in with `import assessmentTemplate from '../templates/assessmentTemplate.tex?raw'`. Vite's `?raw` resolves at **build time** — the file's text is inlined into the JS bundle as a string literal (the same way the three XSLTs are; you can find them verbatim inside `viewer.zip`'s `index.*.js`). The bundle is then zipped into the installed Python package and extracted into every bank by `Bank.build_viewer()`. So there is no `.tex` file at runtime for any bank to override, and downstream authors — who `pip install checkit-dashboard` and get a prebuilt `viewer.zip` — have no way to customize it at all.

The only per-bank channel into the running viewer is `assets/bank.json`, fetched at runtime by `App.svelte`. So a bank-declared preamble has to travel that path:

1. Bank author writes e.g. `latex_packages.tex` in the bank root
2. `bank.py`'s `to_dict()` reads it into a new key
3. it lands in `assets/bank.json` via `write_json()`
4. the viewer already loads `bank.json` — no change
5. `getRandomAssessmentFromSlugs(bank, slugs)` already receives the whole bank, so it just passes the value into the Mustache render
6. `assessmentTemplate.tex` grows a `{{{latex_preamble}}}` placeholder in its preamble

Open questions before building it: `bank.json` becomes a compatibility surface (banks generated by an older CheckIt won't have the key, and the viewer must not crash); and a bank that forgets the file silently reverts to the missing-package failure this was meant to fix, so the absent case needs designing rather than defaulting. Note `tikz_preamble.tex` (used by `tikz.py`) can't be reused directly — it's a full `standalone` document class, not an `article`-compatible package block.

### Adding a New Helper to the CheckIt Module

All helpers live in `dashboard/checkit/wrapper/wrapper.sage` inside the `CheckIt` class. To add a new helper:

1. Add a `@staticmethod` method to the `CheckIt` class:
```python
@staticmethod
def my_new_helper(param1, param2):
    """Documentation for generator authors."""
    # SageMath code here
    return result
```
2. No import is needed — `CheckIt` is already in scope when generators run
3. Document it in your bank's README

Since `wrapper.sage` is loaded by `importlib.resources` at runtime, changes to it take effect immediately after modifying the file (no rebuild needed, unless you've distributed the package via pip — then a `pip install -e .` reinstall is needed).

### Making Exercise Versions Viewable by AI Helper Chatbots

**These are two different goals and they need different solutions. Don't conflate them.**

| | who is reading | sees the SPA's rendered DOM? |
|---|---|---|
| **A. Student shares an exercise with a chatbot** | browser assistant, or a chat window they paste into | yes — assistants read the rendered page, after JS |
| **B. Crawler discoverability** | GPTBot, ClaudeBot, Googlebot | no — they fetch the URL and never run JS |

Only **B** is blocked by the "SPA serves an empty shell" problem. The three options below address B. They do nothing for A, because a browser assistant already sees everything the student sees.

#### Goal A — implemented: the "Copy for AI Chatbot" button

A student-facing button on the outcome page (`routes/Outcome.svelte`) copies the currently-viewed exercise to the clipboard, built by `outcomeToAiText(bank, outcome, seed)` in `utils/index.ts`. The payload is: the bank author's prompt header, identifying context (slug, title, learning outcome, version, source URL), then the exercise **including its answer**, rendered as HTML.

Three decisions worth preserving:

- **HTML, not LaTeX.** `outcomeToHtml()` goes through `outcomeToStx()`, which stamps `@remote` with the page's absolute origin + path, so every `<img src>` is a fully-qualified public URL a chatbot can fetch to *see* the figure. The LaTeX output emits bank-relative `\includegraphics` / `\input{...tikz}` paths instead, which mean nothing off the authoring machine. HTML also leaves math as raw `\( \)` LaTeX rather than rendered KaTeX spans, which is more legible to a model, not less.
- **Answers are included, deliberately.** This is a tutoring aid, not an assessment surface. Note the contrast with the *display* path: `Knowl.svelte` uses `{#if showOuttro}` (a conditional render, not CSS hiding), so a browser assistant reading the page does *not* see the answer until the student reveals it. The button is the explicit, opt-in channel for handing it over.
- **The prompt header is bank-authored**, via `<ai-prompt>` in `bank.xml` at bank or outcome level (§8). This is the first use of the "bank declares something the viewer needs" channel — the same mechanism the bank-declared LaTeX preamble would use.

- **The clipboard write can be refused, and must not fail silently.** `navigator.clipboard.writeText()` rejects with `NotAllowedError` in some browsers and permission states even on a secure origin inside a click handler — observed on the published site, where the first version of this button did nothing at all and logged nothing. `Outcome.svelte` now shows the payload in a readonly textarea (focused and pre-selected) when the write is refused.

  **`document.execCommand('copy')` is not a usable fallback here, and was deliberately removed after being tried.** On the published site, with `writeText` denied, `execCommand('copy')` still returned `true` *and* fired a `copy` event carrying a populated `clipboardData` — while writing nothing to the clipboard. Its success is indistinguishable from its failure, so relying on it silently re-creates the "looks like it worked" bug this branch exists to prevent. **`writeText()` resolving is the only trustworthy signal**, since per spec it resolves only after the clipboard is actually written.

- **The copy state resets when the student changes outcome or version** (routing is hash-based and never reloads the page, so a stale "Copy blocked" textarea holding the *previous* exercise would otherwise follow them onward). The reset body must stay in a function rather than being inlined into the `$:` block: inline, `clearTimeout(copyTimer)` reads `copyTimer`, making it a dependency of the block — and `copyForAi`'s own `copyTimer = setTimeout(...)` then re-triggers the block, resetting `copyState` to `'idle'` in the same flush that set it to `'copied'`. The confirmation never renders. This bit once, and cost a deploy cycle to find, because it is invisible in the source.

Known limits, both inherent rather than bugs: the image URLs only resolve when the bank is **published** (from a local preview they point at `localhost`), and whether a given chatbot actually fetches a pasted URL is up to that chatbot. The button makes vision possible, not guaranteed.

A related cheap win for goal A: image `description` attributes become the `alt` text, so a *data-driven* description (IMG1's `"Line with intercept {{intercept}} and slope {{slope}}"`) is far more useful to a model — and to a screen reader — than a static one (TIKZ's `"A triangle with its circumscribed circle"`, which omits the coordinates that make the figure specific).

#### Goal B — crawler discoverability (not implemented)

**Option 1: Add a static HTML export command.**
Add a `checkit export-html` CLI command that, for each outcome and each of the first N seeds, calls `Exercise.html()` and writes the result to `docs/bank/<slug>/<seed>.html`. Also write a `docs/bank/index.html` with links to all pages. This creates a crawlable site.

Files to modify:
- `dashboard/checkit/__main__.py` — add the command
- `dashboard/checkit/bank.py` — add a method like `export_static_html()`
- `dashboard/checkit/exercise.py` — `Exercise.html()` is already available

**Option 2: Use server-side rendering.**
Deploy the bank with a Python server that accepts `GET /bank/<slug>/<seed>` and returns fully rendered HTML (using `Exercise.html()` + the KaTeX CSS) with no JavaScript required. **Note this abandons static hosting** — a bank currently deploys as files on GitHub Pages with no server anywhere, and Option 2 requires one to be running for the bank to be readable at all. That's a change to the project's deployment model, not just an added feature. Option 1 achieves the same crawlability while staying static.

**Option 3: Add a JSON-LD metadata file.**
Generate a `docs/exercises.jsonld` with exercise content in schema.org `Quiz` format. AI systems that understand structured data can consume this directly.

### Image generation backends (Sage, TikZ, and future PreFigure)

CheckIt's image step supports multiple backends. Two are implemented:

- **Sage graphics** — generators define a `graphics()` method returning `{name: <sage plot object>}`; wrapper.sage saves each as `<name>.png`.
- **TikZ** — generators define a `tikz_graphics()` method returning `{name: <tikz source string>}`; wrapper.sage writes each as `<name>.tikz`, then `tikz.py`'s `compile_tikz_for_outcome()` compiles them to PNG via pdflatex + pdftoppm (PDF kept only in a temp dir, discarded after).

The two backends are gated differently, and the asymmetry is deliberate:

| | written by | gated by `--images`? | gated by `--image-seeds`? |
|---|---|---|---|
| `graphics()` → `.png` | wrapper.sage | yes | yes |
| `tikz_graphics()` → `.tikz` | wrapper.sage | **no** | **no** |
| `.tikz` → `.png` | tikz.py | yes | yes |

Sage graphics rasterize immediately, and PNGs are only consumed by the HTML/viewer surfaces, so both gates apply. TikZ splits into a cheap text step and an expensive raster step: the LaTeX output `\input{}`s the `.tikz` source directly, so print needs it for every seed and it is written unconditionally; only the rasterization is capped. A PreFigure backend would follow the TikZ shape if its source is text, the Sage shape if it rasterizes directly.

PreFigure (a Python library for generating mathematical figures as SVG/PNGs from XML descriptions) could replace Sage's `plot()` for image generation. The integration point is the `graphics()` method in generators and the image-saving loop in `wrapper.sage`.

Current image generation in `wrapper.sage` (after implementing TikZ but not PreFigure):
```python
        directory = os.path.dirname(seeds_path)
        seed_path = os.path.join(directory, f"{seed_int:04}")
        # ungated: cheap text, and print needs it for every seed
        tikz = generator.tikz_graphics()
        if tikz is not None:
            os.makedirs(seed_path, exist_ok=True)
            for name, source in tikz.items():
                with open(os.path.join(seed_path, f"{name}.tikz"), "w") as f:
                    f.write(source)
        # gated: rasterizing is the expensive half
        if gen_images and i < image_amount:
            graphics = generator.graphics()
            if graphics is not None:
                os.makedirs(seed_path, exist_ok=True)
                for filename in graphics:
                    graphics[filename].save(os.path.join(seed_path, f"{filename}.png"))
```

The `graphics[filename]` object is currently a Sage graphics object with a `.save(path)` method. To support PreFigure:
1. Have `graphics()` return PreFigure diagram objects instead of Sage plot objects
2. In `wrapper.sage`, detect the type and call the appropriate save method
3. Or: have `graphics()` always return objects with a `.save(path)` method — if you make PreFigure diagrams have that interface (or wrap them), no change to `wrapper.sage` is needed.

The `generator_path` loaded by `wrapper.sage` runs in the SageMath namespace, so PreFigure would need to be importable from within SageMath's Python environment. Since SageMath uses conda, install it with `conda install prefigure` or `pip install prefigure` in the sage conda env.

### Limiting image rendering with `image_seeds` (--image-seeds)

`generate --image-seeds N` **rasterizes** images for only the first N seeds of each outcome, while still generating full seed *data* for all of them. Threaded through Bank.generate_exercises → Outcome.generate_exercises → sage() → wrapper.sage (as sys.argv[6]) **and → compile_tikz_for_outcome()**, and per-outcome (N applies to each outcome independently, not N total across the bank). Default (None) renders all.

**The cap applies to PNGs only.** `wrapper.sage` writes a `.tikz` file for *every* seed, ungated by both `--images` and `--image-seeds`, because the LaTeX output `\input{}`s that source directly and print has to work for every seed. `--image-seeds` then limits how many of those get rasterized by `tikz.py`. (Before this was split, one gate covered both, so a low cap silently produced *no* `.tikz` file for the uncapped seeds and LaTeX assessments drawing on them failed with a missing-file error — while the note below claimed print was immune.)

Intended for fast local previews. Consumer exposure to un-rasterized seeds:
- Viewer: caps at `PUBLIC_SEEDS` (50), so image_seeds >= 50 keeps it clean.
- Print/PDF: uses the .tikz source via \input{}, needs no PNG at all — and since the source is now always written, a low cap genuinely cannot break print.
- LMS export: uses seeds 100–999, so a low image_seeds value produces broken   images if a TikZ outcome is exported. Use the full count for LMS-bound banks.

### Changing How Banks Are Structured

The bank structure is read in `bank.py`'s `Bank.__init__`:
```python
xml = etree.parse(os.path.join(self.abspath(), "bank.xml")).getroot()
if xml.get("version") != "0.2":
    raise Exception(...)
self.title = xml.find(f"{CHECKIT_NS}title").text
self.slug = xml.find(f"{CHECKIT_NS}slug").text
self.url = xml.find(f"{CHECKIT_NS}url").text
self._outcomes = [
    Outcome(
        ele.find(f"{CHECKIT_NS}title").text,
        ele.find(f"{CHECKIT_NS}slug").text,
        ele.find(f"{CHECKIT_NS}path").text,
        ele.find(f"{CHECKIT_NS}description").text,
        self,
    )
    for ele in xml.find(f"{CHECKIT_NS}outcomes").iter(f"{CHECKIT_NS}outcome")
]
```

To add a new field to `bank.xml` (e.g., `<version>1.0</version>` for the bank's own version):
1. Add the XML element to your `bank.xml`
2. Read it in `Bank.__init__`: `self.bank_version = xml.find(f"{CHECKIT_NS}version").text`
3. Include it in `Bank.to_dict()` so it appears in `bank.json`
4. Add it to the `Bank` TypeScript type in `viewer/src/types.ts`
5. Use it wherever needed in the viewer

To change the outcome structure (e.g., add tags):
1. Add `<tags>...</tags>` to each outcome in `bank.xml`
2. Read it in the `Outcome` constructor list comprehension in `Bank.__init__`
3. Pass the new field through `Outcome.__init__`
4. Include it in `Outcome.to_dict()`
5. Add to TypeScript `Outcome` type
6. Display it in the viewer

To change the `seeds.json` format (e.g., add metadata per exercise):
- `wrapper.sage` writes the format: the `seed` dict is `{"seed": seed_int, "data": json_ready(data)}`
- `Outcome.load_exercises()` reads it: `Exercise(d["data"], d["seed"], self)`
- Changes must be made in both places
- The final `bank.json` format is derived from `Outcome.to_dict()` which calls `e.to_dict()` → `{"seed": self.seed, "data": self.data}`
- The viewer TypeScript type `Exercise = {seed: number; data: Object}` would also need updating

## Packaging and distribution: how a bank gets its CheckIt

A bank never contains CheckIt; it *installs* it. There are three routes, they
behave very differently, and confusing them fails quietly rather than loudly.

**Editable install** — what this repo's own `.venv` uses. A `.pth` file
(`__editable__.checkit_dashboard-*.pth`) points Python at
`dashboard/checkit/` in the working tree, so `import checkit` loads the source
directly and every edit takes effect with no reinstall. This is why platform
work here needs no build step. It only works where the source lives.

**A wheel built from a working tree** — `cd dashboard && python -m build
--wheel`. Contains everything, including `viewer.zip`, because setuptools copies
from the tree rather than from git. This is the route for anyone else.

**PyPI** — and the trap. `checkit-dashboard` on PyPI is **upstream's** package.
Version 0.2.8 there was published by Steven Clontz on 2026-08-01 and is
different code from this fork's 0.2.8. A bank pinning `checkit-dashboard ==
0.2.8` installs upstream, works, and silently lacks every change in this fork.
`checkit new` therefore writes the fork's release-wheel URL instead of a version
pin.

### viewer.zip decides which routes work

`viewer.zip` is the compiled browser app with no bank data in it: `npm run
build` produces `viewer/dist/`, `update_viewer.py` deletes the placeholder
`assets/bank.json` from a copy, zips the rest into `checkit/static/viewer.zip`,
and `Bank.build_viewer()` extracts it into a bank's `docs/` before copying that
bank's own `assets/` alongside. It exists so a bank author can publish a site
without ever installing Node.

It is a **gitignored build artifact**, and that has a consequence worth stating
plainly:

| route | ships viewer.zip? | why |
|---|---|---|
| editable install | yes | reads the working tree |
| wheel built locally | yes | setuptools copies from the tree |
| `pip install git+https://...` | **no** | pip clones the repo, where it is not tracked |

So a git URL in a bank's `requirements.txt` produces an install whose
`checkit viewer` fails on a missing resource. Distribute a wheel, not a git ref.

Committing `viewer.zip` would make git installs work, and is tempting, but the
filenames inside are content-hashed while the zip stores each file's *mtime* —
which `npm run build` rewrites every run. The bytes therefore change on every
build even when nothing meaningful did, so it would produce a stream of
meaningless 1.1 MB diffs. Making the zip deterministic would fix that; nobody
has needed to yet.

### Cutting a release

0. **If anything under `viewer/src/` changed, run `dashboard/update_viewer.py`
   first.** `viewer.zip` is gitignored, so it is not rebuilt by anything the
   release does and a stale one ships silently — the wheel would carry
   stylesheets that know a new element and a viewer that does not.
1. Bump `VERSION` in `dashboard/checkit/__init__.py` (digits and dots only).
2. `cd dashboard && python -m build --wheel` — output lands in `dashboard/dist/`
   (gitignored).
3. Install that wheel into a throwaway venv and run `checkit new`,
   `checkit generate`, `checkit viewer`, `checkit check`. This is the only way
   the packaging bugs above are visible. If the release adds a SpaTeXt element,
   assert it is actually in the installed stylesheets *and* in `viewer.zip`'s
   bundled JS — the two travel separately and only one of them is tracked by
   git.
4. Commit and **push** — a release tags whatever `origin/main` is at publish
   time, so an unpushed commit silently tags the wrong code.
5. Create the release and upload the wheel. `gh release create` reported a
   misleading "workflow scope may be required" here; the REST API works:

```
gh api repos/<owner>/checkit/releases --method POST \
  -f tag_name=v<VERSION> -f target_commitish=main -f name=v<VERSION> -F draft=true -f body="..."
gh api --method POST -H "Content-Type: application/octet-stream" \
  "https://uploads.github.com/repos/<owner>/checkit/releases/<id>/assets?name=<wheel>" \
  --input dashboard/dist/<wheel>
```

6. Check the **stored** asset name matches what was uploaded, then publish with
   `gh api repos/<owner>/checkit/releases/<id> --method PATCH -F draft=false`.

7. Install once more **from the published URL** into an empty venv. This is the
   round trip that caught the `+` mangling: the wheel building and the wheel
   being downloadable are different claims.
8. Repoint each bank's `requirements.txt` at the new URL. A bank using a new
   SpaTeXt element *must* move, because the stylesheets drop an unknown element
   and its contents without erroring.

Creating it as a draft first is worth the extra step: a draft is invisible,
creates no tag until published, and can be deleted without trace — which is how
the `+` mangling was caught before anything went public.

> **`pip show` lies in a development bank.** mat-106's venv has an editable
> install pointing at the platform checkout, so `pip show checkit-dashboard`
> reports whatever version was current when it was installed and never updates.
> To see what is actually running: `python -c "import checkit;
> print(checkit.__file__, checkit.VERSION)"`.

---

## Checking a build

```
checkit check                    # generators, then the built bank
checkit check --no-built         # generators only; needs no build
checkit check --no-generators    # the built bank only
```

Exits non-zero on findings. Added 2026-08-27 (`0.2.8.4`), after the same
detectors had been written as throwaway scripts three times.

`smoke.py` execs each `generator.py` in `wrapper.GENERATOR_NAMESPACE`,
constructs `Generator()` properly, and calls `data()` across seeds either side
of both range boundaries and every declared variant. **Construct it, do not
stub it**: `BaseGenerator.__init__` sets `variant`, and `Gen.__new__(Gen)`
produces false `AttributeError: variant` failures on every outcome declaring
`variants`. This is the fastest thing available -- 29 generators in seconds,
no build -- and the only way to see a generator's real traceback while
`generate` still hides it.

`checks.py` covers what a build gets wrong *without failing*:

| check | catches |
|---|---|
| `escaped-markup` | `{{double braces}}` showing `&lt;m&gt;` to a student |
| `raw-tex` | TeX rendering as literal text |
| `control-char` | non-raw literals turning `\textpmhg` into TAB + `extpmhg` |
| `relative-img` | root-relative `<img src>`, which 404s off-site |
| `math-punctuation` | a greedy pattern italicising a full stop |
| `latex-braces` | documents that will not compile |
| `nested-in-m` | `<m>` containing elements, whose content is dropped |
| `bundle` | the same, over seeds 50-399 |

Three of these have a design point worth not undoing:

- **`raw-tex` matches single-character escapes too.** Requiring two or more
  letters after the backslash is what let `27.6\%` and `\$770.13` ship in 300
  versions while the check reported clean.
- **`nested-in-m` reads the SpaTeXt, never the HTML.** `<m>` renders with
  `normalize-space(text())` in both stylesheets, so the dropped content does
  not exist by the time there is HTML to inspect.
- **`latex-braces` deliberately does not flag `\text`, `\textbf` or `\mbox`
  inside maths.** All three are legal in math mode and all are used on purpose
  here; flagging them produced 976 findings against a correct bank, which is
  how a check teaches people to ignore it. The real bug was an unbalanced
  brace, which brace balance catches by itself.

**A clean run is not a substitute for looking at the page.** Three of these
checks were written *after* a human spot-check found what the automated checks
had passed, and one earlier check passed an outcome that was rendering "is a
multiple of" with both of its numbers missing. They catch documents that will
not compile and markup that will not render. They say nothing about whether an
exercise is right, readable, or breaks lines in a sensible place.

Run it against the *previous* build as well as the new one when investigating:
the useful output is rarely "there are findings", it is "which of these are new
today".

---

## Tests

There were none until 2026-08-21; `dashboard/tests/` had held an empty `.keep`
since the initial import.

```
python -m unittest discover -s dashboard/tests -t dashboard/tests
```

| file | covers |
|---|---|
| `spatext_fixtures.py` | hand-written SpaTeXt covering the structural cases |
| `test_subset.py` | `subset` filtering, the `Exercise` API, cross-language constants |
| `test_precompute.py` | the precompute emitter and its declared coverage |
| `test_packaging.py` | what actually ends up in an installed copy |
| `test_outcome_filter.py` | that `generate -o SLUG` narrows regeneration and nothing else |
| `test_checks.py` | that every `checkit check` detector can actually fail |
| `browser_harness.py` | manual: re-runs the stylesheet checks in a real browser |

Four choices worth knowing about:

**Stdlib `unittest`, not pytest.** The repo had no test dependency and no
runner. Adding one should not be the price of adding a first test.

**Hermetic fixtures, not `demo-bank`.** A bank's `assets/**/generated` is
gitignored, so a fresh clone has no `seeds.json`; a bank-backed test would need
a full `checkit generate` before it could run. `test_precompute.py` does build a
real `Bank`, but from temporary files it writes itself.

**Tests compare two implementations rather than checking against golden files.**
The central `subset` test performs the stylesheet's filtering *and* the viewer's
class-removal filtering and asserts they match. That needs no stored snapshot
and stays meaningful as the stylesheets change. Where two things must agree
across a boundary nothing enforces — the two `PUBLIC_SEEDS` declarations, the
two `install_requires` lists — there is a test asserting it.

**Everything here is mutation-checked.** Each guard was verified by breaking the
code it protects and confirming the suite goes red: changing the `subset`
default, dropping the outtro guard, guarding the whole `xsl:choose`, leaving
LaTeX beside the MathML, rendering display maths inline, skipping MathML
conversion, dropping the missing-`remote` check, inlining every seed, starting
the bundle at zero, adding pretext to it, dropping the coverage declaration,
leaving stale bundles, removing `sympy` again, and filtering the Bank
instead of the regeneration pass. A guard that cannot fail is
decoration, and this codebase has been bitten enough times by silent success to
be worth the extra step.

The browser harness is the exception to all of this: it is run by hand, it needs
a real browser, and it **expires**. It drives a real `XSLTProcessor`, which
Chrome removes in 158 on 2026-11-17. Its value has already dropped now that the
viewer does not transform anything — it only cross-checks the Python `subset`
implementation against a real XSLT engine. It was never run in Firefox, which is
the engine that has actually surprised this project before.

---

## Browsers are removing XSLT (hard deadline, ~Nov 2026)

**This is a dated architectural risk, not a hypothetical.** Firefox already prints
`XSLT will be removed from this web browser soon` to the console when the viewer
runs a transform (observed 2026-07-29 on the published demo).

Status: removal of XSLT from the web platform reached **stage 3** at WHATWG
(whatwg/html#11523), meaning broad cross-engine agreement. It is not one vendor's
decision — Chromium proposed it, Mozilla's standards position is *positive*
(mozilla/standards-positions#1287), and WebKit has also signalled intent. The
rationale is security (libxslt and friends are aging C/C++ with a long history of
memory-safety bugs) plus very low remaining usage.

Chrome's published schedule:

| Chrome | date | effect |
|---|---|---|
| 146 | 2026-03-10 | Enterprise Policy escape hatch available |
| 152 | 2026-08-25 | Origin Trial available |
| **158** | **2026-11-17** | **XSLT stops working on stable for everyone else** |
| 176 | 2027-08-17 | Origin Trial + Enterprise Policy end; off for all |

Re-verified against Chrome's deprecation page on 2026-08-20: all four dates
above are current. Three earlier milestones are already past — 142
(2025-10-28) added console warnings, 143 (2025-12-02) was the formal
deprecation, and 145 disabled XSLT in Canary/Dev/Beta. Chrome puts remaining
usage at ~0.02% of page loads, which is why no amount of objection is likely to
move the date.

### What this breaks in CheckIt

Everything that calls `XSLTProcessor` in `viewer/src/utils/index.ts` —
`outcomeToLatex()`, `outcomeToHtml()`, `outcomeToPtx()` — and therefore:

- `Exercise.svelte`'s Raw HTML / LaTeX / PreTeXt instructor tabs
- `Export.svelte`'s Canvas, Brightspace and Moodle exports
- `Assessment.svelte`'s generated assessment LaTeX (via `outcomeToLatex`)
- `Outcome.svelte`'s "Copy for AI Chatbot" button (via `outcomeToHtml`)

**What does *not* break:** the default student-facing display path. `Knowl.svelte`
→ `ContentNodes` → `ParagraphNodes` render SpaTeXt directly from the DOM;
`outcomeToStx()` uses `DOMParser`, not `XSLTProcessor`. Students browsing
exercises are unaffected. So does the whole Python/dashboard side, which
transforms with `lxml` server-side and is entirely outside the browser.

That containment is structural rather than incidental, which is worth knowing
before anyone "tidies" `Exercise.svelte`. The XSLT calls sit inside
`{:else if mode == "html"}` branches, so Svelte never evaluates them while
`mode == "display"`; and the tabs that change `mode` render only under
`{#if $instructorEnabled}`. A student cannot reach a throwing transform even by
accident. Hoisting any of those calls into a `$:` statement or a shared variable
would destroy that guarantee and take the student view down with it.

### Status

**All three steps are complete as of 2026-08-21.** `Exercise` produces
everything the viewer produces (filtered subsets, MathML for the LMS, absolute
image URLs), `generate` emits the precomputed formats, and the viewer reads them
instead of transforming. The migration write-ups — the measurements, the option
comparison, and the two implementation steps — are in Appendix A; what stays
here is the deadline itself, what step 1 landed, and the questions still open.

Still open: whether MathML is the right target for Canvas at all, and Firefox,
which has never been exercised. Both below.

What landed:

- `<xsl:param name="subset" select="'all'"/>` in `html.xsl`, with the three
  `apply-templates` calls in the `stx:knowl` template guarded. Nested knowls
  re-enter that template, so one guard filters every depth, matching the
  viewer's global `querySelectorAll` removal.
- `consumer` was deliberately **not** declared. Declaring a parameter nothing
  reads is exactly what produced the original four-year-old bug. It arrives
  with the MathML work.
- `Exercise.html_ele()` validates `subset` and raises on any `consumer` other
  than `'basic'`. `Exercise.pretext_ele()` raises on either non-default value
  instead of accepting and discarding them: nothing asks PreTeXt for a subset
  (`outcomeToPtx()` takes none), and dropping `<statement>` from a PreTeXt
  `<exercise>` would emit structurally invalid PreTeXt, so that wants designing
  against a real consumer rather than guessing.
- `latex.xsl` is untouched. `Exercise.latex()` accepts no `subset` and
  `outcomeToLatex()` does not filter, so there was nothing to reach parity with
  at the time.

  **That is now the gap.** `latex.xsl` hides answers by unconditionally emitting
  `\renewcommand{\stxOuttro}[1]{}` with a comment telling a human to delete the
  line — the same decision `subset` expresses as a parameter in `html.xsl`, done
  a second way in a second file. The print tool needs answer keys, so it needs
  this settled; see "What is missing, concretely" under the print tool.

Then the other two halves:

- **The MathML consumer.** `consumer='canvas'` or `'brightspace'` converts every
  math span's contents to MathML, mirroring what the viewer does with KaTeX
  after its transform. Done as a **Python pass over the result tree, not an
  `xsl:param`** — an XSLT extension function would make `html.xsl` unable to run
  standalone in a browser, permanently forking the two copies in order to fix a
  duplication problem. `consumer` therefore never reaches the stylesheet, and
  `subset` remains the only XSLT parameter.

  One deliberate difference from the viewer: KaTeX wraps its output in
  `<span class="katex">`, a hook for KaTeX's own stylesheet, which is absent
  from an exported quiz. That wrapper is not reproduced.

- **The `remote` base URL.** `html.xsl` builds `<img src>` as `@remote` + `/` +
  `@source`, and nothing in Python had ever set `@remote` — so every image came
  out root-relative and would have 404'd inside an LMS. `spatext_ele(remote=…)`
  now stamps it, and `html_ele()` **raises** when an exercise contains images
  and no `remote` was given.

  It is deliberately not defaulted from `bank.xml`'s `<url>`. That element names
  the bank's home page, which need not be the directory containing `assets/`, so
  defaulting to it would emit dead links that nothing detects until a student
  meets one. The demo bank's `<url>` does happen to point at its published
  directory, which is why `update_viewer.py` can safely take `--remote` from it
  — that is a property of this one bank, not a rule. `Outcome.html_preview()` passes `remote=''` explicitly to
  keep its existing relative behaviour.

### Is latex2mathml good enough? (measured, 2026-08-21)

Yes, and this was worth measuring rather than assuming, because the course
banks' generators turned out to be **plain Python** — the `.sage` file is only a
shim — so they can be run directly to see what LaTeX they really emit.

Across **805 distinct LaTeX strings** from `mat-106` and `mat-206`, plus 50 more
from the demo bank:

- `latex2mathml` hard failures: **0**
- exact agreement with KaTeX on visible content: **767/805 (95.3%)**
- the 38 disagreements are **two glyph choices only**: `\Box` renders as U+25FB
  rather than U+25A1, and `\overline` as U+2015 rather than U+203E
- structure matches KaTeX on all 150 examples of `\frac`, `\overline`, `^`
  and `_`, and the augmented-matrix rule survives as
  `columnlines="none none solid"`

### Is MathML even the right target for Canvas? (open)

Unresolved, and worth revisiting before anyone extends this. Canvas renders
`\(…\)` LaTeX directly via MathJax, and `text2qti` — the most mature tool
doing this same job — **defaults to LaTeX**, offering MathML only behind a flag
and stating no preference. Canvas QTI import also has a documented issue where
"MathML occasionally will not render correctly".

Against that: `51507be` ("export actual question/answers except for math (need
tex to mathml conversion)") says Steven hit something concrete that pushed him
to MathML for Canvas specifically, while Brightspace and Moodle still pass
`"default"` and receive raw LaTeX.

No evidence was found that Canvas reads MathML's
`<annotation encoding="application/x-tex">`; its own round-trip uses an image
with the LaTeX in alt text. So omitting the annotation, as latex2mathml does,
looks harmless.

The implementation therefore **reproduces current behaviour** rather than
redesigning it. Deciding whether LaTeX would do — which would delete the
consumer concept entirely — needs a real Canvas course to import into, not
documentation.

## Generator runtimes: plain Python (default) and SageMath (optional)

**Implemented 2026-08-04.** Authoring no longer requires SageMath, and therefore
no longer requires a container: `generate`, TikZ compilation, rendering to
LaTeX/HTML/PreTeXt, the viewer build and `build_docs.py` all run on a Windows
host. Sage was *demoted*, not removed — `wrapper.sage` is untouched and fully
functional for anyone who has Sage installed.

### The seam: the generator's file extension picks the runtime

There is no setting and no config field. A generator declares what it needs by
its own filename:

| file | interpreter | wrapper |
|---|---|---|
| `generator.py` | `sys.executable` (the interpreter running checkit) | `wrapper/wrapper.py` |
| `generator.sage` | `sage` | `wrapper/wrapper.sage` |

Defined in `wrapper/__init__.py`'s `RUNTIMES` dict; resolved by
`Outcome.generator_path()`, which looks for `generator.py` first and falls back
to `generator.sage`. Consequences worth knowing:

- **A bank may mix the two.** Migration is per-outcome, not all-or-nothing.
- **Adding a third runtime is one more `RUNTIMES` entry** plus a filename in
  `Outcome.GENERATOR_FILENAMES`. Nothing else changes.
- `sys.executable`, not the string `"python"` — on a machine with several
  Pythons the bare name resolves to whatever is first on PATH, which is often
  not the environment checkit is installed in.

The entry point was renamed `sage()` → `run_generator()`, since a function named
`sage()` that may launch Python is actively misleading.

### What `wrapper/wrapper.py` contains

A SymPy-backed port of `wrapper.sage` that keeps the CLI signature, the
author-facing names, and the `BaseGenerator` / `CheckIt` / `provide_data` API.
Two pieces had no SymPy equivalent and are implemented here:

- **`CheckItMatrix`** — wraps a SymPy `Matrix` and carries the augmented-matrix
  *subdivision* (the vertical bar) that Sage matrices track natively. Exposes the
  subset of Sage's matrix API the helpers and generators actually use, including
  `rref()` returning just the reduced matrix (SymPy returns a `(matrix, pivots)`
  tuple) so the helper code reads the same in both runtimes.
- **`_random_full_column_rank`** — replaces
  `random_matrix(QQ, …, algorithm='echelonizable')`. Starts from an identity
  block, then applies random unimodular row operations, which preserve both rank
  and integrality so the result stays exactly solvable by hand.

`GENERATOR_NAMESPACE` is the author-facing surface — the names a `generator.py`
sees without importing anything. Sage supplies its equivalents automatically;
here they are listed explicitly. Extend that dict to give authors more.

### What a generator can reach: bank helpers and its own seed

**`bank_helpers.py` at the bank root** is where a bank author puts functions more
than one generator needs. `checkit new` scaffolds it with a docstring and two
example functions. Any generator does `import bank_helpers as bh`, however deeply
nested its outcome folder is.

This works because `load_generator()` adds two directories to `sys.path`: the
generator's own folder, then the bank root. Neither is there by default —
running a script puts only *that script's* directory on the path, which here is
the wrapper's temp directory, and cwd (the bank root) is not on `sys.path` in
Python 3. Without this a bank has to resort to `runpy` tricks to share code
between outcomes.

They are **appended, not inserted at position 0**. Prepending would let a bank
file shadow the standard library — a `math.py` or `random.py` at the bank root
would break the runtime in a thoroughly confusing way. Appending means the worst
case is a bank module being ignored because an installed package already claims
the name, which is confined to the file that misnamed itself. Verified: a
bank-root `math.py` that raises on import does not affect generation.

Distinguish this from the built-in **`CheckIt` class**, which ships with the
platform, is available without importing, and is *ours* to maintain.
`bank_helpers.py` is the author's and is *theirs*.

**`self.seed`** is readable inside `data()`, alongside the existing
`self.variant`. It exists for skills that cannot be randomized algorithmically:
serve a fixed, hand-written problem for each of the seeds the viewer exposes,
and choose randomly above that, where printed assessments draw from. See the
`CURATED` demo outcome.

Note the seed was always *stored* — but under a name-mangled `self.__seed`, and
`get_data()` only added it to the returned dict as `__seed__` *after* `data()`
had already run. So it was unreachable at the moment a generator needed it.

### Migration hazard: three Sage-isms that fail *silently*

Porting the eight demo generators surfaced exactly three real differences, and
**none of them raise an error** — they produce wrong output:

| Sage | plain Python | seen in |
|---|---|---|
| `x^p` — exponentiation | **bitwise XOR** | EX2, `checkit new` scaffold |
| `a == b` — builds an equation | **compares, returns `False`** | EX1 |
| `-A/B` — exact `Rational` | **float** `-0.666…` | EX1 |

Use `x**p`, `Eq(a, b)` and `Rational(-A, B)`. Any future bulk migration wants an
automated scan for `^` and bare integer division rather than a read-through; EX1
would otherwise have shipped `0.6666666666666666` as a slope indefinitely.

Also dropped: MX1's `var("zw", latex_name="w")`. Sage used it to give a symbol a
sort key different from its printed name. SymPy has no display-name override —
but that helper takes an explicitly ordered list, so the trick was unnecessary.
Note `CheckIt.vars()`'s name-shuffling **is** still needed: SymPy orders the
terms of a sum by symbol name exactly as Sage does.

### Known gaps and future options

- **`matplotlib` is an optional extra** (`pip install checkit-dashboard[plots]`),
  not a hard dependency: only banks calling `plot()` need it, and
  `tikz_graphics()` needs no Python plotting library at all. `plot()` raises a
  clear message when it is absent. The built-in `plot()` is deliberately simple
  (single expression, one variable, fixed range) — Sage's is far richer, and a
  bank needing more should either use `tikz_graphics()` or extend
  `GENERATOR_NAMESPACE`.
- **Output is not comparable across runtimes.** The RNGs differ, so seed *N*
  yields different content, `build_variant_bag`'s shuffle-bag reassigns variants,
  and SymPy's LaTeX spacing differs cosmetically from Sage's. A bank that
  switches regenerates from scratch; do not diff generated output across the
  change and conclude something broke.
- **Nothing in this repo exercises the Sage path any more** — every demo
  generator is now `.py`, by choice. `wrapper.sage` is working code rather than a
  stub, but it is untested code from here on. If it is ever revived, expect to
  fix bit-rot.
- **Duplicated `CheckIt` helpers.** The helper library now exists twice, in Sage
  flavor and SymPy flavor. This was accepted deliberately rather than abstracted
  away up front: an interface designed against a single implementation is usually
  the wrong interface. Should a third runtime ever be wanted, the options are, in
  increasing order of cost:
  1. leave the duplication alone (fine while only one runtime is maintained);
  2. factor the backend-specific operations behind a small adapter — `latex`,
     `symbol`, `matrix`, `rref`, `nullspace` — leaving the algorithmic bulk of
     `CheckIt` written once. Design it by extracting what `wrapper.py` and
     `wrapper.sage` genuinely share, not by guessing;
  3. a source-to-source translator. Viable for *syntax* (`^` → `**`) and worth it
     as a one-time, reviewed, committed codemod for generator files. Not viable
     for semantics: `A.rref()` returns different shapes in the two libraries and
     `random_matrix(algorithm='echelonizable')` has no SymPy counterpart at all,
     so no text rewriter can bridge them. Never at runtime — the code that ran
     would not be in the repo to grep, diff or breakpoint.
- **The devcontainer still installs SageMath**, which is now optional. It could
  be slimmed considerably, or kept as the "full" environment for anyone who wants
  the Sage runtime available.
- **Abstract algebra remains the real gap** if the Sage runtime is ever needed:
  Sage's GAP-backed group theory, polynomial rings over arbitrary rings and
  `GF(q)` are well ahead of SymPy. Combinatorics is workable via `math.comb`,
  `itertools` and SymPy's `catalan`/`bell`/`stirling`; algebra, precalculus,
  calculus, linear algebra, discrete and intro stats are fully covered.
  *(Assessed, not tested.)*


## Do not regenerate W1 or W1-E

**mat-106's `W1` and `W1-E` seeds are frozen.** Students are working through
them as homework right now, and a student half way through an assignment must
not find the problems have changed underneath them.

Practically, that means never running a bare `checkit generate -r` against
mat-106. Regenerate per outcome:

```
python -m checkit generate -r -a 1000 -o SLUG --remote https://jslyemath.github.io/mat-106-checkit
```

`-o` regenerates only that outcome's `seeds.json` and re-renders everything else
from data already on disk, so the other outcomes' versions are untouched. (That
is only true since the `-o` fix; before it, `-o` also destroyed the rest of
`bank.json`. See "Known platform bugs".)

Verify rather than trust, when a change is near them:

```
md5sum assets/W1/generated/seeds.json assets/W1-E/generated/seeds.json
```

Take that before and after. It is what was done for the 2026-08-31 variant
conversion, and it is two seconds against a fortnight of student work.

**This is now a mechanism, not just a note** (built 2026-08-31). Both outcomes
carry `<frozen/>` in `bank.xml`, and `generate_exercises` refuses to regenerate
a frozen outcome:

```
SKIPPING W1: marked <frozen/> in bank.xml. Its existing seeds are kept.
To regenerate it anyway: --thaw W1
```

Four properties worth keeping if this is ever touched:

- **It blocks regeneration, not rendering.** A plain `checkit generate` still
  re-renders a frozen outcome, so a stylesheet fix reaches published HTML
  without anyone thawing anything. The problems do not change; only how they
  are drawn.
- **It is loud.** A `-r` that quietly did less than asked would be its own
  hazard, so the skip is printed per outcome with the exact command to override.
- **The outcome stays in `bank.json`.** Frozen means "keep these versions", not
  "drop this outcome" -- the `-o` bug taught that lesson already.
- **Thawing names the outcome.** `--thaw W1`, repeatable, and refused if the
  slug is unknown *or* not actually frozen. A blanket `--force` would be typed
  reflexively, which is the reflex the flag exists to interrupt.

---

## Where things stand (2026-09-02)

| | |
|---|---|
| SageMath removed as a requirement | done |
| TikZ image backend | done |
| Browser XSLT migration (steps 1-3) | done — see "Browsers are removing XSLT" |
| Viewer shows 50 versions, not 20 | done — `PUBLIC_SEEDS` |
| Test suite | done — **127** in checkit, **53** in checkit-printit |
| Build verification | done — `checkit check`, see "Checking a build" |
| Fork versioned and released as a wheel | **v0.2.8.5 is the newest wheel; source is 0.2.9.1.** See "The unreleased wheel" |
| Port mat-106 off its Sage shims | done — 28 outcomes + 1 associate, `mode` retired |
| mat-106 published and verified | done — 2026-08-27, no `checkit check` findings |
| SpaTeXt elements for per-medium differences | done — `<glyphs>`, `<nobreak>` |
| mat-206 | **not started, and not a port** — see below |
| Print tool as its own package | done — [checkit-printit](https://github.com/jslyemath/checkit-printit), stages 1-5 and 9; see `PRINT_TOOL_DESIGN.md` |
| A real quiz printed from mat-106 | done — 2026-09-01, 98 pages; all 28 outcomes build. See "The first real quiz" |
| `skillcheckpoints.sty` drift between banks | **drifted 2026-09-02.** mat-106 and the printit package match; mat-206 is one colour fix behind and is being rebuilt from scratch, so it is deliberately not chasing |
| Upstream merge | current — 0 behind, 97 ahead as of 2026-09-02 |
| mat-106 typography pass | done — commas, spacing, entities; regenerated and republished |

Known open questions, none blocking:

- **Is MathML the right target for Canvas at all?** Canvas renders `\(...\)`
  LaTeX via MathJax, and `text2qti` defaults to LaTeX. Settling it needs a real
  Canvas course to import into. The current implementation reproduces the
  viewer's previous behaviour rather than redesigning on documentation.
- **Firefox is unverified** for the `subset` stylesheet work; `browser_harness.py`
  was only ever run in Chromium, and Firefox is the engine that surprised this
  project before.
- **The LMS export hardcodes 900 versions per outcome**, which is what makes the
  published `docs/` 25 MB. Reducing it is an instructor-facing choice.
- **No printed output has been compiled since the port.** Every check written so
  far reads the emitted LaTeX, not a PDF. `checkit check` will tell you the
  document is well-formed; it cannot tell you the page looks right. The print
  tool is where that gets exercised for the first time.
- **The bank has two templates per outcome, and always has.** `template.xml`
  for the web and `textemplate.tex` for print. The print templates carry
  things SpaTeXt cannot say -- true/false items, fill-in blanks, two-column
  layout, working space -- which is why they exist. Whether that stays a
  permanent split or shrinks to an escape hatch is the print tool's central
  design question; see "Print-specific appearance".

### The bank has not been reviewed exercise by exercise

**Worth knowing before trusting a clean `checkit check`.** On 2026-08-27 a
human spot-check of four outcomes found all four rendering visibly wrong
content, and each fix exposed the next problem:

| | rendering as | since |
|---|---|---|
| `N1`, `N1-E` | "is a multiple of" — *both numbers missing* | the port |
| `W4` | a bare `\mbox{`; print would not compile | the port |
| `D4` | `27.6\%` and `\$770.13`, literally | the port |
| `R2` | `228 // 12`, `228 % 12`, `ceiling(...)` | earlier |
| `W4` (embedded W4-E) | "explaining the &nbsp; to an elementary student" | the port |
| `D1-E` | "If one &nbsp; represents one unit… ten **s** to create a single &nbsp;" | **predates the port** |

Every one of them was found by a person looking at a page, and every automated
check in place at the time passed them. `D1-E` is the one to keep in mind: it
was broken before any of this work started, in an outcome nobody had cause to
open.

The checks now catch that whole family — empty substitutions, swallowed markup,
TeX in prose, uncompilable LaTeX — and `checkit check` is clean across all 28
outcomes. But **roughly 23 outcomes have never been read closely by anyone**,
and the checks only know about faults that have already bitten. A pass through
the bank, one outcome at a time, is unglamorous and is the highest-value
unstarted work on this list after the print tool.

### Known platform bugs

**The assessment builder references images that were never rendered**
(found 2026-09-01, unfixed). `getRandomAssessmentFromSlugs` picks a seed in
`[PUBLIC_SEEDS, BUNDLE_UNTIL)` -- 50 to 399. `--image-seeds N` rasterises PNGs
only for seeds `0` to `N-1`. mat-106 publishes with `--image-seeds 50`, so
**every assessment containing `F2` or `F2-E` points at a PNG that does not
exist**, in both the HTML preview and the LaTeX export.

Three things hide it:

- browsing is fine, because the viewer only ever shows seeds 0-49;
- print is fine, because mat-106's `textemplate.tex` writes TikZ inline and
  never touches the PNGs;
- `checkit check`'s `relative-img` check passes, because the `<img src>` *is*
  absolute -- it points at a real URL that happens to 404.

The immediate fix is `--image-seeds 400`, at roughly eight times the
rasterisation time and `docs/` size. The better fix is publishing `.tikz` and
having figures `\input` their source, which also makes an exported assessment
self-contained -- see `PRINT_TOOL_DESIGN.md` section 6b.

A check worth adding: every `<img src>` and `\includegraphics` in the published
bundles resolves to a file that exists. That is a cheap addition to
`checks.py` and it would have caught this.


**`checkit generate` swallows generator tracebacks.** `run_generator` runs each
generator in a subprocess and lets `subprocess.CalledProcessError` propagate, so
a failing generator reports only the argv and an exit status -- the child's
actual `AttributeError`/`NameError` and its line number are lost. On 2026-08-27
this turned a one-line naming bug into a guessing game, because the only way to
see the real exception was to write a separate in-process runner. Propagating
the child's stderr into the raised error would fix it; the generator already
runs under a known interpreter, so there is nothing to negotiate.

Until it is fixed, the workaround is an in-process runner: exec each
`generator.py` in `wrapper.GENERATOR_NAMESPACE`, construct `Generator()`
normally, set `seed` and `variant`, and call `data()` across a spread of seeds.
It checks every generator in seconds. Construct it normally rather than with
`__new__` -- `BaseGenerator.__init__` sets `variant`, and stubbing around it
produces false `AttributeError: variant` failures on any outcome declaring
`variants`.

~~**Build-verification tooling has no home.**~~ Resolved 2026-08-27: it is
`checkit check`, in `checks.py` and `smoke.py`. See "Checking a build" below.


**`checkit generate -o SLUG` destroyed the rest of `bank.json`** (fixed
2026-08-27). The command filtered `Bank._outcomes` down to the one requested
and then called `write_json()`, which serialises whatever is left -- so a
single-outcome regeneration silently rewrote the manifest to contain that
outcome alone. The per-outcome `seeds.json` files survived, so nothing was lost
permanently, but the published bank was wrong until a full `checkit generate`
ran again. This was upstream behaviour, not a fork regression, and it is the
natural thing to reach for when iterating on one generator.

The same narrowing skipped the missing-`remote` preflight for the outcomes it
excluded -- the same shape, since that check also runs over `self.outcomes()`.
Their precomputed HTML still lands in `bank.json`, so it still needs an
absolute base URL; without one the `<img src>` is root-relative and 404s
wherever the HTML is displayed.

**The fix: the filter was one layer too high.** It now travels as `only=`, a
set of slugs, into `Bank.generate_exercises()` -- the single operation that
should be narrowed -- and the Bank keeps every outcome it parsed. `write_json()`
is never handed a partial Bank, so both symptoms go away together rather than
needing separate guards.

Two consequences worth knowing:

- **`-o` is no longer fast.** `write_json()` now re-renders the precomputed
  formats for every outcome, because that is what a correct manifest contains.
  It does *not* re-run generators: `write_json()` passes `regenerate=False`, so
  each outcome loads from its existing `seeds.json`. Only the XSLT work repeats.
- **`-o PLAIN` on a bank with figures now demands `--remote`,** even when the
  named outcome has none. That is correct -- the manifest carries the other
  outcomes' HTML -- but it is a behaviour change from before the fix.

A slug matching no outcome now raises `BadParameter` listing the available
slugs. It previously produced an empty filter, and regenerating nothing is
indistinguishable from a successful run.

`test_outcome_filter.py` guards all of it, reusing `test_precompute.py`'s
two-outcome fixture: `PLAIN` has no figures and `FIGURED` does, which is exactly
the pair both symptoms need. Seven of its ten tests fail against the unfixed
code; the three that pass describe behaviour that was already correct.

## Next: mat-206, and the lessons the mat-106 port left behind

mat-106 is done and published; what remains here is mat-206 (which is not a
port -- see below) and the print tool, which is the next thing to start.

One thing that turned up while testing `latex2mathml` and makes the port easier
than it looks: **the course banks' generators are already plain Python.** They
import only `random`, `slye_math`, `fractions`, `math`, `re`, `inflect`,
`datetime` and `decimal` — no Sage anywhere — so they can be run directly today.
All 805 distinct LaTeX strings in the corpus were produced that way. Two
incidental findings from doing so, worth knowing before the port:

- `mat-106`'s `F3-E` raises `TypeError: Random.choice() takes 2 positional
  arguments but 3 were given` under plain Python, so something there depends on
  Sage's `choice`. It is the one generator that will not simply move across.
- Four outcomes (`D4`, `F5`, `F5-E`, `R2`) need `inflect`, which is in the
  banks' `requirements.txt` but is not a CheckIt dependency.

### Context

The course banks (`mat-106-checkit`, `mat-206-checkit`) predate the Python
runtime. Each outcome there holds a `pygenerator.py` with the real logic and a
25-line `generator.sage` shim that `runpy`-loads it and inserts `outcomes/` into
`sys.path`. There was never duplicated logic — the shim existed only because
Sage could not otherwise reach a plain-Python file, and because the bank root
was not importable. **Both reasons are now gone.**

Those banks also each carry a copy of a print pipeline (`pdfgenerator.py`,
`skillcheckpoints.sty`, `main_template.tex`) that turns a roster CSV into a
single PDF: many exercise versions, distributed by seating chart, student names
inserted, answer keys appended. That is *not* CheckIt's assessment builder, which
produces one anonymous assessment.

### The `<m>` wrapper a converted generator leaves behind (found 2026-08-27)

**This is the one that actually reached students, and it is the worse
direction of the same mistake.** A generator that used to emit plain TeX had a
template wrapping its slot in `<m>`:

    <p><m>{{{p1_prob}}}</m></p>

Converting the generator to emit `<m>` elements makes that wrapper *nested*,
and `html.xsl` renders `<m>` with `normalize-space(text())` -- direct text
children only. Every nested element is discarded and the prose between them
survives, typeset as mathematics. So

    <m><m>12</m> is a multiple of <m>4</m></m>

renders as the words "is a multiple of" in italic maths, **with the numbers
gone**. The exercise is not merely ugly, it is unanswerable, and nothing fails:
the build is clean, the data is correct, and `bank.json` contains a perfectly
well-formed `<span class="math">`.

Found in 22 template slots across `N1` (11), `N1-E` (3) and `W4` (8). W4
rendered as a bare `\mbox{`. **The conversion is only half done until the
template's wrapper comes off** -- that is the step to look for whenever a
generator starts emitting markup.

The detector is exact, and belongs in any bank's checks: walk each exercise's
SpaTeXt (`Exercise.spatext_ele()`) and report every `<m>` that has element
children. Do not try to detect this in the rendered HTML -- by then the
evidence has been deleted.

> **Principle.** When a value changes from text to markup, every place that
> *wraps* it is now wrong. The wrapper is not neutral just because it was
> correct yesterday.

### The second trap generalises, and it was live (found 2026-08-27)

That last trap is not a detail of one generator. The first real rebuild after
the port found **five** places emitting LaTeX into fields that are not maths,
across 232 exercise versions. Two were already published and being read by
students; three were latent in generators committed but never built.

| | leaked | why | fix |
|---|---|---|---|
| `W1`, `W1-E` | `\text{MDCXLVIII}` | bare TeX into a `{{{markup}}}` slot | `bank_helpers.as_math()` |
| `F5` | `\textbf` | left over from the `mode` merge | `<em>` |
| `F2-E` | `\textbf` | written in the template's own prose | `<em>` |
| `F3-E` | `\dfrac` | bare TeX into a `{{text}}` slot | `<m>` in the template |

**`<em>` is the fix rather than a workaround**, because `latex.xsl` already
renders `stx:em` as `\textbf{...}`. Print output is byte-identical and only the
screen changes -- the same stylesheet seam that `<glyphs>` uses. `spatext_math`
now rewrites `\textbf{...}` into `<em>` alongside the maths forms, so the
generators that already route prose through it are fixed at one site.

**Where the fix lives depends on what else fills the slot.** `F3-E` is fixed in
its template, because those two slots only ever carry maths. `W1`/`W1-E` cannot
be: the same slot also receives `glyphs()` output, and a `<glyphs>` element
placed inside `<m>` is silently swallowed by the rule above. There the choice
has to travel in the value, which is what `as_math()` is for.

**A related one-line bug, same family.** `W1-E` wrote `'\Large\textpmhg{...}'`
as a non-raw Python string, so `\t` became a tab and print received
`\Large<TAB>extpmhg{...}`. Its two sibling lines escaped correctly; only that
one did not, and `\L` is an *invalid* escape that warns while `\t` is a valid
one that does not. 334 of the 382 occurrences were in seeds 50-399 -- the pool
printed handouts draw from, so it would have surfaced on paper.

**These are now `checkit check`** (see "Checking a build"). What they look for,
and why each shape matters:

- stray control characters (`\t`, `\f`, `\v`, `\b`, `\a`, `\r`) in any
  precomputed format -- catches the non-raw-literal bug directly;
- backslash-commands surviving in HTML *text*, after stripping tags and
  `class="math"` spans -- catches everything in the table above. **Match both
  shapes**: multi-letter commands (`\text`, `\dfrac`) *and* single-character
  escapes (`\%`, `\$`, `\&`, `\_`, `\#`). The first version required two or
  more letters after the backslash and therefore reported a confident clean
  while `D4` showed students `27.6\%` and `\$770.13` in 300 places;
- `<m>` elements containing child elements, read from the SpaTeXt rather than
  the HTML -- see the section above, and note that the HTML cannot show it;
- the same two run over the `derived.json` bundles, because `bank.json` inlines
  only the 50 public seeds and says nothing about what print will get.

Run them against the previous build as well as the new one: the useful output
is not "there are leaks" but "which of these are new today".

**Two process lessons that cost real time.**

`checkit generate` runs each generator in a subprocess and reports only
`subprocess.CalledProcessError` with the argv -- the actual traceback is lost.
A generator failure is therefore near-undiagnosable from the build log. An
in-process runner that execs each `generator.py` in `wrapper.GENERATOR_NAMESPACE`
and calls `data()` across a spread of seeds and every declared variant surfaces
it in seconds, and checks all 29 generators faster than one build checks none.
Construct the generator normally and set `seed`/`variant`; stubbing the object
with `__new__` produces `AttributeError: variant` and four false failures.

**Do not write these scripts through a Bash heredoc on this machine.** The tool
mangles backslashes: `text.count('\\')` arrived as `text.count('\')`, and a
sweep whose regex `r"\\[a-zA-Z]{2,}"` arrived as `r"\[a-zA-Z]{2,}"` reported a
confident, wrong "none". On a LaTeX-heavy codebase that is a silent-failure
generator. Write the file with an editor tool and run it, and give any detector
a self-check against a known-bad probe so a broken pattern cannot pass as a
clean result.

**A greedy pattern is the same failure in miniature.** `spatext_math`'s money
rule was `\\\$[0-9][0-9,.]*`, which happily consumes the punctuation that ends
the sentence: "worth \$982.69." became `<m>\$982.69.</m>`, setting the full stop
in italic maths. Requiring the run to *end* in a digit fixes it. Nothing catches
this by inspection of one example, because the amount looks right -- the
detector is "maths whose content ends in `.` or `,`", and it has to allow
display maths, where punctuation inside the equation is correct typesetting.

> **Principle.** A detector that cannot demonstrate a failure has not reported
> a pass. This is the same rule the test suite already follows by breaking the
> code each guard protects.

**Naming hazard.** The helper was first called `math()`, which replaced the
stdlib `math` that `bank_helpers.py` imports at module level; `rel_primes` then
called `math.gcd` on a function object and every `F5` seed died. Hence
`as_math()`, and a standing assertion that `sm.math.gcd` is still callable.

**Why not simply keep `mode`.** The pipeline already has two designed seams for
this: the stylesheets, for how one thing renders in different media, and the
seed ranges, for which exercises serve which purpose. A generator-level `mode`
is a third place expressing the same distinctions, and the three cannot be kept
consistent by anything but discipline -- the failure this codebase has already
paid for twice with the duplicated stylesheets and the duplicated dependency
list.

### mat-206 is not a port (established 2026-08-27)

The roadmap above says "port mat-206" alongside mat-106. That is wrong, and it
matters because it sets the wrong expectation for the work.

**mat-206 has no generators.** All 30 `outcomes/*/pygenerator.py` are five-line
stubs -- `def generate(**kwargs): return {}` -- and every `template.xml` is 255
bytes. `outcomes/slye_math.py` is a copy of mat-106's, not a sibling: 27 of its
29 functions are byte-identical, and the only real difference is that mat-106's
`to_simple_babylonian` grew a `mode` parameter for `<glyphs>`. It also carries
`generator.sage` shims, a `pdfgenerator.py`, and a `requirements.txt` pinning
`checkit-dashboard == 0.2.7`, all inherited by copy rather than written.

What *is* real is `bank.xml`: **31 outcomes** with genuine titles, slugs,
descriptions and a colour map (prefixes `G`, `M`, `A`, `S` -- geometry,
measurement, algebra, statistics). That is the specification, and it is a
larger one than mat-106's 28. The work is authoring generators against it, not
migrating anything.

(There are 30 `outcomes/*/` directories against 31 declared outcomes, so the
scaffold does not even cover its own manifest. Worth reconciling before writing
anything.)

Consequences for the roadmap steps below: steps 1, 2 and 5 are moot for mat-206
(there is nothing to move, unwrap, or audit), step 3 is moot (no generator
mentions `mode`), and step 4 is moot (no generator mentions `course_progress`).
What mat-206 should inherit is mat-106's *finished* `bank_helpers.py`, dropped
in at the bank root, and the `Generator` class shape -- not its history.

## The first real quiz, and what it found (2026-09-01)

Four pretend students, the first 14 outcomes, A/B by seating, keys at the back.
Ninety-eight pages, and it took three fixes to get there. Then all 28 outcomes,
two students: 130 pages, clean.

Worth reading because none of it was visible to `checkit check`, to the test
suite, or to the website. All three needed a PDF.

### SpaTeXt was leaking into LaTeX in nine of 28 outcomes

The bug the whole two-template split was always going to produce.

A generator returns strings, and since the port some of those strings carry
inline SpaTeXt: `<m>` for maths, `<em>`, `<glyphs>` for an ancient numeral,
`<nobreak>`. `template.xml` inserts such a field with **triple** braces, so the
markup becomes part of the document the stylesheets transform, and the web is
right. `textemplate.tex` inserts the same field into LaTeX, where a tag is just
characters. W1 sent pdflatex an Egyptian hieroglyph inside a `latex="..."`
attribute and the build stopped:

    ! LaTeX Error: Unicode character U+133FA not set up for use with LaTeX.
    l.15 ...thousand\Hmillion\Hmillion\Hmillion}">

Affected: **R2, W1, W1-E, W4, N1, N1-E, N2, F5, D4**. Every one of them is an
outcome whose generator was reformatted to emit SpaTeXt. Fixing the web broke
print, silently, and nothing looked at print until now.

The fix is in the print tool, not the bank: `checkit_printit/spatext.py` renders
each field through `latex.xsl` before Jinja sees it. Reusing the stylesheet
matters -- it already knew to prefer a `<glyphs>` element's `@latex` attribute
over its Unicode, which is exactly the case `<glyphs>` was added for. A
reimplementation in Python would have had to learn that again.

Two banks files needed editing too: W1 and W1-E wrapped those fields in
`$...$`, which was right while the field was a bare LaTeX string and nests
maths inside maths once the field renders its own. Seeds untouched -- the
freeze on W1/W1-E is about seeds, and this changes only how a page is built.

**The lesson to carry to mat-206.** A field that carries markup has exactly one
correct consumer: something that parses it. Any second template that pastes the
same field as text will drift the moment a generator changes, and the drift is
invisible until someone compiles. An outcome with no `textemplate.tex` cannot
have this bug at all, which is the strongest argument yet for the SpaTeXt route
being the default.

### Figures: only the machine-made ones were being copied

`_copy_assets` copied `assets/<slug>/generated/`, which is where the TikZ
backend writes. R1's 38 hand-drawn PNGs sit directly in `assets/R1/` and never
travelled, so the output folder referenced `assets/R1/pemdas-1p.png` and did not
contain it.

It now scans the written skill files for `\includegraphics` and `\input{*.tikz}`
and copies exactly what they name. Two gains beyond the fix: the folder carries
2 figures instead of 38, and a reference the bank cannot satisfy is reported by
name at assembly instead of surfacing as `using draft setting` a thousand log
lines before pdflatex gives up.

### The pdflatex log was decoded with the locale encoding

`subprocess.run(..., text=True)` decodes with the locale codec, which is cp1252
on this machine. pdflatex echoes font and file names byte for byte, one of them
contained 0x81, and the decode ran on subprocess's reader **thread** -- so the
exception printed to stderr, `stdout` came back as `None`, and a real LaTeX
error became `TypeError: unsupported operand type(s) for +: 'NoneType' and
'str'` six lines later. Now decoded as UTF-8 with `errors="replace"`.

Worth remembering as a shape, not just a bug: an exception on a reader thread
does not fail the call, it empties the result.

### Still open after this run

- **Babylonian answers print black on the key.** `\babo` and `\babt` in
  `skillcheckpoints.sty` draw with TikZ `fill=black`, which ignores the ambient
  `\color{scCOLOR}` that `ansenv` sets. `fill=.` would take the current colour.
  Not fixed because the `.sty` exists in three byte-identical copies (both banks
  and the print package) and they should change together.
- **N1's `textemplate.tex` asks for six fields no generator sets** --
  `explain_prob_1..3`, `explain_ans_1..3`. All six are inside `%` comments,
  left from when N1-E shared the slot, so the run is correct. The tool reports
  them because a missing field inside a comment and a missing field in live
  text look identical to Jinja.
- **W4 runs to two pages** (ten items) and **N1** likewise. Content, not layout.

## The print tool

> **Superseded by `PRINT_TOOL_DESIGN.md`** (2026-09-01), which folds in a
> review conversation and reverses one decision recorded below. The short
> version of the reversal: `skillcheckpoints.sty` is deliberately a working
> *by-hand* system -- MAT 206's skills are hand-written `.tex` files using it,
> with no CheckIt involved -- so the unit of exchange is a skill `.tex` file and
> the `.sty`'s existing commands are the interface. The proposal below, to have
> `latex.xsl` emit semantic `\stxKnowl`/`\stxTask` commands for a theme to
> redefine, would create a second vocabulary that hand-authors never write.
> What follows is kept for the reasoning that still holds.

Belongs in **its own repo**, installed as a package depending on
`checkit-dashboard` — not in the platform (Google OAuth and seating charts are
not platform concerns, and it would worsen upstream merges) and not in a bank
(there are two, and the pipeline is currently copied between them by hand).

Intended shape: consume a bank's pregenerated `seeds.json` rather than importing
generators, so printing needs no generation step and printed versions are
reproducible. Join the roster locally — student names never enter the bank at
all.

**But not from the published seed range.** An earlier version of this note said
to draw from seeds at or above `PUBLIC_SEEDS` because the viewer does not offer
them. That is wrong: `derived.json` publishes seeds 50-399 *with their answers*.
See "The conflict: printed seeds cannot come from the published range" below,
which has to be settled before the tool is written — it decides whether the tool
takes a bank checkout or a URL.

**Start by compiling something.** No printed output has been produced since the
port. `checkit check` verifies the emitted LaTeX is well-formed; nothing has
verified it *typesets*.

---

## What the print pipeline actually is today

Read this before designing anything. The existing setup is considerably more
capable than "a LaTeX template", and an earlier version of these notes badly
under-described it.

**`skillcheckpoints.sty`, 610 lines, and byte-identical between the two banks.**
The open question about whether it had drifted is answered: it has not
(`diff` produces nothing, 2026-08-27). That is a much better starting position
than assumed — one file, one theme, no reconciliation needed.

**Each outcome has *two* templates.** `template.xml` is SpaTeXt for the web.
`textemplate.tex` sits beside it and is a full Jinja-style LaTeX template
(`\VAR{p1_prob}`) rendered against the same generator data. So the bank already
has a print-specific template per outcome, and has had one all along.

**`pdfgenerator.py` assembles.** It writes `Skill Descriptions.tex` from
`bank.xml` (slug, colour, description → `\setskilldesc[colour]{slug}{desc}`),
renders each outcome's `textemplate.tex` per seed, wraps student copies with
`\setname{...}` and `\preparefornextstudent`, and then emits the whole thing a
second time under `\setboolean{anstoggle}{true}` to produce the answer keys.

### The four answer mechanisms, which are the important part

`anstoggle` is a single boolean, but it is *consumed* four different ways, and
the differences are not stylistic — they are about what kind of answer the
exercise has.

| | definition | reveals by | used by |
|---|---|---|---|
| `\ans{...}` | `.sty:71` | printing the answer text inline, in the theme colour | F2, F2-E, R1 |
| `ansenv` | `.sty:72` | un-commenting a whole block and colouring it | 21 outcomes |
| `\tfleft[True]{stmt}` | `.sty:77-89` | **boxing one of two already-printed words** | N1 |
| `\fillinblank[2.25in]{ans}` | `.sty:100-102` | filling a ruled space that is *always* there | D3, W4 |

That table is the whole design problem in miniature.

- `ansenv` is the only one CheckIt can currently express. It is exactly
  `<outtro>` and `subset='statement'`.
- `\tfleft` reveals an answer **without printing anything new**: TRUE and FALSE
  are both on the page either way, and turning answers on draws a box around
  the right one. Nothing in SpaTeXt can describe that, because SpaTeXt has no
  notion of an exercise whose answer is a *selection*.
- `\fillinblank` reserves space unconditionally — a 2.25in rule the student
  writes on — and puts the answer inside it when keys are printed. The blank
  is part of the *question's* layout, not the answer's.
- `\ans` is an inline fragment inside otherwise-shared prose.

**`\tfleft` and `\fillinblank` are the two that matter**, because they prove the
gap is not about styling. Both are statements about *what kind of response the
exercise wants*, and that is a property of the exercise, not of the page.

### The other pieces worth naming

- **`\skillheader{N1}`** (`.sty:476`) opens each skill with a coloured
  `tcolorbox` titled with the slug and containing the outcome description,
  looked up from the `pgfkeys` dictionary that `pdfgenerator.py` generated out
  of `bank.xml`. The bank is already the single source of truth for that
  content; only the box is print-specific. **This one is already right** and
  needs no redesign — it just needs to keep working.
- **`\setvseed{\VAR{seed}}`** puts the version in the footer, so printed
  versions are already identifiable. CheckIt's LaTeX output, by contrast,
  records neither slug nor seed anywhere in the document.
- **Layout the templates rely on**: `\minicol[.5][.427]{prob}{Property: blank}`
  for two columns, `\vfill` between items for working space (22 outcomes),
  `\onehalfspacing` / `\doublespacing`, `\\[4ex]`.
- **Bank-specific macros the content cannot compile without**: `\babo`,
  `\babt`, `\babz` (TikZ drawings, not font glyphs), `hieroglf` for
  `\textpmhg`, `\rnc` for Roman numerals, `\arc`, `\additiontable`.

---

### The full feature list, from reading `pdfgenerator.py`

The tool is not "render templates and concatenate". Catalogued so nothing gets
dropped by a rewrite that only looked at the LaTeX:

| feature | where | note |
|---|---|---|
| **Per-student skill selection** | roster columns `1:`, `2:`, … | each student's packet is a *different subset* of skills |
| **Variant → seed mapping** | `Var:` column | students sharing a variant share a version; this is the seating-chart defence |
| **Random 5-digit seeds** | `random.choice(range(10000, 100000))` | see the conflict below |
| **Seed override** | `Seed Override:` | forces one seed for every variant, for reprints |
| **Sections** | `Sec:` column | `\setsect`, appended to the header |
| **Names on/off** | `Include Names:` | real name, or a ruled blank |
| **Key count** | `Key Amount:` | whole key packet repeated N times |
| **Per-run generator settings** | `course_progress`, `w7_allow_terminating`, `n3_n4_force_listing_method`, `d2_allow_repeating` | passed straight into `generate(**settings)` |
| **Per-skill colour** | `bank.xml` `<color_map>`, or a per-outcome `<color>` | resolved by slug prefix, defaulting to `scCOLOR` |
| **Associates** | `<associate>` entries | parsed, and deliberately not generated |
| **Key deduplication** | `used_versions` set | only versions actually handed out get keys, sorted in bank order |
| **Double-sided safety** | `\preparefornextstudent` | stops one student's packet backing onto another's |
| **Course/semester/professor** | spreadsheet | the four `\VAR{}`s in `main_template.tex` |
| **Error log to file** | `latex_error_log.txt` | a LaTeX failure does not flood the terminal |

Two of these deserve attention in any redesign.

### The state of `variants` versus `course_progress` (audited 2026-08-27)

**It is done, and the port plan's count was right.** An earlier version of this
section claimed twenty-five outcomes still read `course_progress` and that
converting them blocked the print tool. Both claims were wrong, from grepping
for the token rather than checking whether the value is ever read.

Only **five** generators use it, which is exactly what the port plan said:

| | mechanism | state |
|---|---|---|
| `W4`, `W4-E`, `W5` | `variants = ["no_multiplication", "multiplication"]`, and `progress` derived from `self.variant` | converted |
| `R2` | `variants`, passed as `generate(group=self.variant)` | converted |
| `R1` | branches on `self.seed < PUBLIC_SEEDS`: self-study pool below, assessment pool above | converted, by seed rather than variant |

The other twenty write `course_progress = kwargs.get('course_progress')` and
never read it. That is a dead extraction, not a setting. Seventeen also pass
`mode='html'`, which no `generate()` reads. Both are leftovers from the shims;
both are noise rather than debt.

**So nothing here blocks the print tool.** Printed versions can come from
pregenerated seeds today: every axis that varies content is already either a
`variant` (pregenerated across the seed space, filterable at print time) or a
function of the seed itself.

**The dead arguments are gone** (2026-08-31). Twenty-two generators now call
`generate()` with nothing; `mode='html'` is deleted everywhere, and
`course_progress=6` everywhere it was ignored. Verified as a no-op by capturing
every generator's `data()` across ten seeds and every variant before and after
-- 350 samples, byte-identical -- and confirming the rebuilt `bank.json`
differed only in `generated_on`.

### Four settings that are read and are not yet variants

The audit above covered `course_progress`. Three other spreadsheet settings are
genuinely read, and a fourth is read but unreachable:

| setting | read by | `data()` passes | effect |
|---|---|---|---|
| `w7_allow_terminating` | `W7` | `True`, hardcoded | every pregenerated seed allows terminating decimals |
| `d2_allow_repeating` | `D2` | `True`, hardcoded | every pregenerated seed allows repeating decimals |
| `n3_n4_force_listing_method` | `N3`, `N4` | nothing, so `False` | the listing method is never forced |
| `two_base_ten` | `W2`, `W3` | nothing, so `False` | **also absent from `pdfgenerator.py`'s settings dict, so it is unreachable from either path** |

**Done 2026-08-31 for the first three.** Each is now a variant, dealt across
the seed space by `build_variant_bag`, giving exactly 500/500 and recorded per
seed as `__variant__` so the print tool can select on it:

| outcome | variants |
|---|---|
| `W7` | `no_terminating`, `terminating` |
| `D2` | `no_repeating`, `repeating` |
| `N3`, `N4` | `any_method`, `listing_only` |

Both labels were checked to genuinely change output at the same seed -- 40/40
seeds for `W7`, `N3` and `N4`, 37/40 for `D2`, whose other three pick the
terminating branch either way. A variant that changes nothing is decoration,
and that is worth a check rather than an assumption.

**`two_base_ten` is deliberately left as it was.** `W2` and `W3` read it and the
code behind it stays; it simply keeps its `kwargs.get(..., False)` default
rather than becoming a variant. Nothing has ever been able to set it -- it is
absent from `pdfgenerator.py`'s settings dict -- so making it a variant would
double those outcomes' seed space for a case nobody has asked for. Deleting the
code would throw away work that may yet be wanted.

### `R1` and `R2`'s legacy branches

Both keep a `course_progress` path reachable only from `pdfgenerator.py`, which
passes the kwarg directly. Once the print tool selects variants instead, those
branches become dead. `R1`'s also reads `assets/R1/used_versions.json`, which
makes generation stateful and is deliberately bypassed by the CheckIt path.

> **Method note.** Three counts in this section were wrong before this audit,
> each from a grep that matched a token rather than a use. `grep -l
> course_progress` finds files that mention it; `kwargs['course_progress']` is
> a subscript with a string constant, so an AST walk looking for a *variable*
> of that name misses it too. What settled it was printing every matching line
> and reading them. When a count drives a decision, read the lines.

**Per-student packet assembly is the feature with no CheckIt counterpart.**
Nothing in the platform knows about rosters, per-student skill lists, or
double-sided packet boundaries, and nothing should. This is the print tool's
actual job.

### The conflict: printed seeds cannot come from the published range

The earlier note here said to draw print versions from seeds at or above
`PUBLIC_SEEDS`, "which the viewer does not expose, so students cannot look up
the printed version". **That is wrong, and worth correcting loudly.**

`derived.json` ships in `docs/`, covers seeds `PUBLIC_SEEDS` to `BUNDLE_UNTIL-1`
(50-399 today), and contains the rendered `outtro` — the answers. Verified
2026-08-27. The viewer's *picker* does not offer those seeds, but the file is a
plain fetch away, so a printed quiz drawn from that range is a printed quiz
whose answers are published.

The existing tool sidesteps it by seeding with
`random.choice(range(10000, 100000))` and running the generator directly, so
printed versions exist nowhere else. That was a deliberate delineation, not an
accident — but it is also no longer necessary.

**The unpublished pregenerated range already exists.** Verified 2026-08-27:

| range | where it lives | published? |
|---|---|---|
| 0 - 49 (`PUBLIC_SEEDS`) | inlined in `bank.json`, all three formats | **yes** |
| 50 - 399 (`BUNDLE_UNTIL`) | `derived.json`, html + latex, answers included | **yes** |
| 400 - 999 | `seeds.json` only, data with no rendered formats | **no** |

`build_viewer()` copies `assets/` into `docs/` with
`ignore_patterns("seeds.json", "*.tikz")`, so the seed *data* never ships — only
the two rendered tiers do. Seeds 400-999 are therefore pregenerated,
reproducible, in the bank, and absent from the published site in any form.
**That is the print pool, and no new mechanism is needed to get it.**

That is what the three constants are for, and it is worth stating plainly
because the names do not say it:

- `PUBLIC_SEEDS` — how many versions a student can browse.
- `BUNDLE_UNTIL` — where publishing stops. Everything from here to `--amount`
  is generated but not published.
- `--amount` — how many exist at all. Raise it for more print versions; 1000
  gives 600 unpublished ones today.

The only cost is that seeds 400-999 have no precomputed LaTeX, so the print
tool renders them through `latex.xsl` itself. That is not a real cost: the tool
has the platform installed by definition, and rendering at print time means
stylesheet fixes reach print without regenerating the bank.

**Consequence for the tool's input:** it takes a bank checkout, not a URL. That
follows from wanting unpublished versions and is not a limitation to design
around.

### A fifth answer mechanism: figures

The four table entries above are the ones in `skillcheckpoints.sty`. There is a
fifth, and it is the hardest to fit any vocabulary:

- `\ans{}` **inside a TikZ picture**. F2's number line puts `\ans{$label$}` in
  the axis tick labels and `\ans{\node ... circle}` for the mark itself, so
  turning answers on adds a dot to a diagram rather than any text.
- The generator side does the same thing differently: `tikz_graphics()` emits
  **paired figures**, `p1_prob_model.tikz` and `p1_ans_model.tikz`, and the
  choice is which one to include.

The paired-figure approach is the better one and is already how the web works.
It also means "answers on" is not a single mechanism but a *policy* applied
differently per response type, which is the thing a redesign has to preserve
rather than flatten.

**Do not migrate the inline-TikZ templates yet.** F2, F2-E and F3 carry TikZ
written by hand in `textemplate.tex`, duplicating what `tikz_graphics()` now
produces. Consolidating onto the generator is right eventually, but the HTML
viewer's TikZ output needs tweaks first, and the hand-written code is the only
reference for what the figures should look like. Losing it before the web
version is correct would be losing the specification.

---

## Print-specific appearance, without a second source of truth

### Correcting the obvious first answer

The tempting reading of `latex.xsl` is: it already emits `\stxKnowl`,
`\stxOuttro` and `\stxTitle` rather than layout, so a print theme is just a
`.sty` redefining those, and nothing else is needed. That is true as far as it
goes and it is the right *mechanism* — but it is nowhere near sufficient, and
believing it would throw away most of what `skillcheckpoints.sty` does.

Redefining `\stxOuttro` gets you `ansenv`. It cannot get you `\tfleft`, because
there is nothing in the SpaTeXt for a theme to know that the exercise is a
true/false item. The answer is not a block to hide — it is a choice to
highlight among options that are on the page either way.

**So the gap is vocabulary, and the missing vocabulary is not layout. It is
response type.**

### The line: meaning versus appearance

An element earns a place in SpaTeXt if it asserts something about *meaning*
that each medium then honours differently. It does not if it asserts something
about *appearance on a page*.

Applying that to what the templates currently do:

| | verdict | why |
|---|---|---|
| "this is a true/false item" | **SpaTeXt** | a property of the exercise; the web can render it as a T/F pair too |
| "this answer is short enough to write on a line" | **SpaTeXt** | a claim about the response, not the rule |
| "the rule is 2.25in wide" | theme | pure appearance |
| "the blank sits to the right in a second column" | theme | pure appearance |
| "leave `\vfill` of working space here" | theme | pure appearance |
| "the skill header is a blue rounded box" | theme | pure appearance |
| "this skill's colour is `scCOLOR`" | **bank** | already in `bank.xml`'s `<color_map>` |
| "these characters are Egyptian" | **SpaTeXt** | `<glyphs>`, already done |
| "don't break this equation" | **SpaTeXt** | `<nobreak>`, already done |

The pattern: **the templates are currently mixing all three**, and the reason
`textemplate.tex` has to exist per outcome is that there is no way to say the
first column of that table in SpaTeXt.

### Response type is the missing element

The concrete proposal. SpaTeXt gains a way for a knowl to declare what kind of
response it wants, and each stylesheet renders that its own way:

```xml
<knowl>
  <content><p>Every factor of <m>6</m> is a factor of <m>42</m>.</p></content>
  <response type="truefalse"/>
  <outtro><p>True</p></outtro>
</knowl>
```

- `latex.xsl` emits `\stxTrueFalse{True}{...}`, which the theme defines as
  today's `\tfleft` — including the `\fcolorbox` highlight when answers are on.
- `html.xsl` renders a TRUE / FALSE pair, and the viewer can mark the right one
  when solutions are shown. **The web gets a feature it does not currently
  have**, which is the tell that this is real semantics rather than a print
  workaround.
- `pretext.xsl` has a genuine equivalent in PreTeXt's `<statement>` /
  `<choices>`, so this direction stays open.

Similarly `<response type="short"/>` for the `\fillinblank` cases: print emits
`\stxBlank{answer}` and the theme decides it is a 2.25in rule; the web renders
an input-sized span or simply the answer under the question.

**What this buys.** The per-outcome `textemplate.tex` files collapse from "a
second copy of the exercise" to "nothing at all" for the regular cases, because
the response type now travels in the SpaTeXt and the widths live in the theme.
N1's print template becomes unnecessary: `\stxTasks` + `\stxTrueFalse` from a
theme reproduces it.

**What this does not buy.** Outcomes with genuinely bespoke print layout will
still want a hand-written file. That is fine — see "the escape hatch" below.
The goal is not to eliminate `textemplate.tex`; it is to stop *every* outcome
needing one to express things that are not actually per-outcome.

### The answer machinery, restated so nothing is lost

This is the part to be most careful about, because the requirement is explicitly
that none of the current behaviour is lost. Mapping each mechanism forward:

| today | becomes | who decides what |
|---|---|---|
| `\setboolean{anstoggle}{true}` | `subset='answer'` / `'all'` passed to `latex.xsl` | the **publication** ("this run is a key") |
| `ansenv` | `\stxOuttro`, already emitted | the **theme** (colour, `\vfill` around it) |
| `\ans{x}` | `<outtro>` inline within a `<p>`, or `\stxAns` | the **theme** (colour) |
| `\tfleft[True]{s}` | `<response type="truefalse"/>` → `\stxTrueFalse` | **SpaTeXt** says it is T/F; the theme draws the box |
| `\fillinblank[w]{a}` | `<response type="short"/>` → `\stxBlank` | **SpaTeXt** says short answer; the theme sets the width |

The single `anstoggle` boolean stays exactly as it is inside the theme. What
changes is only that the *decision* to set it arrives as a parameter rather than
as a hardcoded `\setboolean` line, so one source can produce handout and key
without the tool editing LaTeX text.

**Important detail worth preserving deliberately:** `\tfleft` prints TRUE and
FALSE identically whether answers are on or off, and only the box changes. That
property — the handout and the key have *identical layout*, differing only in
ink — is why a key can be laid over a handout and compared at a glance. Any
replacement must keep it. It is also the reason `\fillinblank` reserves its
space unconditionally. **Do not let a redesign turn these into "print the answer
after the question".**

### What is missing in `latex.xsl` regardless

Independent of response types, four gaps stand between today's output and a
theme being able to do anything:

1. **Structure is hardcoded where it should be a hook.** Nested knowls emit a
   literal `\begin{enumerate}` / `\item`; `<list>` emits `\begin{itemize}`. A
   theme wanting `enumitem`'s `label=(\alph*)` — which `skillcheckpoints.sty`
   already sets globally — or `\vfill` between items, cannot get there without
   redefining `enumerate` for the whole document. These want to be
   `\stxTasks{...}` / `\stxTask{...}`, defaulting to current behaviour.
2. **The document cannot say what it is.** Nothing records which outcome or
   which seed a chunk came from, so a theme cannot reproduce
   `\setvseed{\VAR{seed}}` or `\skillheader{N1}` from CheckIt's own output. An
   `\stxExercise{slug}{seed}{...}` wrapper fixes both and costs one template.
3. **`subset` does not exist in `latex.xsl`.** `html.xsl` takes it; `latex.xsl`
   instead always emits `\renewcommand{\stxOuttro}[1]{}` with a comment telling
   a human to delete the line. Same idea, two implementations, two files — the
   shape this codebase keeps paying for. The print tool needs keys, so this has
   to be settled first.
4. **Nothing declares the macros the content needs.** `\babo` and `\textpmhg`
   are not style choices; the document does not compile without them. See
   "Letting a bank declare its own LaTeX preamble".

### The split worth committing to

| | declares | lives in |
|---|---|---|
| **bank** | what the content says; response types; the macros it needs to compile (`\babo`, `hieroglf`); slug, description and colour | `template.xml`, `bank.xml`, and a new preamble declaration |
| **theme** | how `\stxTasks`, `\stxTrueFalse`, `\stxBlank`, `\stxOuttro`, `\stxExercise` render — widths, colours, spacing, the skill box | `skillcheckpoints.sty` — **shipped as the package default, replaced by a copy in the bank root if one exists** (decided 2026-08-31) |
| **publication** | what *this run* wants: handout or key, which outcomes, how many versions, roster, seating, course/semester/professor | a file in the course repo |

`bank.xml` already holds slug, description and colour, and `pdfgenerator.py`
already turns them into `\setskilldesc`. That flow is correct as-is and should
survive unchanged.

The middle column is where `skillcheckpoints.sty` mostly already sits. Most of
its 610 lines — the boxes, the pgfplots styles, the fonts, the header/footer —
are already pure theme and need no change at all. The parts that would move are
the four answer commands, which become definitions of `\stx*` hooks rather than
commands the templates call directly.

### Where the theme lives (decided 2026-08-31)

**The print package ships a default `skillcheckpoints.sty`; a bank may place its
own in the bank root to replace it.** Exactly the convention `tikz.py` already
uses for `tikz_preamble.tex`, so it is one rule rather than two.

Why this rather than the alternatives: shipping it only in the package means a
`pip install --upgrade` silently overwrites an instructor's edits; keeping it
only in each bank means the two banks drift, and today they are byte-identical,
which is worth preserving. Default-plus-override gives upgrades for free to
anyone who has not customised, and full control to anyone who has.

The consequence for the new repo: the 610 lines are **copied in once** as the
package default, and the banks' copies are deleted rather than kept in sync.
A bank re-adds one only when it actually wants to diverge.

### The preamble files, and why there are two

Both are LaTeX; neither has anything to do with HTML as such. They are
different *kinds* of file, which is why they cannot be one:

- **`tikz_preamble.tex`** must contain `\documentclass[tikz,border=4pt]{standalone}`
  — it is a whole document preamble for compiling one figure to PNG, and so it
  serves the **web**. Already supported by `wrapper/tikz.py`, read from the bank
  root, defaulting to `standalone` + `pgfplots`. mat-106 has no custom one yet.
- **The print preamble** is loaded *after* `\documentclass{article}`, which
  makes it a package: a `.sty`.

They overlap in the macros the content needs, so the shape that avoids
duplicating those is a third, shared file:

```
bank_helpers.sty      macros the CONTENT needs: \babo, hieroglf, \rnc, \arc
                      no \documentclass, no layout

tikz_preamble.tex     \documentclass[tikz,border=4pt]{standalone}
                      \usepackage{bank_helpers}   <- shared macros
                      \usepackage{pgfplots}    <- figure-only extras

skillcheckpoints.sty  \usepackage{bank_helpers}   <- the same shared macros
                      ...layout, boxes, \stx* hooks
```

Both consumers import the shared piece rather than one importing the other. A
figure compile must **not** inherit page geometry, `fancyhdr` or the `\stx*`
hooks — it is a borderless standalone — and the print document cannot inherit
`\documentclass{standalone}`. Override still works: `tikz_preamble.tex` is a
whole file the bank controls, so it can load `bank_helpers.sty` and then change
anything.

### The escape hatch, and why it is not a failure

**`textemplate.tex` should not be abolished.** Some outcomes will want layout no
vocabulary will ever capture, and the promise "you can always drop to LaTeX for
one outcome" is worth more than purity. The design that keeps both:

- If an outcome has a `textemplate.tex`, the print tool uses it, exactly as
  `pdfgenerator.py` does today. Nothing breaks on day one.
- If it does not, the tool renders the SpaTeXt through `latex.xsl` and the
  theme. New outcomes cost one template instead of two.
- Outcomes migrate one at a time, when someone touches them anyway.

That also means **this work can start without migrating anything**, which is the
main reason to prefer it. The first version of the print tool is
`pdfgenerator.py` cleaned up and packaged, reading `seeds.json` instead of
importing generators, with the theme and templates carried across unchanged.
Response types come afterwards, one outcome at a time, and each migration is
verifiable by diffing a PDF against the old one.

### On the PreTeXt analogy

The instinct is right and worth stating precisely. PreTeXt's separation is
*source* (what the mathematics is) from *publisher file* (how this particular
publication renders it), so one source serves many outputs without the author
choosing an output. That is the model.

Where CheckIt differs, and should: PreTeXt's publisher file is large because it
targets many formats with deep customisation of each. This needs one output
format done well, and it has something PreTeXt does not — a **theme in the
target language itself**. A LaTeX `.sty` is a far better customisation surface
for a LaTeX document than any options schema, because the instructor already
knows LaTeX and can change anything without the tool anticipating it.

So: take PreTeXt's *split*, not its publisher-file design. Keep the publication
file small — the settings that vary per course, which today are the four
`\VAR{}`s in `main_template.tex` (`course`, `semester`, `professor`,
`full_title`) plus roster and seating — and let the theme be a file you edit.

**"The theme is just a file you can edit" is a better promise than any options
schema**, and it is the one thing here that must not be traded away for
tidiness.

### Open, and deliberately unanswered

- The eventual goal is a GUI replacing much of the current Google Sheet: pull
  responses from Google Forms directly, set up the form and sheet for a new
  course, and drive printing. That makes the existing CSV-scraping code
  throwaway, so it is not worth porting carefully.
- Whether the key is a second compile of the same source with `subset='answer'`
  (simple, matches `html.xsl`) or one compile emitting both (keeps version
  numbering trivially consistent). `pdfgenerator.py` currently does the former,
  in the same document.
- Whether print draws from `derived.json` (pre-rendered, no XSLT at print time)
  or re-renders from `seeds.json` (slower, picks up stylesheet fixes without
  regenerating). `BUNDLE_UNTIL` caps the pre-rendered range at 400, so a run
  wanting more versions than that has already answered this by force.
- Whether `<response>` is one element with a `type` attribute or several
  elements. The attribute reads better in the XML; separate elements are easier
  to give distinct content models to later (a `truefalse` has no answer text
  beyond the value, a `short` does).

## Upstream 0.2.9 merged: MCQ support (2026-09-02)

Eleven upstream commits, one feature. Fork version is now **0.2.9.1**.

### What MCQ is

A distractor is an extra `<outtro>` carrying `distractor="true"`:

```xml
<outtro><p><m>2x</m></p></outtro>
<outtro distractor="true"><p><m>5x</m></p></outtro>
```

`html.xsl` renders every outtro and stamps `data-distractor` on the wrong
ones; the viewer lists them as lettered choices; the Canvas export builds a
`multiple_choice_question`. `CheckIt.choices_from_list()` shuffles a list whose
first element is correct.

### It is experimental, and print is the gap

Upstream's own UI says "(experimental)". Rendering an MCQ through each
stylesheet shows why:

| | |
|---|---|
| `html.xsl` | all choices, distractors marked |
| `latex.xsl` | **choices dropped** -- `stx:outtro[not(@distractor='true')][1]` |
| `pretext.xsl` | **choices dropped**, same selector |

So a printed MCQ is the prompt plus the correct answer, with nothing to choose
between. For the print tool the feature does not exist yet. Fixing it means
deciding how a paper MCQ should look -- lettered list, blank for the letter --
which is a `skillcheckpoints.sty` question as much as a stylesheet one.

Smaller gaps, all upstream's and all worth sending back rather than diverging
over:

- `Knowl.svelte` tests `distractor='true'].length > 1`, so an MCQ with a single
  distractor renders no choice list. `> 0` is presumably meant.
- `choices_from_list` assigns a `letter` to each choice that no template uses.
- Canvas only; the Brightspace and Moodle paths are untouched.

### What the merge needed

- **`choices_from_list` was Sage-only.** Ported to `wrapper.py`, or no
  plain-Python generator could author an MCQ -- and plain Python is this fork's
  default runtime.
- **EX4 arrived as `generator.sage`**, the only `.sage` left in demo-bank.
  Ported: `Add(a*x, b*x, evaluate=False)` for `(a*x).add(b*x, hold=True)`.
- **`viewer/src/spatext/xsl/*` stayed deleted.** Upstream still transforms
  SpaTeXt in the browser and edited its copies; this fork removed them in
  August. Their edits are already in `dashboard/checkit/static/`, which merged
  cleanly. **Expect this every time upstream touches a stylesheet** -- it is a
  translation, not a conflict git can resolve.
- **`html.xsl` took both sides**: this fork's `$subset` guard, and upstream
  dropping `[1]` so every outtro renders.

### Two traps worth remembering

**`git stash` during a merge destroys `MERGE_HEAD`.** Committing afterwards
produces an ordinary commit with one parent that *looks* finished: the tree is
right, the tests pass, and git no longer knows upstream was merged -- so the
next merge re-conflicts on all of it. Check `git log -1 --format=%P` shows two
parents, or `git merge-base --is-ancestor upstream/main HEAD`. Recovered here
with `git commit-tree <tree> -p <ours> -p <theirs>`.

**`checks.py` `missing-data` is scope-blind.** It computes
`referenced - set(exercise.data.keys())` against *top-level* keys, so any
variable inside a Mustache section resolving to a nested dict is a false
positive. The demo bank reports 10 findings for this reason -- IMG1's
`{{slope}}` lives inside `{{#findfunction_line}}`, XML's `{{f}}` inside its own
section. The banks are correct; the check is not. Nothing was wrong on mat-106,
which has no section-scoped variables, so this never showed there.

## Where we paused (2026-09-02)

Everything below was decided in conversation and is not yet built. Recorded so
picking it back up costs nothing.

### The seating/records GUI: agreed shape, not started

**A local web app with a Python backend**, not a desktop toolkit and not Godot.

The privacy constraint that seemed to rule out a browser does not: it rules out
*hosting*. A page served from `127.0.0.1` publishes nothing, and student data
stays in local files exactly as it does now. Bind to `127.0.0.1` and never
`0.0.0.0`, which would put names on the campus network.

Reasons the browser wins here, in order of weight:

1. The data model is already Python. `checkit_printit` reads banks, resolves
   seeds, applies selection modes, orders seating around pins. A GUI in another
   language reimplements that or talks to it over IPC.
2. Draggable desks on a rearrangeable canvas is the hardest requirement, and
   the browser is the best-documented environment for it.
3. Editable tables are nearly free in HTML and painful in Qt.

Rejected, with reasons: **Godot** solves the canvas and nothing else — no
tables, no forms, no TOML, no access to the Python that reads the bank.
**Tkinter** has no table widget and you write your own hit-testing. **PySide6**
is the serious alternative and `QGraphicsScene` is genuinely good, but it costs
a ~100MB dependency and Windows packaging pain. **Flet/NiceGUI** are web UIs
underneath, so they are the same answer with the JavaScript hidden — until a
custom drag canvas, where the abstraction thins and you write it anyway.

**Storage, which is the part to get right:**

| | |
|---|---|
| `publication.toml`, `roster.toml`, `seating.toml` | stay the source of truth; the GUI edits these files rather than replacing them |
| desk x/y positions | new data, but it belongs in `seating.toml` |
| tracking records | **SQLite** — append-heavy, machine-written, queried by date/student/skill |

A GUI that writes TOML means the CLI and the GUI can never disagree and
everything stays in git. A GUI with its own state file would break that.

**Not a decision yet:** `pywebview` puts the same frontend in a native window
with no browser chrome and no open port, for ~2MB and a few lines. So "local
web app" and "desktop app" are not a fork in the road — the second wraps the
first. Build the frontend; choose the shell later.

**First slice, in order:** `checkit-printit gui` serves `seating.toml` as
read-only desks; then drag-to-swap writes the file back; then confirm
`checkit-printit build --preview` reads it unchanged. That last step is the
real test — if the GUI's output is a file the CLI already understands, the
whole thing is additive and nothing can drift.

### Spacing: a `<workspace/>` element, designed but not built

PreTeXt's answer is a `@workspace` **attribute** on an `<exercise>` inside a
`<worksheet>`, in absolute units (`workspace="1.25in"`), treated as a minimum
and distributed proportionally. It has **no `\vfill` equivalent** —
[issue #2207](https://github.com/PreTeXtBook/pretext/issues/2207) is an open
request for exactly the relative spacing mat-106 already uses everywhere.

For SpaTeXt an **element** beats an attribute: an attribute means "this thing
gets space after it" and cannot say "put space *here*, between these two items".

```xml
<workspace/>                  <!-- \vfill: take what is left -->
<workspace height="1.5in"/>   <!-- \vspace: a minimum -->
```

Supporting both spellings puts this ahead of PreTeXt rather than behind it.

**Make it block content, allowed wherever `<p>` is allowed.** That is the whole
design decision. A direct child of `<knowl>` would have to sit *between*
`<content>` and `<outtro>`, and all three stylesheets process those by fixed
name in fixed order, so placing something between them means rewriting the
knowl template three times to walk children in document order.

Work, now that the code has actually been read:

| | |
|---|---|
| `latex.xsl` | one template, plus `\|stx:workspace` in the select lists |
| `html.xsl` | name it and emit nothing, so "dropped on purpose" is distinguishable from "forgotten" |
| `pretext.xsl` | same. `@workspace` cannot be emitted meaningfully: this stylesheet produces a bare `<exercise>` with no `<worksheet>` around it, so whether the attribute is legal depends on where the author pastes it |
| the viewer | **nothing.** `ContentNodes.svelte` is an `{#if}` chain with no `{:else}` and already ignores what it does not know |
| subset filter | nothing, given the block-content decision |

**Prototype on W2 first.** Its two templates differ by nothing but
`\vspace{20pt}` and `\vfill`, so it either drops its print template cleanly or
names what is missing, before twenty others are touched. The known gap is space
*after* the answer, which W2's trailing `\vfill` provides today.

### MCQ: leave it alone until upstream finishes

Decided 2026-09-02. Upstream's MCQ is a first pass and its own UI says
"experimental". The three gaps found — a two-choice MCQ rendering no choices,
an unused `letter` field, Canvas-only export — are **not** to be fixed here.
Wait to see the full implementation.

The larger idea: the eventual move may be to **port MCQ's approach onto the
true/false items**, which N1 and D3 already have in bespoke form via
`\tfleft`. A distractor is just an extra `<outtro>`, and a true/false item is a
two-choice MCQ, so one mechanism could serve both. Not started, and it depends
on what upstream settles on.

Note that **print is where MCQ stops**: `latex.xsl` and `pretext.xsl` both
select `stx:outtro[not(@distractor='true')][1]`, so a printed MCQ is the prompt
plus the correct answer with nothing to choose between.

### Upstream contribution strategy

Agreed posture: **build first, show later.** A previous feature request — that
generators be able to see their seed — was refused on design grounds, and that
refusal is diagnostic rather than arbitrary. It maps to one specific boundary,
the **generator contract**: CheckIt rests on "any seed is as good as any other",
which is what makes a seed range interchangeable and a version reproducible from
a number. `self.seed` breaks that invariant invisibly. This fork sets it anyway
(`roll_data()`), so the fork is *already* not back-portable in whole. The
realistic goal is not "stay mergeable" but "keep sending back what is sendable".

**Four unarguable bug fixes to send when convenient**, each with a reproducible
failure and no design decision for the maintainer to make:

- `pretext.xsl` wrapping tasks in an extra `<task>` — emits invalid PreTeXt for
  every multi-part exercise
- `latex.xsl` not bracing a `<glyphs>` `@latex`, so a `\Large` runs to the end
  of the document
- `-o` not repeatable, silently regenerating outcomes the user did not name
- `update_viewer.py` assuming `python` and `npm` are literal executable names

Two more are upstream's own, found in the MCQ merge: `Knowl.svelte`'s
`> 1` off-by-one, and the unused `letter`.

**The GUI is structurally the safest thing to build** with an eye to
upstreaming: almost entirely new files, which never conflict on merge, and it
goes nowhere near the generator contract. If it is ever proposed, keep the
upstream half to exactly what the deprecated Jupyter dashboard did — preview,
generate, generate with graphics, build bank, build viewer — because a narrow
replacement is far easier to accept than a new feature. Note that
`html_preview()` and `preview_exercises()` in `outcome.py` are used by nothing
but that deprecated dashboard, so core already carries a GUI-support API with no
live consumer.

**History worth knowing:** the Jupyter GUI was built in 2021 (issue #30). On
2026-05-20 four commits landed in one day — "setup devcontainer and start work
on checkit cli" through "flexible cli commands" — and v0.2.7 the next day
deprecated the dashboard with "we recommend using Codespaces/CLI". Read that as
the GUI being collateral of adopting Codespaces rather than a verdict on GUIs.
Two dashboard issues (#34, #49) are still open. Expect "Codespaces already
handles onboarding" as the first objection, and answer it with the local-first
instructor who has no GitHub account.

### One loose end

**The unreleased wheel.** Source is `0.2.9.1`; the newest published wheel is
`v0.2.8.5`, and both banks' `requirements.txt` pin that URL. Local work is
unaffected because this machine uses an editable install, but a fresh clone of
mat-106 gets a CheckIt without the glyphs brace fix, the pretext task fix, the
repeatable `-o`, the `missing-data` section fix, or MCQ. Cut a `v0.2.9.1` wheel
and update both banks' `requirements.txt` when convenient.

## Local divergences from upstream StevenClontz/checkit

This fork diverges from upstream in these deliberate ways. Recorded so an
upstream merge doesn't silently revert them:

- **TikZ image backend** — new wrapper/tikz.py; tikz_graphics() added to
  BaseGenerator in wrapper.sage; <tikz-image> rule added to all three XSLTs
  (at the time, both the dashboard/checkit/static/ and viewer/src/spatext/xsl/
  copies; only the former exists now);
  image_amount cap in wrapper.sage. NOTE: the rule alone is not enough — the
  `parseDisplay` template in each stylesheet must also list `stx:tikz-image` in
  its `apply-templates select`, or the rule is dead code and the element renders
  as nothing. (This was initially missed; watch that an upstream merge of the
  XSLTs keeps `|stx:tikz-image` in all six `parseDisplay` selects.)
- **TikZ in the interactive viewer** — `<tikz-image>` is wired into the Svelte
  display path: `ParagraphNodes.svelte` has a `tikz-image` case, and
  `outcomeToStx` (utils/index.ts) stamps `@remote` on `image, tikz-image`.
  Without these, TikZ figures render only in the html/latex/pretext export tabs,
  not in the default display mode.
- **Bank helper modules + `self.seed`** — `load_generator()` appends the
  generator's folder and the bank root to `sys.path`, so a bank can share code
  via `bank_helpers.py` (scaffolded by `checkit new`) instead of `runpy` tricks;
  and `roll_data()` sets a plain `self.seed` so `data()` can branch on which
  version it is producing. Demo outcomes CURATED and WORDS cover both.
- **Plain-Python generator runtime** — `wrapper/wrapper.py` (SymPy-backed)
  alongside the untouched `wrapper.sage`; the generator's file extension selects
  which runs (`RUNTIMES` in `wrapper/__init__.py`, resolved by
  `Outcome.generator_path()`). `sage()` renamed `run_generator()`. `sympy` added
  to `install_requires`, `matplotlib` as a `[plots]` extra. All eight demo
  generators ported to `.py`, so upstream's `.sage` versions are gone here.
  Authoring no longer needs a container. See "Generator runtimes" for the three
  silent Sage-isms an upstream merge could reintroduce (`^`, `==`, `1/3`).
- **update_viewer.py Windows portability** — uses `sys.executable` rather than
  the literal `"python"`, resolves `npm` via `shutil.which` (it is `npm.cmd` on
  Windows), and passes `check=True` so a failed generate stops the build instead
  of silently publishing an empty demo site.
- **TikZ packages in the assessment preamble** — `viewer/src/templates/`
  `assessmentTemplate.tex` loads `tikz` and `tkz-euclide` alongside `graphicx`.
  Without them the LaTeX output's `\input{<source>.tikz}` hits an undefined
  `\begin{tikzpicture}` and *every* assessment containing a TikZ exercise fails
  to compile. This can't be fixed in latex.xsl: its root template is emitted
  per-exercise inside the document body, where `\providecommand` is legal but
  `\usepackage` is not. Note the seam — `tikz` belongs to the platform (it has a
  `<tikz-image>` element, so its template should support one), but
  `tkz-euclide` is *demo-bank's* choice and should not be pushed onto every
  CheckIt user. Upstreaming this means sending the `tikz` line only, or building
  the bank-declared preamble channel described below.
- **"Copy for AI Chatbot" button** — student-facing button in
  `routes/Outcome.svelte`, payload built by `outcomeToAiText()` in
  `utils/index.ts`; new optional `<ai-prompt>` element in `bank.xml` (bank-level
  with per-outcome override), parsed by the new `xml.optional_text()` helper and
  carried to the viewer as an `ai_prompt` key on both `Bank.to_dict()` and
  `Outcome.to_dict()`. `types.ts` gains matching optional fields. See §12; note
  the `ai_prompt` key is the first thing a bank declares that the viewer reads
  at runtime, so it is also the template for the bank-declared LaTeX preamble.
- **image_seeds option** — added to the CLI generate command and threaded
  through Bank/Outcome.generate_exercises, sage(), and compile_tikz_for_outcome().
  Caps *rasterization only*; `.tikz` source is always written (see §12).
- **tikz.py robustness** — judges pdflatex success by PDF existence (not exit
  code, since pgfplots can exit non-zero on recoverable warnings); a
  COMPILE_TIMEOUT backstop converts stuck compiles into bounded, reported
  errors (empirically, neither stdin=DEVNULL nor batchmode prevents the stall
  on a malformed figure — the timeout is the real protection).
- **tikz.py incrementality** — `compile_tikz_for_outcome()` takes an
  `image_seeds` cap and skips any figure whose `.png` is already no older than
  its `.tikz`, printing a `compiled N / skipped M` line so the skip is visible
  rather than silent. Previously it walked every seed directory and recompiled
  unconditionally on every call, so a 20-seed preview after a 1000-seed build
  paid ~30 minutes of pdflatex. A failed compile leaves no PNG, so failures
  always retry. The cap reads the seed number from the directory name
  (`f"{seed:04}"`); a non-numeric name raises rather than silently rasterizing
  the wrong subset — relevant if wrapper.sage's unused `random` seed mode is
  ever enabled, since seed numbers would stop matching loop indices.
- **load_exercises() fix** — added the missing `return` on the cached path so
  the cache-skip optimization actually fires (upstream likely still has this
  no-op; watch on merge).
- **Custom TikZ preamble** — tikz.py loads tikz_preamble.tex from the bank root
  if present, else uses a built-in default.

## Codespace / devcontainer notes

> **The container is no longer required.** It existed for exactly one reason — SageMath does not run natively on Windows — and as of 2026-08-04 the default generator runtime is plain Python + SymPy. The whole pipeline, including `generate`, TikZ compilation, the viewer build and `build_docs.py`, has been run end to end on a Windows host with no Sage installed. See "Generator runtimes" above.
>
> The devcontainer still installs SageMath and could be slimmed considerably, or kept as the "full" environment for anyone who wants the optional Sage runtime available.

- The devcontainer installs a current TeX Live (2026) from upstream tlnet (scheme-infraonly + tlmgr), NOT Debian's apt texlive (which is 2019 and too old for current tkz-euclide/tkz-elements). Add LaTeX packages by extending the tlmgr install list in .devcontainer/setup.sh.
- poppler-utils (pdftoppm) is installed via apt in setup.sh.
- TikZ compilation currently lives in wrapper/. Revisit whether image-rendering backends deserve their own package once PreFigure is added (premature now with only one such file).

---

# Appendix A: closed decisions

Everything below is **finished**. The decision was made, the work landed, and
nothing here tells you what to do next -- it is kept because the reasoning is
harder to reconstruct than the code, and because two of these were re-litigated
once already before anyone found the note.

If you are looking for what to work on, this is the wrong end of the file:
see "Where things stand".

## Packaging

### Why the fork version is `0.2.8.N` and not `0.2.8+slye.N`

The fork needs a version distinct from upstream's, or `pip show
checkit-dashboard` cannot tell you which one is installed.

`0.2.8+slye.1` is the semantically correct form — a PEP 440 *local version*
means precisely "this upstream release plus local changes" — and it does not
survive GitHub. Uploading
`checkit_dashboard-0.2.8+slye.1-py3-none-any.whl` to a release rewrites the `+`
to `.`, and pip then refuses the stored file outright:

```
ERROR: Invalid wheel filename (invalid version):
'checkit_dashboard-0.2.8.slye.1-py3-none-any'
```

The wheel would have been undownloadable-by-pip from the only place it is
published. Hence `0.2.8.1` — digits and dots only, which passes through
unchanged. `test_packaging.py` asserts the version contains no `+` and differs
from upstream's `0.2.8`.

> **Principle.** A version string is also a filename, and filenames pass through
> systems that rewrite characters. Anything that has to survive that round trip
> should stick to the least expressive form that works.

### The sympy bug, and why it hid for months

`setup.py` duplicates `install_requires` "for GitHub's dependency graph", and
**setuptools uses setup.py's copy**, because a `setup()` keyword overrides
`setup.cfg`. `sympy` was added only to `setup.cfg` when the plain-Python
generator runtime landed. Every wheel this repo produced therefore shipped
without it, and a clean install could scaffold a bank and then fail to generate
a single exercise with `ModuleNotFoundError: No module named 'sympy'`.

It was invisible here because the development environment is an *editable*
install into a venv that already had sympy — nothing ever exercised the
dependency list. It took building a wheel and installing it into a fresh venv
to see it, which is not something anyone does by accident.

This is the same shape as the duplicated stylesheets and the duplicated
`PUBLIC_SEEDS`: one idea, two copies, no enforcement. `test_packaging.py` now
asserts the two lists agree.

## The XSLT migration (2026-08-20 to 2026-08-21)

Browsers dropping XSLT forced the viewer off in-browser transforms and onto
precomputed formats. The deadline and the still-open questions live in
"Browsers are removing XSLT"; the measurements and the decision are here.

### The two implementations are not equivalent (verified 2026-08-20)

The three stylesheets are byte-identical across `dashboard/checkit/static/` and
`viewer/src/spatext/xsl/` — `diff` is clean on all three, so the hand-sync
discipline has held so far. The *calling code* is another matter, and it
diverged without either copy of the `.xsl` ever changing.

**`subset` and `consumer` are dead parameters.** `Exercise.html_ele()` and
`Exercise.pretext_ele()` pass `subset` and `consumer` into `etree.XSLT(...)`,
but no stylesheet declares an `xsl:param` and neither name appears anywhere in
any `.xsl`. They are accepted and silently ignored — a textbook instance of
the silent-failure pattern, sitting in the public API of `Exercise`.

This is a **regression, not an unfinished idea**, and the history matters
because it says the feature is recoverable rather than hypothetical:

- `ccc9b09` (Jan 2022) added `<xsl:param name="subset"/>` and
  `<xsl:param name="consumer"/>` to `html.xsl`, with `$subset` gating
  statement/answer output and `$consumer='canvas'` branching for the LMS.
- `fde75e8` (May 2022, "update spatext") rewrote all three stylesheets and
  dropped the params — while leaving the Python call signatures behind.
- `4b48149` ("housecleaning") deleted `xsl/canvas.xsl`, `xsl/brightspace.xsl`
  and the LMS manifest templates.

So parameterized, LMS-aware, server-side rendering **used to exist here**. The
browser's JS filtering is a later re-implementation of a capability lost in a
rewrite. The duplication is not a design decision anyone made; it is drift.

**What the browser does that Python currently cannot.** `outcomeToHtml()` takes
`mathMode` and `solutions` and applies both *after* the transform, by DOM
surgery: stripping `[class~="stx-outtro"]` / `stx-intro` / `stx-content` for
`hide` and `only`, and running KaTeX to MathML for `canvas`/`brightspace`.
`Exercise.html()` has no equivalent for either and can only produce the
`all`/`basic` form.

The `latex2mathml` import in `exercise.py` is the other half of the same lost
feature: `tex_to_mathml()` is defined, never called, and `latex2mathml` is still
a hard install dependency. Commit `51507be` names the gap it was meant to fill.

**Consequence for option 1 below:** "the Python layer already performs exactly
these three transforms" is true of the *transform* and false of the *feature*.
Precomputing requires restoring subset filtering and adding server-side MathML
first. `ccc9b09` is a known-good reference for the first.

### Measured sizes (2026-08-20)

Rendering every demo outcome to all three formats and comparing against its data
JSON:

```
per seed, all 10 outcomes:  data 1,883   html 8,636   latex 5,895   ptx 5,615 bytes
three formats / data     =  10.7x
```

`docs/demo/assets/bank.json` is 1.49 MB (10 outcomes x 1000 seeds, data only).
Inlining all three formats for every seed would take it to roughly **16 MB**,
downloaded by every visitor on load. HTML alone is ~4.6x, still ~7 MB. A blanket
inline is therefore out, as previously assumed — but the consumers do not all
want the same seeds, and that asymmetry is the opening:

| surface | formats | seeds | source |
|---|---|---|---|
| instructor tabs | html, latex, ptx | 0 to PUBLIC_SEEDS-1 | `Exercise.svelte` |
| Copy for AI Chatbot | html | 0 to PUBLIC_SEEDS-1 | `outcomeToAiText` |
| assessment builder | latex | PUBLIC_SEEDS-999 | `getRandomAssessmentFromSlugs` |
| LMS export | html x2 (hide + only) | 100-999 | `Export.svelte` (`Array(900)`, `seed=i+100`) |

PreTeXt is **only ever needed for the public seeds**, which is the one clean
saving available.

**Measure the payload compressed, not raw.** An earlier version of this section
said inlining the public seeds at `PUBLIC_SEEDS` = 50 costs "~1.0 MB, a 65%
increase", and concluded it was no longer affordable. That figure was raw JSON
bytes, which is not what a visitor downloads. Measured on the live site
(2026-08-21, `performance.getEntriesByType('resource')`):

```
decodedBodySize (uncompressed): 1,420,295 bytes
transferSize    (over the wire):  152,441 bytes
compression ratio: 9.3x            download: 168 ms
```

`bank.json` is overwhelmingly repetitive -- the same tags, slugs and LaTeX
fragments over and over -- so it compresses about tenfold, and precomputed HTML
is *more* repetitive still. Rebuilding the published demo bank with seeds 0-49
inlined:

| inlined | raw | gzipped |
|---|---|---|
| nothing (today) | 1.42 MB | 148 KB |
| html only | 1.81 MB (+28%) | 163 KB (+10%) |
| html + latex | 2.07 MB (+46%) | 173 KB (+17%) |
| all three formats | 2.33 MB (+64%) | **180 KB (+22%)** |

So the honest cost of the full inline tier is about **32 KB more over the
wire**, on a request that currently takes 168 ms. That is affordable, and the
earlier warning was wrong. A course bank has roughly 3x the outcomes of the
demo, so expect roughly 3x these figures and still well under a megabyte.

Two costs compression does *not* remove, and neither is a blocker: the browser
still parses the full uncompressed JSON (2.33 MB rather than 1.42 MB) and holds
it in memory, and the raw file still occupies disk in the bank repo. Note also
that `docs/**` is committed here, and generated files are marked `binary` in
`.gitattributes` for good reason (see the corrupt-merge incident) -- a
3x-larger generated JSON makes that more important, not less.

> **Principle.** For anything served over HTTP, "how big is the file" is the
> wrong question; "how many bytes cross the wire, and how long does that take"
> is the right one. They differ here by a factor of nine, which is more than
> enough to reverse a decision.

Also worth knowing: the LMS export calls `outcomeToHtml` twice per seed across
900 seeds, so **1,800 transforms per outcome per export**, on the main thread.
Precomputing that surface is a performance win regardless of the deprecation.

### The options that were weighed

1. **Precompute the derived formats at generate time (recommended).** The Python
   layer runs these same three transforms via `lxml` (`Exercise.html()` /
   `.latex()` / `.pretext()`). Emit them at build time and have the viewer fetch
   rather than transform. Requires first restoring the `subset` filtering and
   server-side MathML described above — real work, not a rename.

   The strong argument is not the deadline. It is that the transforms exist
   **twice**, which is why the three stylesheets are duplicated and must be kept
   in sync by hand (§5), and which is what produced the document-vs-element
   bug: the browser path silently required a different source node type than the
   Python path, and only Firefox ever said so. Precomputing collapses two
   implementations into one.

2. **Replace browser XSLT with a JS/WASM implementation** (a libxslt WASM build,
   SaxonJS, or hand-porting the stylesheets to TS). Keeps transforms
   client-side, so no payload or seed-range design is needed, and it is the
   smallest behavioral change. But it adds a dependency and *preserves* the
   dual-implementation problem that caused the bug — it buys time without
   buying simplification.

3. **Drop derived formats from the browser entirely**, moving export to the CLI.
   Smallest amount of code, largest loss of function for instructors.

### The recommendation, and what was built

**Option 1, staged, with a two-tier payload. Not a hybrid with option 3.**

The temptation is to send the heavy surfaces (assessment builder, LMS export) to
the CLI and precompute only the cheap ones. Resist it. Those browser surfaces
are what the platform is *for* from an instructor's point of view, and a
CLI-only export is a real downgrade for the audience least likely to want a
terminal. The reframe that makes this tractable: **"in the browser" is a claim
about the instructor's experience, not about where the transform executes.** The
button stays, the download stays, the copy-to-clipboard stays. Only the compute
moves to build time. Nothing an instructor can do today is lost.

Sequence, in dependency order:

1. **Restore server-side parity first, while browser XSLT still works.** Port
   `$subset` back into the three stylesheets from `ccc9b09`, and wire
   `tex_to_mathml()` in for the `canvas`/`brightspace` consumer. Do this
   *before* touching the viewer, because until 2026-11-17 you can render the
   same seed both ways and diff them — the browser is a free oracle for
   verifying the Python output. **That verification window closes on the removal
   date**, and afterwards there is nothing left to check the port against. This
   is the step with a real deadline; the rest is ordinary work that can happen
   whenever.

2. **Emit precomputed formats at generate time, in two tiers.** Inline the
   public seeds (all three formats) into `bank.json` — that alone fixes the
   instructor tabs and the AI button with no new fetch machinery, and costs
   about 32 KB more over the wire (see the payload measurements above). Emit
   the heavy ranges as per-outcome bundles under `assets/<slug>/generated/`,
   fetched lazily only when an instructor actually clicks Assessment or Export.
   The ranges differ per surface, so a partial precompute reintroduces the
   coverage trap from `--image-seeds` (§ image_seeds): decide the range
   policy *before* writing the emitter, and make a missing range fail loudly
   rather than render blank.

3. **Switch the viewer to read, then delete.** Replace the three
   `XSLTProcessor` calls in `utils/index.ts` with lookups, then delete
   `viewer/src/spatext/xsl/` outright. One implementation of the transforms
   remains, in `lxml`, and §5's hand-sync requirement disappears with it.

Two things to design rather than default:

- `bank.json` becomes a compatibility surface. A bank generated by an older
  CheckIt will not carry the precomputed keys, and the viewer must say so rather
  than render an empty tab — the same concern recorded for `<ai-prompt>` and
  for the bank-declared LaTeX preamble.
- Build time grows by 1000 seeds x 3 transforms per outcome. Expect the same
  staleness pressure `compile_tikz_for_outcome` already has, and plan to skip
  unchanged outcomes rather than discovering the cost after the first full run.

What this does *not* solve: the assessment `.tex` template is still baked into
the bundle at build time (see "Letting a bank declare its own LaTeX preamble"),
and that remains an independent problem.

### Step 2: the emitter

**Only `XSLTProcessor` disappears.** This is the realisation that shrank step 2,
and it is worth stating plainly because it is easy to assume the whole of
`outcomeToHtml()` is at risk. It is not: `DOMParser`, `querySelector`,
`katex.render` and the class-based node removal all survive the deprecation
untouched. The viewer therefore needs only the **base** rendering precomputed
— `subset='all'`, `consumer='basic'` — and can keep applying its own
`solutions` filtering and LMS MathML on top of it.

Emitting every `subset` x `consumer` combination instead would have multiplied
the payload roughly fourfold to replace code that still runs. It would also have
been slower to build and no safer.

That leaves the server-side `subset` and `consumer` support from step 1 off the
critical path for the viewer migration. They are not wasted — they are what a
CLI export would use, and building them is what produced the tested oracle
proving the two filtering implementations agree — but the honest description
is that step 1 was scoped slightly wider than the migration strictly required.

**The coverage policy, decided before the emitter was written.** The ranges are
unequal, and unequal coverage is exactly the trap `--image-seeds` set once:

| tier | formats | seeds | where |
|---|---|---|---|
| inline | html, latex, pretext | 0 to `PUBLIC_SEEDS`-1 | inside `bank.json` |
| bundle | html, latex | `PUBLIC_SEEDS` to end | `assets/<slug>/generated/derived.json` |

PreTeXt is absent from the bundle deliberately: its only consumer is the
instructor tab, and the version picker cannot reach past `PUBLIC_SEEDS`, so it
would be dead weight for 950 seeds per outcome.

The policy is **declared in `bank.json`** under a `precomputed` key rather than
left implicit, so a consumer can ask "was this emitted?" instead of inferring a
hole from rendering nothing. A bank generated before this exists has no such
key at all, which is how the viewer will tell "not precomputed" from
"precomputed but missing this seed".

**Measured cost** (published demo bank, 8 outcomes x 1000 seeds):

- inline tier: `bank.json` 1.42 MB -> 2.33 MB raw, but 149 KB -> 180 KB over
  the wire, because it compresses about tenfold
- bundle tier: ~1.4 MB raw per outcome, ~51 KB over the wire (this content
  compresses about 28x), fetched only when an instructor acts
- on disk a 31-outcome course bank grows by ~44 MB of generated files. Banks
  gitignore `assets/**/generated`, so that lands in the repo only once
  published under `docs/**`, where git's own compression absorbs most of it.

**`--remote` is now required when a bank has images.** Precomputed HTML has to
carry absolute `<img src>` values, and the check runs *before* anything is
written so a build fails at once rather than several minutes in, and names the
offending outcomes. `--no-precompute` skips the whole thing and also deletes any
stale bundles, so `bank.json` never says "not precomputed" while old bundles sit
beside it.

### Step 3: the viewer reads what the emitter wrote

`utils/index.ts` no longer contains the word `XSLTProcessor`, and
`viewer/src/spatext/xsl/` is gone. **The three stylesheets now exist once**, in
`dashboard/checkit/static/`, and §5's hand-sync requirement is retired. The
bundle shrank 603.6 KiB → 588.3 KiB, which is the inlined stylesheets leaving.

How it reads:

- `outcomeToLatex` and `outcomeToPtx` return the stored string directly.
- `outcomeToHtml` parses the stored base HTML with `DOMParser` as `text/html`,
  then applies its existing `solutions` filtering and LMS MathML. Those were
  never XSLT and did not need replacing.
- Seeds at or above `inline_below` need their outcome's bundle, so the
  assessment builder and the LMS export `await ensureDerivedForSlugs(...)`
  before rendering. One await at the top of each keeps every builder below it
  synchronous. Bundles are fetched at most once per outcome and cached.

**An old bank refuses rather than falling back.** A bank with no `precomputed`
key gets a message naming the command to run. The alternative — keeping
`XSLTProcessor` as a fallback — works only until Chrome 158 and would have kept
the browser stylesheets alive forever, which is the duplication this whole
migration exists to remove.

**Every read failure renders.** This needed a second pass: the first version
threw from inside markup, and Svelte's response to that is to leave the tab
*blank*. An instructor clicking "Raw HTML" saw nothing at all, with the
explanation only in the console — a silent failure introduced by the very code
meant to prevent one. `Exercise.svelte` now renders the message, and the AI copy
button distinguishes "could not build the payload" from "the clipboard refused",
which are different problems with different fixes.

Verified in a browser against two real banks: the current demo (student view,
all three instructor tabs, the AI button, and an assessment that fetched two
bundles and produced 2.8 KB of LaTeX with no `undefined` in it), and a
deliberately stripped copy with no `precomputed` key, which shows the
regenerate-me message in the tabs and in the assessment builder.

Verification, and the first tests this repo has ever had, in `dashboard/tests/`
(stdlib `unittest`, hermetic SpaTeXt fixtures, no bank or generated data
needed). The core test asserts the two implementations agree rather than
comparing against a golden file. Also confirmed: `subset='all'` output is
byte-identical to the pre-change stylesheet across the demo bank, and a real
Chromium `XSLTProcessor` agrees with `lxml` on every fixture and subset
(`browser_harness.py`). The suite is mutation-checked.

Two things this does **not** cover. Firefox was not exercised — the
document-vs-element bug was Chromium-invisible, so `browser_harness.py` should
be run there too before the viewer is rebuilt. And `static/viewer.zip` is still
the pre-change build, so the browser-facing edit is inert until
`update_viewer.py` runs; that also means there are effectively *three* copies
of each stylesheet, the third being the one Vite inlined into the bundle.


Sources: whatwg/html#11523, mozilla/standards-positions#1287,
https://developer.chrome.com/docs/web-platform/deprecating-xslt

## The plain-Python generator runtime

How it works is still live reference, under "Generator runtimes". These two
are the record of doing it.

### Why this was cheap: the important seam already existed

`json_ready()` converts every generated value to a **string** before it reaches
`seeds.json`. No backend object has ever crossed that boundary, so `bank.py`,
`exercise.py`, the XSLTs and the viewer were always runtime-agnostic and needed
no changes at all. The subprocess wall was already in the right place; only what
runs *inside* it changed.

**Do not collapse either wall.** Importing sympy directly into `outcome.py` for
convenience, or letting a SymPy object into `seeds.json`, would undo this.

### What the runtime port was verified against

On a Windows host with no Sage installed: all eight outcomes generate; all eight
render through `Exercise.latex()`/`.html()`; EX2's product rule, MX1's
system-matrix correspondence and EX1's exact `-7` slope are correct; KaTeX
renders SymPy's LaTeX in the browser with zero errors; `--image-seeds` still caps
PNGs while writing `.tikz` for every seed; `build_docs.py` completes; and an
assessment generated from the viewer compiles under `pdflatex` to a printable PDF
containing the TikZ figure — drawn from a seed past the image cap, so it had no
PNG and relied on the `.tikz` source.

## The mat-106 port (2026-08-21 to 2026-08-27)

Retiring `mode` is the single most useful thing in this appendix: it is the
argument for why per-medium differences belong to the stylesheets and the
seed ranges, which is the ethos everything since has been held to.

### `mode` is the wrong layer, and what replaces it (resolved 2026-08-22)

**No generator in mat-106 branches on `mode` any more.** All nine are converted,
in three groups.


Nine generators in mat-106 took a `mode='html'|'latex'` argument and branched on
it. Six were the same workaround for one false belief -- that a SpaTeXt text
field could not carry mathematics -- and all six are gone, replaced by
`bank_helpers.spatext_math()` emitting `<m>` elements from the TeX the
generators already wrote.

The remaining three are not that, and they are worth separating because they
pull in opposite directions.

**W1 and W1-E are a presentation difference.** Egyptian numerals are set with
`\textpmhg` for print and `\Huge` in the browser, because that LaTeX font has
no web equivalent. The content is identical; only its rendering differs. That is
precisely what the three stylesheets exist for, so the fix belongs there: a
SpaTeXt element (say `<glyphs font="...">`) that `html.xsl` renders as a styled
span and `latex.xsl` as `\textpmhg{...}`. Adding a SpaTeXt element is the
documented multi-file dance (§12), now three files rather than six.

**R1 is a content difference tied to purpose.** Its `versions` and
`html_versions` dictionaries share no keys, but the names pair up: `add-coladd-1`
against `add-coladd-1p`. Comparing a pair shows they are different problems, and
the print one has empty `thinking` and `feedback` fields -- because print is the
student handout, where those are blanks to write in, while the viewer copy
carries model answers for self-study.

That is a real distinction, but it is not about the *medium*: it is about
whether an exercise is for browsing or for assessment. The seed ranges already
encode exactly that (§ "Bound the precomputed range"): 0..PUBLIC_SEEDS-1 is what
students browse, everything above it feeds assessments, printed or exported. So
R1 wants neither `mode` nor a variant -- it wants to branch on `self.seed`,
which `BaseGenerator` already exposes for this purpose:

    def data(self):
        studying = self.seed < PUBLIC_SEEDS
        return generate(pool='self_study' if studying else 'assessment')

A variant would fit badly here: variants are dealt evenly across all seeds, so
roughly half of the versions a student browses would come from the assessment
pool.

**How the nine were actually split.**

* Six were the same false belief -- that a text field could not carry maths --
  and were fixed by emitting `<m>` elements: N2, F5, W4, N1, N1-E through
  `bank_helpers.spatext_math()`, which rewrites the TeX the generators already
  wrote; **R2 by hand**, writing `<m>` directly into its f-strings. Worth
  knowing before editing R2: running `spatext_math` over a string that already
  contains `<m>` would escape it into visible `&lt;m&gt;`, since the function
  escapes everything outside the maths it matches. D4 was added to the
  `spatext_math` group later (2026-08-27) for `\$` and `\%`.
* Two were a genuine per-medium difference in the characters themselves, and
  became `<glyphs>`: W1 and W1-E.
* One was a difference of purpose rather than medium, and became a branch on
  `self.seed`: R1.

**There was a fourth kind, and it was missed (found 2026-08-27).** W4 also used
`mode` for *typesetting control*: its equations are long, LaTeX broke them at
the operators, and `\mbox` was the fix. The generator wrote `\mbox{$...$}` and
a `clean_latex_string` helper stripped it again when `mode == 'html'`. Print
was the default, so print got the boxes and the browser did not.

Retiring `mode` deleted the branch and orphaned `clean_latex_string` --
defined, never called -- leaving `\mbox` in the string for both media. The
template's `<m>` wrapper then swallowed it into `\(\mbox{\)`: an unmatched
brace inside math mode, which does not compile. **Print was broken for 50
versions of W4 while every HTML check was green,** and nothing noticed because
the mode-drop commit landed 46 minutes after the last `docs/` build and was not
built again for five days.

The fix is `<nobreak>`, the same shape as `<glyphs>`: `latex.xsl` renders it
`\mbox{...}`, `html.xsl` a `white-space: nowrap` span, `pretext.xsl` passes the
content through. W4 emits two of them per equation, matching the original
`\mbox{$...$} \mbox{$...$}` -- a break *between* the sides is fine, a break
inside either is not.

Unlike `<glyphs>`, this element **wraps** other elements, so every rule calls
`parseDisplay` instead of reading `text()`. Reading text nodes would discard
the `<m>` elements it exists to hold together, which is the same bug it was
introduced to fix.

> **Principle.** "Purely presentational" is not the same as "safe to delete".
> Presentation is the whole deliverable for print, and the browser is not the
> medium that proves it. A per-medium difference always has a stylesheet home;
> removing the branch without building that home just loses the requirement.

**A lesson about verification, not just about `\mbox`.** Every check written
during the port read the HTML. The LaTeX comes from a different stylesheet with
its own rules, and it shipped an uncompilable document while the HTML checks
passed. The print-side checks worth keeping are cheap and structural: brace
balance across the whole document, brace balance inside each `\(...\)`, and
text-mode commands appearing inside inline maths. `\(\textbf{W1}\)` is the one
standing exception -- the outcome-title element, legal and deliberate.

Templates that receive generated markup must inject with **triple** braces, or
Mustache escapes it into visible `&lt;m&gt;`. That in turn makes the prose the
generator emits XML-relevant, which is why `spatext_math` escapes everything
outside the maths it wraps. Two traps found by looking at rendered output rather
than at the data: a field wrapped in `<m>` by its template silently swallows any
element inside it, because `html.xsl`'s rule for `<m>` reads only text nodes;
and a LaTeX spacing command that was harmless inside a maths field becomes
literal text once the content is no longer inside one.

### The bank port (mat-106; done)

1. Move `slye_math.py` from `outcomes/` to the **bank root**, renamed
   `bank_helpers.py` — `load_generator()` adds the bank root and the generator's
   own folder to `sys.path`, not `outcomes/`.
2. `pygenerator.py` → `generator.py`, wrapped in the `Generator` class; delete
   `generator.sage`. Roughly 775 lines of shim disappear across 31 outcomes.
3. Drop the `mode='html'|'latex'` parameter. Only ~9 generators branch on it, and
   8 of those are formatting; emit `<m>` in the string instead (see the `WORDS`
   walkthrough) and let the print side convert. `R1` is the exception — it
   selects genuinely different content and wants `variants`, or splitting in two.
4. Convert `course_progress` and friends to **`variants`**. Today the value is
   frozen in each shim, so advancing the semester means editing files and
   regenerating; as a variant it is pregenerated across all cases and *filtered*
   at print time.

   > **Done** (audited 2026-08-27). The count in this step was correct: five
   > outcomes use these settings, and all five are converted -- `R2`, `W4`,
   > `W4-E` and `W5` by `variants`, `R1` by seed. The twenty others extract the
   > kwarg and never read it. See "The state of `variants` versus
   > `course_progress`".
5. Check LaTeX literals are raw strings: `"rac"` makes `` a formfeed.
