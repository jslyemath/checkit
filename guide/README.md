# CheckIt guide

Documentation for people using CheckIt to author and publish a bank.

| | |
|---|---|
| [Getting started](getting-started.md) | install, a first bank, adding an outcome, publishing |
| [CLI reference](cli.md) | every command and option, and the three constants |
| [Bank format](bank-format.md) | `bank.xml`, every file a bank can contain, override points |
| [Writing generators](generators.md) | `data()`, seeds, variants, figures, SageMath |
| [SpaTeXt reference](spatext.md) | the template vocabulary, and the traps that fail silently |
| [Checking a build](checking.md) | `checkit check`, and freezing an outcome |

## Where to look for what

**"How do I…"**

| | |
|---|---|
| …add an exercise | [Getting started → Adding an outcome](getting-started.md#adding-an-outcome) |
| …make one exercise vary by topic or difficulty | [`variants`](generators.md#variants--pregenerating-an-axis) |
| …draw a figure | [Figures](generators.md#figures) |
| …stop a rebuild changing problems students are using | [Freezing](checking.md#freezing-an-outcome) |
| …use my own LaTeX macros | [`bank_helpers.sty`](bank-format.md#bank_helperssty) |
| …change how figures are compiled | [`tikz_preamble.tex`](bank-format.md#tikz_preambletex) |
| …share Python between generators | [`bank_helpers.py`](bank-format.md#bank_helperspy) |
| …find out why a generator failed | [`checkit check`](checking.md#generators) |
| …make more versions than 1000 | [Constants](cli.md#constants) |
| …set the chatbot prompt | [`<ai-prompt>`](bank-format.md#bank-level) |

**"Why is my…"**

| | |
|---|---|
| …site showing an old date | you ran `generate` without `viewer` — [see](cli.md#checkit-viewer) |
| …exercise showing `&lt;m&gt;` | double braces where triple are needed — [see](spatext.md#traps) |
| …exercise missing its numbers | an `<m>` wrapper swallowing markup — [see](spatext.md#m-swallows-any-element-inside-it) |
| …exercise showing `\dfrac` literally | bare TeX in a text field — [see](spatext.md#bare-tex-in-a-text-field-renders-literally) |
| …figure a broken image | `--image-seeds` capped below 50 — [see](cli.md#--image-seeds-n) |
| …build refusing to run | `--amount` below 50, or a bank with figures and no `--remote` |

Run `checkit check` before assuming any of the above — it catches all of them
by name.

---

Developer-facing notes — why things are the way they are, what has been tried,
what is still open — live in [`CODEBASE_NOTES.md`](../CODEBASE_NOTES.md). That
file is long and is not a user guide.
