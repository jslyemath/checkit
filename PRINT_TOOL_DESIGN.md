# checkit-print — design draft

**Status: draft for review.** Nothing here is built. Written 2026-09-01 from
reading `pdfgenerator.py`, `skillcheckpoints.sty`, `main_template.tex` and the
30 `textemplate.tex` files in mat-106, plus the requirements given in
conversation.

Companion to the "The print tool" sections of `CODEBASE_NOTES.md`, which this
supersedes where they disagree.

---

## 1. What it is

A separate installable package that turns a CheckIt bank plus a roster into a
printable PDF: many versions of many skills, distributed across students,
optionally with answer keys.

It is **not** CheckIt's built-in assessment builder, which produces one
anonymous assessment. This produces a class set.

Its own repo, depending on `checkit-dashboard`. Not in the platform (rosters
and Google OAuth are not platform concerns, and it would worsen upstream
merges) and not in a bank (there are two, and the pipeline is currently copied
between them by hand).

---

## 2. The constraint that shapes everything

**`skillcheckpoints.sty` is a working by-hand system, and must remain one.**

MAT 206's skills are currently hand-written `.tex` files using that package,
with no CheckIt involved at all. That is not a temporary state to be migrated
away from — it is a supported way to use the system, and it is why the package
looks the way it does.

Three consequences, and they decide the architecture:

1. **The unit of exchange is a skill `.tex` file**, not anything CheckIt-shaped.
   A hand-written skill file and a generated one must be indistinguishable to
   the assembler, so a single document can mix them.
2. **The `.sty` vocabulary is the interface.** `\skillheader`, `\tfleft`,
   `\fillinblank`, `\minicol`, `\ans`, `ansenv`, `\setvseed`, `\setname`,
   `\setsect` are a public API. The print tool *targets* them; it does not
   replace them.
3. **The `.sty` must not require CheckIt.** No generated file it depends on, no
   import path, no assumption that `bank.xml` exists.

An earlier draft in `CODEBASE_NOTES.md` proposed making `latex.xsl` emit
semantic `\stxKnowl` / `\stxTask` commands and having a theme redefine them.
**That is now the wrong direction.** It would create a second vocabulary that
hand-authors do not use, and split the system in two. The existing commands
already are the semantic layer.

---

## 3. Architecture

```
     BANK                              PRINT TOOL                    LATEX
┌──────────────┐            ┌────────────────────────────┐      ┌────────────┐
│ seeds.json   │──seeds──▶  │ render                     │      │            │
│ (400-999)    │            │   textemplate.tex + data   │──▶   │ skill .tex │
│              │            │   or SpaTeXt → .tex        │      │  per       │
│ bank.xml     │──slug,     │                            │      │  version   │
│              │  desc      │ assemble                   │      └─────┬──────┘
│ textemplate  │──layout──▶ │   roster × seating × skills│            │
│   .tex       │            │   keys, extras, ordering   │            ▼
│ bank_helpers │            │                            │      ┌────────────┐
│   .sty       │──macros──▶ │ emit                       │──▶   │ main .tex  │
└──────────────┘            │   one folder, recompilable │      │  + .sty    │
                            └────────────────────────────┘      └─────┬──────┘
     ROSTER                                                           │
┌──────────────┐                                                      ▼
│ names,       │──────────────────────▶                          ┌────────┐
│ selections,  │                                                 │  PDF   │
│ seating      │                                                 └────────┘
└──────────────┘
```

### Layers, and what each owns

| | owns | lives in |
|---|---|---|
| **bank** | what an exercise says; the macros its content needs | the bank repo |
| **skill `.tex`** | one version of one skill, laid out | generated, or hand-written |
| **theme (`.sty`)** | how everything looks | print tool default; a bank or course may replace it |
| **publication** | what *this run* wants | a file in the course repo |
| **roster** | who gets what, and in what order | Google Sheet today; local file always possible |

---

## 4. Inputs

### 4.1 Publication file

The settings that describe a run. Plain data, versioned with the course, no
code. TOML proposed.

```toml
[course]
name       = "MAT 106"
semester   = "Fall 2026"
professor  = "J. Slye"
title      = "Skill Checkpoint 4"
date       = "2026-09-15"

[bank]
path = "../mat-106-checkit"

[print]
keys          = true      # print answer keys at the end
key_copies    = 2
names         = true      # false prints a blank rule instead
double_sided  = true
seed_override = 0         # 0 = pick per the seating chart

[[extras]]
skill  = "W1"
copies = 3                # blank name line; versions shuffled if > 1
```

Replaces the named cells currently read from the sheet.

`PDF Location:` is genuinely used and should stay: "Default Folder" or a save
dialog. An earlier draft of this document said it was ignored; that was wrong —
it drives `filedialog.asksaveasfilename` at `pdfgenerator.py:165`.

`Include Names:` is dead *in Python*, but only because the Apps Script already
applied it, writing the literal `Blank` into the name column before the CSV is
exported. That is the split-brain problem in miniature: one setting, two
implementations, and the second one looks broken when read alone.
`Submission Cutoff:` is read and unused on both sides.

### 4.2 Roster

Who exists, what each student selected, and which section they are in.

**The tool's own format is structured data it defines** — TOML or JSON with real
fields:

```toml
[[student]]
name    = "Ada Lovelace"
email   = "kstellat@oswego.edu"
sid     = "806510955"
section = "800"
skills  = ["G2-E", "G4", "A2"]
```

**Getting Google responses into that shape is an import step, not the format.**
The current pipeline treats a CSV export *as* the data model: magic headers
(`Full Name:`, `Sec:`, `Var:`, `1:`) located by string-searching a grid, in a
format never intended for structured records. Reproducing that would be
inheriting the hack rather than replacing it.

Two importers, either of which writes the structured file:

- **Forms/Sheets API** — the eventual path, and the only reason Google is
  involved at all (university-controlled accounts, no good alternative for
  polling students).
- **A CSV import step** — map columns once, interactively, eyeball the result.
  Useful as a fallback when the API is down or scopes lapse.

Either way nothing downstream ever sees a magic header.

### 4.2b Skill selection modes

Three overrides, all in the current Apps Script, all wanted:

| mode | behaviour |
|---|---|
| **Simply Print** | everyone gets the same listed skills; responses ignored entirely |
| **No Submission? Default to…** | fallback skills for students who did not respond |
| **Append for Everyone** | these skills are added on top of whatever each student chose |

They compose: Append applies on top of both of the others.

### 4.3 Seating chart

Currently a set of sheets (one per section) with columns
`Group | Variant | Students | N`. Students sit in groups of four; the Variant
column alternates `A, B, A, B` within a group, typed by hand.

It determines the **order** students print in, so a stack of paper matches the
room, and which version each gets.

**The rule, stated plainly: two versions, and no two immediately adjacent
students share one.** Not "everyone at a table differs" — immediate neighbours.
That is why two versions suffice for a table of four.

Sections currently share the pool: `A`/`B` across both 800 and 810. A later
seating chart could use `E`/`F`/`G`/`H` to make a section disjoint, but nothing
needs that today.

**Long term** this becomes a GUI: drag seats into position, mark each with a
version letter, and the tool derives everything. That is the target.

**In the interim**, the smallest thing that removes the hand-typing: a seating
file listing groups in order, with the tool alternating versions along each
group and warning when two adjacent seats collide. A seat may be pinned to a
version explicitly, so the tool never overrules a deliberate choice.

```toml
[[group]]
seats = ["Ada Lovelace", "Alan Turing", "Grace Hopper", "Katherine Johnson"]

[[group]]
seats = ["Emmy Noether", "Srinivasa Ramanujan", "David Blackwell", "Mary Cartwright"]
```

The interim format should be whatever the GUI will eventually read and write,
so the GUI is a front end for it rather than a replacement.

## 5. Where versions come from

**Seeds 400–999 of the bank's `seeds.json`.** Pregenerated, reproducible, and
published nowhere — `checkit viewer` excludes `seeds.json` from `docs/`, so
those versions exist only in the bank.

This replaces the current approach of seeding `random` with a 5-digit number and
running the generator directly. Two gains: printing needs no working generator
environment, and a printed sheet can be reproduced exactly from its seed.

Do **not** use seeds 50–399: `derived.json` publishes those *with their answers*.

Variants are selected here too. An outcome declaring
`variants = ["no_repeating", "repeating"]` records the label per seed, so a
publication can ask for the case the course has reached:

```toml
[variants]
D2 = "no_repeating"
W7 = "terminating"
```

Without an entry, any variant is acceptable.

**Seed overrides** let the user choose the seeds *and* how they map onto the
seating versions — not just "use seed 509", but "version A is seed 509, version
B is seed 662". That makes a reprint exact, and it makes "give me the same quiz
as last section" a one-line change.

```toml
[seeds]
A = 509
B = 662
```

---

## 6. Output

### 6.1 The skill `.tex` file — the unit

One file per (skill, version):

```
out/
├── main.tex                  the assembled document
├── skillcheckpoints.sty      the theme, copied in
├── bank_helpers.sty          the bank's macros, copied in
├── skills/
│   ├── W1/
│   │   ├── W1 v451.tex
│   │   └── W1 v802.tex
│   └── N3/
│       └── N3 v451.tex
└── assets/                   figures the skills reference
```

**Requirement: this folder must compile with `pdflatex main.tex` and nothing
else.** No absolute paths, no reference back to the bank, no tool required. That
is what makes the output auditable, archivable, and fixable by hand at 11pm the
night before a quiz.

A hand-written skill file dropped into `skills/` is indistinguishable from a
generated one, which is the property §2 demands.

### 6.2 How a skill `.tex` is produced

Two paths, in priority order:

1. **The outcome has a `textemplate.tex`** — render it with the version's data,
   exactly as today. This is how every mat-106 outcome works, and it is how
   layout that no vocabulary will capture stays possible.
2. **It does not** — render the SpaTeXt through `latex.xsl` and wrap it in the
   theme's commands.

Path 2 means new outcomes cost one template instead of two, and path 1 means
nothing has to migrate. `textemplate.tex` is a permanent escape hatch, not a
transitional state.

### 6.3 Skill descriptions

`\skillheader{W1}` already opens a skill with its slug and description, looked
up from a `\setskilldesc` dictionary that `pdfgenerator.py` writes out of
`bank.xml`. That flow is correct and should survive unchanged.

For hand-written banks with no `bank.xml`, the descriptions file is written by
hand — which is exactly how MAT 206 works today.

---

---

## 6b. The assessment builder should converge on this

The viewer already has an assessment builder: pick outcomes, get one random
version of each as LaTeX, copy it or push it to Overleaf. **The goal is for it
to be the same thing as a print run with one student, a blank name, and one
seed.**

That is closer than it looks, because the mechanism already exists.

### What is already there

`viewer/src/templates/assessmentTemplate.tex` is a **self-contained** document —
its own `\documentclass`, its own `\usepackage` list, a Mustache loop over the
exercises. It is **already user-editable in the UI**, stored per browser, with a
reset-to-default button. It already POSTs to Overleaf.

So "carry the theme in the header" is not a new capability. It is a different
default template.

### Inlining the theme

LaTeX has a feature for exactly this, and Overleaf supports it:

```latex
\begin{filecontents*}[overwrite]{skillcheckpoints.sty}
... the whole theme ...
\end{filecontents*}

\begin{filecontents*}[overwrite]{Skill Descriptions.tex}
\setskilldesc[Blue]{G1}{I can identify lines of symmetry...}
\end{filecontents*}

\documentclass[12pt]{article}
\usepackage{skillcheckpoints}
\begin{document}
\setname{Blank}\setsect{Blank}
\skillheader{G1}
... exercise body ...
\end{document}
```

`filecontents` writes those files at compile time, so one pasteable block
carries the theme *and* the `\input{Skill Descriptions.tex}` the theme depends
on. No attachments, no folder.

**The exported assessment carries answers** — it is an instructor artefact, so
`\setboolean{anstoggle}{true}`.

### The obstacle: figures

`latex.xsl` renders `<image>` as `\includegraphics{assets/<slug>/generated/<seed>/<name>.png}`
— a **relative path**. Pasted into Overleaf there is no `assets/` folder, so the
figure is missing.

And there is a live bug behind it (found 2026-09-01, see `CODEBASE_NOTES.md`):
the assessment builder draws seeds from `[PUBLIC_SEEDS, BUNDLE_UNTIL)` = 50–399,
but `--image-seeds 50` rasterises PNGs only for seeds 0–49. **Every assessment
containing `F2` or `F2-E` currently references a PNG that was never rendered.**
Browsing looks fine because the viewer only ever shows seeds 0–49; print is fine
because it uses `textemplate.tex` with TikZ written inline and never touches the
PNGs.

Three ways to close it:

1. **Raise `--image-seeds` to `BUNDLE_UNTIL`.** Fixes the broken images. Does
   not fix copy-paste, and multiplies rasterisation time and `docs/` size by
   about eight.
2. **Publish `.tikz` and have `<image>`-style figures `\input` the source.**
   `build_viewer` currently excludes `*.tikz`. With the source published,
   `filecontents` can inline the figure too, and a pasted document draws its own
   figures with no image files at all. **This is the only option that actually
   yields one self-contained file**, and it matches what print already does.
3. **Base64 the PNGs into the document.** Works; bloats the paste enormously.

Recommended: (2), with (1) as an immediate stopgap if assessments are needed
before the tool exists.

### How close the two get

| | print | assessment builder |
|---|---|---|
| theme | `\usepackage{skillcheckpoints}` from a file | same, via `filecontents` |
| skill body | `\input{W1/W1 v451.tex}` | inlined |
| name | `\setname{Kate}` | `\setname{Blank}` |
| answers | off for students, on for keys | on |
| seeds | one per seating version | one, random from 50–399 |
| assembly | loop over students | no loop |

Everything but the last two rows is identical. **If the print tool's theme
becomes the assessment builder's default template, the two differ by a loop.**

---

## 6c. Print tracking

The tool records what was printed for whom, and lets the instructor mark what
happened afterwards.

```
printed 2026-05-06 "Skill Checkpoint" :
  Ada Lovelace  G2-E seed 509   → passed
  Ada Lovelace  G4   seed 509   → did not pass
  Ada Lovelace  A2   seed 509   → did not take
```

**For instructor record-keeping only.** It does *not* feed back into printing —
no "skip skills already passed", no "prioritise repeated failures". That keeps
the print path a pure function of its inputs.

Lives **in the tool**, not a spreadsheet. That means a table-style editor in the
eventual GUI, which is a later bridge; until then the store is a local file the
tool reads and writes.

Its shape matters more than its editor. It should answer:

- what did this student receive, on what date, at which seed?
- what happened with it?

which also makes exact reprints a lookup rather than a re-derivation. That is
why **byte-for-byte reproducibility is not a requirement**: recording the seed
is cheaper and more honest than making the whole run deterministic, and it does
not cost the freedom to reshuffle.

---

## 6d. Where output goes

A canonical location on the local machine, so the same PDF can be rebuilt later:

```
~/CheckItPrint/MAT 206/2026-05-06 Skill Checkpoint/
├── main.tex
├── skillcheckpoints.sty
├── bank_helpers.sty
├── skills/…
└── assets/…
```

`pdflatex main.tex` works there, forever, with no tool and no bank. **Not
committed to a repository** — it is a local record, not a published artefact.


## 7. Google integration

Two directions, and they are different problems.

**Reading responses** replaces the CSV export step. Google Forms API or Sheets
API; needs OAuth, a client secret, and a token cache. Contained: one adapter
behind the interface in §4.2.

**Writing the form** — updating the week's available skills so students can
select them — is the more valuable half and the harder one. It needs the Forms
API with edit scope, and it needs to know which skills are "available this
week", which is a fact the tool does not currently have anywhere.

Proposed: the publication file names them.

```toml
[form]
id     = "1FAIpQLSc..."
skills = ["W1", "W2", "N3", "F2"]
```

**Suggestion: build the CSV path first and the Forms path second.** The CSV path
is the whole pipeline minus one adapter; adding OAuth to a tool that already
works is easier than debugging both at once.

---

## 8. Feature inventory

Everything the current tool does, plus what is wanted. Marked by state.

| feature | today | proposed |
|---|---|---|
| Per-student skill selection | ✅ roster columns `1:`, `2:`… | keep |
| Variant → seed mapping | ✅ random 5-digit seeds | change to pregenerated 400–999 |
| Seed override | ✅ | keep, in the publication file |
| Sections in header | ✅ `\setsect` | keep |
| Key packets, N copies | ✅ `Key Amount:` | keep |
| Key deduplication, bank order | ✅ | keep |
| Double-sided safety | ✅ `\preparefornextstudent` | keep |
| Course / semester / professor | ✅ four `\VAR{}`s | move to publication file |
| Skill headers with descriptions | ✅ from `bank.xml` | keep |
| Version stamp in footer | ✅ `\setvseed` | keep |
| LaTeX error log to file | ✅ | keep |
| PDF location: default folder or choose | ✅ `pdf_location_raw` drives a save dialog | keep |
| **Names on/off** | ⚠️ dead *in Python* — the Sheet already applied it | one place, not two |
| **Submission cutoff** | ⚠️ read, never used, in both | implement or drop |
| **Seating-chart ordering** | ❌ prints in roster order | build |
| **Version count from seating** | ❌ | build |
| **Extras with blank names** | ❌ (`\setname{Blank}` exists) | build |
| **Shuffled extras** | ❌ | build |
| **Keys optional** | ❌ always emitted if `Key Amount` > 0 | make an explicit toggle |
| **Recompilable output folder** | ⚠️ partly — `TeX Outputs/` exists | make it a guarantee |
| **Google Forms read** | ❌ manual CSV export | build |
| **Google Forms write** | ❌ | build |
| **Selecting variants** | ❌ n/a | build |
| Simply Print / No-Sub default / Append | ✅ in Apps Script | keep all three |
| Available-skills list drives the Form | ✅ Apps Script | keep |
| Form validation (at most / least / exactly N) | ✅ Apps Script | keep |
| Email students who did not respond | ✅ Apps Script | **eventually**, in the tool |
| Printed log | ✅ a sheet | becomes tracking, §6c |
| **Attempt outcomes (took / passed / failed)** | ❌ | build, §6c |
| Per-skill print counts, page estimate | ✅ Apps Script | keep as a preview |
| Reset settings after a run | ✅ `printAndReset` | keep |
| **Auto-attached explanation skills** | ✅ Apps Script | **deprecated** — explanations are standalone outcomes now |

---

## 9. Staging

Each stage ends with something that works.

**1 — Package the existing tool.** `pdfgenerator.py` cleaned up, importable,
tested, driven by a structured roster file rather than a magic-header CSV. Same
output. Establishes the repo, the theme's home, and a golden-PDF comparison to
protect everything after.

**2 — Pregenerated seeds.** Swap generator-at-print-time for seeds 400–999, with
seed overrides mapping to seating versions. First point at which printing needs
no generator environment.

**3 — Publication file.** Replace the named cells. Skill selection modes
(Simply Print / No-Submission default / Append) move here.

**4 — Seating, extras, keys.** Group-based ordering with A/B alternation and a
collision warning; extras appended at the end with blank names and shuffled
versions; keys optional.

**5 — Output guarantee.** The canonical folder compiles standalone; a test
asserts it.

**6 — Tracking.** Record what each student received; a way to mark outcomes
afterwards. Storage first, editor later.

**7 — Google.** Read responses, then write the form.

**8 — Assessment-builder convergence.** The theme becomes the viewer's default
assessment template, inlined with `filecontents`. Depends on the figure decision
in §6b.

**9 — SpaTeXt fallback.** Skills with no `textemplate.tex` render through
`latex.xsl`. Last, because nothing needs it until a bank is authored without
print templates.

**Not staged: the seating GUI.** It is the eventual target, and the interim
seating file should be the format it will read and write, so the GUI is a front
end rather than a rewrite.

## 10. Decisions taken

Settled in review, recorded so they are not relitigated.

| | |
|---|---|
| Theme location | ships in the print package; a bank may replace it, same convention as `bank_helpers.sty` |
| Versions needed | **two**, avoiding *immediate* neighbours — not everyone at a table |
| Sections | share the A/B pool today; a seating chart may use other letters later |
| Seed overrides | user picks the seeds **and** their mapping onto seating versions |
| Extras | appended at the end, blank name line, versions shuffled among those available |
| Roster format | the tool's own structured file; CSV is an import step, never the model |
| Skill selection modes | all three kept, and they compose |
| Assessment export | carries answers |
| Tracking | in the tool, instructor-only, does **not** feed back into printing |
| Reproducibility | not a requirement — the tracking log records seeds instead |
| Output folder | canonical local path, rebuildable, never committed |
| Auto-attach | deprecated; explanations are standalone outcomes |
| Email missing students | in the tool, but far out |

## 11. Still open

1. Whether the interim seating file and the eventual GUI share a format from the
   start. Recommended yes; it costs nothing now and avoids a migration.
2. Which figure route to take for self-contained assessments (§6b): raise
   `--image-seeds`, publish `.tikz`, or base64. Recommended: publish `.tikz`.
3. Whether the two banks' identical `skillcheckpoints.sty` copies are deleted in
   favour of the package default, or kept until each course diverges.
4. What a hand-authored bank's `bank.xml` looks like, given the tool should keep
   `Skill Descriptions.tex` in step with it — MAT 206 has a real `bank.xml`
   already, so possibly nothing special is needed.
5. Whether `Submission Cutoff:` is implemented or dropped. It is read and unused
   on both sides today.
