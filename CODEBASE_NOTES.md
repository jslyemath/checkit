# CheckIt Codebase Notes

This document is as close to a complete, self-contained reference for the CheckIt codebase as possible. Every class, function, file, and design decision is explained here in enough detail that someone with no access to the source files can answer any question about how the system works. It started by looking at the original CheckIt by StevenClontz. Now, it also details changes made to this fork, maintained by jslyemath. Note that it is maintained alongside the code but may lag; when in doubt, the actual source code is authoritative.

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

3. **A Bank** (a directory the instructor creates, example in `demo-bank/`): Contains a `bank.xml` manifest, an `outcomes/` directory tree, and for each outcome a `generator.sage` file (SageMath Python code) plus a `template.xml` file (SpaTeXt XML with Mustache placeholders).

The intermediate representation between Python generation and browser display is called **SpaTeXt** (Spatial Text) — a small, well-defined XML vocabulary rooted in a `<knowl>` element, using the namespace `https://spatext.clontz.org`. Three XSLT stylesheets transform SpaTeXt into HTML, LaTeX, and PreTeXt. These stylesheets exist in two identical copies: one bundled inside the Python package (`dashboard/checkit/static/`) for server-side rendering, and one compiled into the browser viewer (`viewer/src/spatext/xsl/`) for client-side rendering.

### High-level data flow

```
bank.xml + generator.sage + template.xml
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
│   └── checkit/                     the actual Python package
│       ├── __init__.py              exports VERSION = '0.2.7'
│       ├── __main__.py              CLI entry point (click + trogon)
│       ├── bank.py                  Bank class
│       ├── dashboard.py             deprecated Jupyter widget dashboard
│       ├── exercise.py              Exercise class + XSLT rendering
│       ├── outcome.py               Outcome class
│       ├── utils.py                 working_directory() context manager
│       ├── xml.py                   XML namespace constants
│       ├── static/                  files bundled inside the installed package
│       │   ├── __init__.py          read_resource() and open_resource() helpers
│       │   ├── bank.xml             boilerplate bank manifest for `checkit new`
│       │   ├── template.xml         boilerplate SpaTeXt template for `checkit new`
│       │   ├── generator.sage       boilerplate generator for `checkit new`
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
│   └── outcomes/                    one subfolder per learning outcome
│       ├── EX/
│       │   ├── EX1/                 Line Slopes outcome
│       │   │   ├── generator.sage
│       │   │   └── template.xml
│       │   ├── EX2/                 Product Rule outcome
│       │   │   ├── generator.sage
│       │   │   └── template.xml
│       │   └── EX3/                 Tasks/Subtasks demo outcome
│       │       ├── generator.sage
│       │       └── template.xml
│       ├── IMG/
│       │   ├── IMG1/                Generating Images outcome
│       │   │   ├── generator.sage
│       │   │   └── template.xml
│       │   └── IMG2/                Manual Images outcome
│       │       ├── generator.sage
│       │       └── template.xml
│       ├── MX/
│       │   └── MX1/                 Matrix Example outcome
│       │       ├── generator.sage
│       │       └── template.xml
│       ├── TIKZ/                    TikZ image-generation test outcome (tkz-euclide)
│       │   ├── generator.sage
│       │   └── template.xml
│       └── XML/                     XML Entities demo outcome
│           ├── generator.sage
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
        │   │   ├── ParagraphNodes.svelte  dispatches inline nodes (m, me, em, c, q, url, image)
        │   │   └── TitleNodes.svelte  inline nodes allowed inside a title (m, c, em, q)
        │   └── xsl/
        │       ├── html.xsl         SpaTeXt -> HTML (browser-side, identical to static copy)
        │       ├── latex.xsl        SpaTeXt -> LaTeX (browser-side)
        │       └── pretext.xsl      SpaTeXt -> PreTeXt XML (browser-side)
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
VERSION = '0.2.7'
```

This is the entire file. It exports a single string constant holding the current package version. This value is imported by `__main__.py` (to write `requirements.txt` for new banks) and is referenced in `setup.cfg` via `version = attr: checkit.VERSION`. It also appears hardcoded in `App.svelte`'s footer.

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
- Creates `<directory>/outcomes/EX1/` and copies `template.xml` and `generator.sage` from the bundled static resources
- Creates `<directory>/.devcontainer/` and copies `setup.sh` and `devcontainer.json`
- Copies `bank.xml` and `README.md` into the root
- Copies `gitignore.txt` as `.gitignore`
- Writes `requirements.txt` containing `checkit-dashboard == 0.2.7`
- Prints a success message

**`generate(amount, regenerate, images, image_seeds, outcome)` — `checkit generate`:**
Options:
- `-a`/`--amount` (default 1000): number of seeds to generate
- `-r`/`--regenerate` (flag): if set, regenerates even if seeds.json already exists
- `-i`/`--images` (flag): if set, also generates PNG graphics
- `--image-seeds` (int, default None / no short flag): render images for only the first N seeds of each outcome, while still generating full seed *data* for all of them. Intended for quick local previews; a low value produces broken images for the viewer (~20 seeds) and LMS export (seeds 100–999). See §12 "Limiting image rendering with `image_seeds`".
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
Returns the full path to `<outcome_dir>/generator.sage`.

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
Used by the (deprecated) Jupyter dashboard for "fresh preview". Calls `sage(self, preview_json, preview=True, images=True)` to generate 20 seeds, then `compile_tikz_for_outcome(self)` to turn any generated `.tikz` files into PNGs, reads them, and returns a list of `Exercise` objects.

**`Outcome.html_preview(self, pregenerated=False)`**
Used by the Jupyter dashboard. If `pregenerated=True`, picks a random already-generated exercise; otherwise calls `preview_exercises()`. Returns a long HTML string showing the rendered exercise, its JSON data, SpaTeXt XML, HTML, LaTeX, and PreTeXt.

**`Outcome.build_path(self)`**
Returns (creating if needed) `<bank>/assets/<slug>/generated/`. All generated files for this outcome go here.

**`Outcome.seeds_json_path(self)`**
Returns `<build_path>/seeds.json`.

**`Outcome.generate_exercises(self, regenerate=False, images=False, amount=1_000, image_seeds=None)`**
- If `regenerate=False`, tries `self.load_exercises()`. If that succeeds (seeds.json exists and is valid), returns early.
- Otherwise calls `sage(self, self.seeds_json_path(), preview=False, images=images, amount=amount, image_seeds=image_seeds)` — this invokes the SageMath subprocess.
- If `images=True`, then calls `compile_tikz_for_outcome(self)` to compile any `.tikz` files the generator wrote into PNGs.
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

Defines the `sage()` function that runs the SageMath generation subprocess.

**`sage(outcome, output_path, preview=True, images=False, amount=1_000, random=False, image_seeds=None)`**

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
1. Changes to `../demo-bank/` and runs `python -m checkit generate -r` to regenerate all demo exercises
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

---

## 4. Detailed Walkthrough of Every `.sage` File

SageMath (`.sage`) files look like Python but are preprocessed by SageMath before execution. Key differences:
- `^` is exponentiation (Python's `**`)
- Many mathematical objects like `var`, `randrange`, `choice`, `shuffle`, `ZZ`, `QQ`, `SR`, `matrix`, etc. are available as global names
- `set_random_seed(n)` makes all subsequent random operations deterministic with seed `n`

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
   - If `gen_images and i < image_amount` (so the cap limits which seeds get images):
     - Calls `generator.graphics()`; if non-None, creates the seed directory and saves each value as `<filename>.png`
     - Calls `generator.tikz_graphics()`; if non-None, creates the seed directory and writes each value as a `<name>.tikz` file (these are compiled to PNG afterward by `tikz.py`, back in the Python layer — not by SageMath)
   - Appends `{"seed": seed_int, "data": data}` to `seeds` list
6. Writes the full JSON: `{"seeds": [...], "generated_on": "...ISO timestamp..."}` to `output_path`

---

### `demo-bank/outcomes/EX/EX1/generator.sage`

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

### `demo-bank/outcomes/EX/EX2/generator.sage`

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

### `demo-bank/outcomes/EX/EX3/generator.sage`

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

### `demo-bank/outcomes/MX/MX1/generator.sage`

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

### `demo-bank/outcomes/IMG/IMG1/generator.sage`

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

### `demo-bank/outcomes/IMG/IMG2/generator.sage`

Demonstrates manually-placed images:

```python
class Generator(BaseGenerator):
    def data(self):
        image_version = f"{randrange(1, 4)}"
        return {"digit": image_version}
```

Randomly selects `"1"`, `"2"`, or `"3"` — corresponding to pre-existing files `demo-bank/assets/IMG2/1.png`, `demo-bank/assets/IMG2/2.png`, `demo-bank/assets/IMG2/3.png` (placed there manually). The template references `source="assets/IMG2/{{digit}}.png"`.

---

### `demo-bank/outcomes/XML/generator.sage`

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

### `demo-bank/outcomes/TIKZ/generator.sage`

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

---

## 5. Detailed Walkthrough of Every XSLT File

SpaTeXt uses three XSLT 1.0 stylesheets. There are two physically separate copies: `dashboard/checkit/static/` (used server-side by lxml) and `viewer/src/spatext/xsl/` (used client-side by the browser's `XSLTProcessor`). The two copies are identical in content.

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

> **Known viewer gap:** unlike `<image>`, `<tikz-image>` is *not* wired into the interactive Svelte rendering path. `outcomeToStx` (in `utils/index.ts`) only sets `@remote` on `image` tags, and `ParagraphNodes.svelte` only dispatches `m/me/c/em/q/image/url` — `tikz-image` falls through and is dropped. So a `<tikz-image>` renders in the **html / latex / pretext export tabs** (which run the XSLT via `XSLTProcessor`) but shows nothing in the default interactive **display** mode. Wiring it up would mean adding a `tikz-image` case to `ParagraphNodes.svelte` and extending the `querySelectorAll("image")` remote-stamping in `outcomeToStx` to cover `tikz-image`.

**`<list>`** — An unordered list.

**`<item>`** — A list item inside `<list>`. May contain `<p>` and nested `<list>`.

---

### `html.xsl` (both copies are identical)

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

**`parseDisplay` template:** Applies templates to all inline children: text nodes, `<m>`, `<me>`, `<q>`, `<c>`, `<em>`, `<url>`, `<image>`.

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

### `latex.xsl` (both copies identical)

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

### `pretext.xsl` (both copies identical)

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

**`outcomeToStx(outcome, seed)`**
Converts an outcome + seed index to a SpaTeXt DOM element.
1. Calls `Mustache.render(outcome.template, outcome.exercises[seed]['data'])` — renders the Mustache template with the exercise data
2. If Mustache fails, returns a knowl with an error message
3. Parses the resulting XML string via `DOMParser`
4. If XML parsing fails (e.g., malformed XML from bad generator output), returns an error knowl
5. Finds all `<image>` elements and sets their `remote` attribute to the current page's origin + pathname (so relative image paths work correctly when the viewer is served from a subdirectory)
6. Returns the root DOM element

**`outcomeToHtml(outcome, seed, mathMode, solutions)`**
1. Calls `outcomeToStx` to get the SpaTeXt element
2. Creates an `XSLTProcessor`, loads `html.xsl`, transforms the element
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
1. For each slug, finds the outcome and picks a random seed from `[20, exercises.length)` (skipping the first 20 "public" versions)
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
3. Creates a temp directory, copies `wrapper.sage` there
4. Uses `working_directory(outcome.bank.abspath())` to change to the bank root
5. Runs:
   ```
   sage /tmp/xxx/wrapper.sage /home/user/my-bank/outcomes/EX1/generator.sage
        /home/user/my-bank/assets/EX1/generated/seeds.json 1000 no
   ```

### Step 5: SageMath execution

SageMath runs `wrapper.sage`. The script:

1. Reads `sys.argv`:
   - `generator_path = "outcomes/EX1/generator.sage"` (relative to bank root, since we cd'd there)
   - `seeds_path = "/home/user/my-bank/assets/EX1/generated/seeds.json"`
   - `amount = 1000`
   - `random = False`
   - `gen_images = False`

2. Calls `load("outcomes/EX1/generator.sage")` — executes the generator file, making `Generator` available in scope. The generator class definition in that file uses `BaseGenerator` and `CheckIt`, which are already defined in `wrapper.sage`.

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

---

## 8. The Bank Format

A bank is a directory with the following structure:

```
my-bank/
├── bank.xml
├── outcomes/
│   ├── SLUG1/
│   │   ├── generator.sage
│   │   └── template.xml
│   └── SLUG2/
│       ├── generator.sage
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

The `<path>` element allows arbitrary directory organization. The demo bank uses `outcomes/EX/EX1` (nested), while the boilerplate uses `outcomes/EX1` (flat).

### `generator.sage`

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

**`outcomes/FR1/generator.sage`:**
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
Effect: Runs SageMath for each outcome, writes assets/bank.json
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

The output formats are defined entirely by the three XSLT stylesheets. There are **two copies** of each that must be kept in sync:
- `dashboard/checkit/static/html.xsl` (server-side, used by lxml)
- `viewer/src/spatext/xsl/html.xsl` (browser-side, used by XSLTProcessor)

To change how a SpaTeXt element renders in HTML:
1. Locate the `<xsl:template match="stx:element_name">` rule in both `html.xsl` files
2. Modify the template in both files identically
3. Rebuild the viewer: `cd dashboard && python update_viewer.py` (rebuilds `viewer.zip`)

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

Currently the viewer is a JavaScript SPA that renders exercises dynamically. AI crawlers see only the empty HTML shell. To make exercises accessible to AI assistants:

**Option 1: Add a static HTML export command.**
Add a `checkit export-html` CLI command that, for each outcome and each of the first N seeds, calls `Exercise.html()` and writes the result to `docs/bank/<slug>/<seed>.html`. Also write a `docs/bank/index.html` with links to all pages. This creates a crawlable site.

Files to modify:
- `dashboard/checkit/__main__.py` — add the command
- `dashboard/checkit/bank.py` — add a method like `export_static_html()`
- `dashboard/checkit/exercise.py` — `Exercise.html()` is already available

**Option 2: Use server-side rendering.**
Deploy the bank with a Python server that accepts `GET /bank/<slug>/<seed>` and returns fully rendered HTML (using `Exercise.html()` + the KaTeX CSS) with no JavaScript required.

**Option 3: Add a JSON-LD metadata file.**
Generate a `docs/exercises.jsonld` with exercise content in schema.org `Quiz` format. AI systems that understand structured data can consume this directly.

### Image generation backends (Sage, TikZ, and future PreFigure)

CheckIt's image step supports multiple backends. Two are implemented:

- **Sage graphics** — generators define a `graphics()` method returning `{name: <sage plot object>}`; wrapper.sage saves each as `<name>.png`.
- **TikZ** — generators define a `tikz_graphics()` method returning `{name: <tikz source string>}`; wrapper.sage writes each as `<name>.tikz`, then `tikz.py`'s `compile_tikz_for_outcome()` compiles them to PNG via pdflatex + pdftoppm (PDF kept only in a temp dir, discarded after).

Both are gated by the `images` flag and the `image_seeds` cap (render images only for the first N seeds — see below). PreFigure would be a third backend following the same shape as TikZ.

PreFigure (a Python library for generating mathematical figures as SVG/PNGs from XML descriptions) could replace Sage's `plot()` for image generation. The integration point is the `graphics()` method in generators and the image-saving loop in `wrapper.sage`.

Current image generation in `wrapper.sage` (after implementing TikZ but not PreFigure):
```python
if gen_images and i < image_amount:
            directory = os.path.dirname(seeds_path)
            seed_path = os.path.join(directory, f"{seed_int:04}")
            graphics = generator.graphics()
            if graphics is not None:
                os.makedirs(seed_path, exist_ok=True)
                for filename in graphics:
                    graphics[filename].save(os.path.join(seed_path, f"{filename}.png"))
            tikz = generator.tikz_graphics()
            if tikz is not None:
                os.makedirs(seed_path, exist_ok=True)
                for name, source in tikz.items():
                    with open(os.path.join(seed_path, f"{name}.tikz"), "w") as f:
                        f.write(source)
```

The `graphics[filename]` object is currently a Sage graphics object with a `.save(path)` method. To support PreFigure:
1. Have `graphics()` return PreFigure diagram objects instead of Sage plot objects
2. In `wrapper.sage`, detect the type and call the appropriate save method
3. Or: have `graphics()` always return objects with a `.save(path)` method — if you make PreFigure diagrams have that interface (or wrap them), no change to `wrapper.sage` is needed.

The `generator_path` loaded by `wrapper.sage` runs in the SageMath namespace, so PreFigure would need to be importable from within SageMath's Python environment. Since SageMath uses conda, install it with `conda install prefigure` or `pip install prefigure` in the sage conda env.

### Limiting image rendering with `image_seeds` (--image-seeds)

`generate --image-seeds N` renders images for only the first N seeds of each outcome, while still generating full seed *data* for all of them. Threaded through Bank.generate_exercises → Outcome.generate_exercises → sage() → wrapper.sage (as sys.argv[6]), and per-outcome (N applies to each outcome independently, not N total across the bank). Default (None) renders all.

Intended for fast local previews. Consumer exposure to un-rendered seeds:
- Viewer: caps at ~20 seeds, so image_seeds >= 20 keeps it clean.
- Print/PDF: uses the .tikz source via \input{}, needs no PNG at all.
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

## Local divergences from upstream StevenClontz/checkit

This fork diverges from upstream in these deliberate ways. Recorded so an
upstream merge doesn't silently revert them:

- **TikZ image backend** — new wrapper/tikz.py; tikz_graphics() added to
  BaseGenerator in wrapper.sage; <tikz-image> rule added to all three XSLTs
  (both the dashboard/checkit/static/ and viewer/src/spatext/xsl/ copies);
  image_amount cap in wrapper.sage.
- **image_seeds option** — added to the CLI generate command and threaded
  through Bank/Outcome.generate_exercises and sage().
- **tikz.py robustness** — judges pdflatex success by PDF existence (not exit
  code, since pgfplots can exit non-zero on recoverable warnings); a
  COMPILE_TIMEOUT backstop converts stuck compiles into bounded, reported
  errors (empirically, neither stdin=DEVNULL nor batchmode prevents the stall
  on a malformed figure — the timeout is the real protection).
- **load_exercises() fix** — added the missing `return` on the cached path so
  the cache-skip optimization actually fires (upstream likely still has this
  no-op; watch on merge).
- **Custom TikZ preamble** — tikz.py loads tikz_preamble.tex from the bank root
  if present, else uses a built-in default.

## Codespace / devcontainer notes

- The devcontainer installs a current TeX Live (2026) from upstream tlnet (scheme-infraonly + tlmgr), NOT Debian's apt texlive (which is 2019 and too old for current tkz-euclide/tkz-elements). Add LaTeX packages by extending the tlmgr install list in .devcontainer/setup.sh.
- poppler-utils (pdftoppm) is installed via apt in setup.sh.
- TikZ compilation currently lives in wrapper/. Revisit whether image-rendering backends deserve their own package once PreFigure is added (premature now with only one such file).
