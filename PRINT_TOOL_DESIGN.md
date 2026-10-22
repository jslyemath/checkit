# checkit-printit — design draft

**Status: stages 1-5 are built** (2026-09-20). Written 2026-09-01 from reading
`pdfgenerator.py`, `skillcheckpoints.sty`, `main_template.tex` and the 30
`textemplate.tex` files in mat-106, plus the requirements given in
conversation. Sections 1-11 are that original draft, still accurate except
where **section 12** revises them; 12 covers stages 6 and 7 and the GUI, and
is the current plan.

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

> **Revised by section 12.5 (2026-09-20)**, which settles form ownership, the
> question-id map, and how to find out whether the Google Cloud path is even
> open on a university account. The sketch below still holds in outline.


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

1. ~~Whether the interim seating file and the eventual GUI share a format from
   the start.~~ **Settled 2026-09-02: yes.** The GUI is a local web app that
   edits `seating.toml` in place, so there is only ever one format. Desk x/y
   positions go in the same file. See "Where we paused" in `CODEBASE_NOTES.md`
   for the full architecture.
2. Which figure route to take for self-contained assessments (§6b): raise
   `--image-seeds`, publish `.tikz`, or base64. Recommended: publish `.tikz`.
3. ~~Whether the two banks' identical `skillcheckpoints.sty` copies are deleted
   in favour of the package default.~~ **Overtaken by events 2026-09-02.** They
   are no longer identical: mat-106 and the printit package carry a color fix
   that mat-206 does not, and mat-206 is to be rebuilt from scratch rather than
   kept in step. Revisit once that rebuild happens.
4. What a hand-authored bank's `bank.xml` looks like, given the tool should keep
   `Skill Descriptions.tex` in step with it — MAT 206 has a real `bank.xml`
   already, so possibly nothing special is needed.
5. Whether `Submission Cutoff:` is implemented or dropped. It is read and unused
   on both sides today.

---

## 12. Local state, Google Forms, and the GUI (2026-09-20)

Stages 1-5 are built and in use: a real class set of 48 students printed on
2026-09-18 from form responses. This section is stages 6 and 7 plus the GUI,
and revises 7, 10 and 11 where they disagree.

### 12.1 The course

**The problem, concretely.** A job folder is self-contained: `publication.py`
resolves `[roster] path` relative to the publication file, so every job carries
its own copy of the roster and the seating chart. The 2026-09-13 run got its
seating by copying the 2026-09-10 run's file. Three copies of the same 48
students now exist on disk.

A student drops. Which file is edited? The next job is made by copying the last
one, so the fix has to be remembered and reapplied at copy time. Miss it and
they get a paper. Nothing detects the drift, because three files that disagree
are three valid files.

**A course folder is the home for state that outlives a job.**

```
~/CheckItPrintIt/
├── courses/
│   └── MAT 106/
│       ├── course.toml         name, code, semester, professor, bank path
│       ├── roster.toml         last, first, preferred, sid, email, section, dropped
│       ├── seating.toml        groups + desk x/y -- the GUI's file
│       ├── availability.toml   skills open for retake + the next assessment
│       ├── form.toml           form id, item ids, last pushed state
│       ├── record.db           SQLite: what was printed, to whom, at which seed
│       └── secrets/            OAuth client + token cache
├── jobs/<job>/                 publication.toml only
└── MAT 106/<title>/            output, unchanged
```

**One course folder need not be one course.** An instructor may run both
sections of MAT 106 from a single folder with one form and `section` as a
roster field. Another may make "MAT 106 820" and "MAT 106 830" and keep
them wholly apart, each with its own roster, seating chart, form,
availability list and print record. Both are supported and neither is the
default. The directory is named by the instructor; nothing derives it from
the course code, and `course init` will make as many as you like.

**Resolution order in `publication.load()`:**

1. an explicit `[roster] path` -- use it, so every existing job folder keeps
   working unchanged;
2. else `[course] folder` -> `~/CheckItPrintIt/courses/<name>/roster.toml`;
3. else an error naming both options.

**Not a symlink.** `viewer/public/assets/bank.json` is a git symlink that
Windows checks out as a 35-byte text file containing its own target, which is
why the viewer dev server cannot load a bank on this machine. Resolution in the
loader is explicit, cross-platform and greppable.

Once roster and seating are shared, the manifest's existing `[inputs]` hashes
start meaning "the course roster as it stood that day", which is worth more
than a hash of a copy.

### 12.2 Roster, and importing from Banner

```toml
[[student]]
last      = "Brienza"
first     = "Matthew"
preferred = "Matt"          # what prints; falls back to first
sid       = "806510955"
email     = "mbrienza@oswego.edu"
section   = "830"
dropped   = false
```

**Legal and preferred names are different fields.** The seating chart says
"Matt Brienza", "Seb Castrillon", "Kat Demars". A Banner export will not.
Without both, every re-import overwrites the name on the printed page.

**SID is the join key. Email is the fallback. Name is never a key.** SIDs do
not change; emails and names do. The Google Form collects email, so the roster
must carry both and a response maps email -> SID -> student.

**`dropped` is a flag, never a deletion.** The print record has to survive.
A dropped student is excluded from printing, from seating auto-fill and from
form pushes, and stays in every query.

**Importing is a merge, and absence is not deletion.** A student present in the
course but missing from a fresh Banner export is marked `dropped = true`,
not removed. A re-import must not clobber `preferred`, `section` overrides, or
anything the seating chart references.

The importer has to be forgiving, because Banner exports are not a format:

- find the header row rather than assuming row 1 -- scan for the row where the
  most known labels appear;
- map columns by matching against a synonym table, e.g. `sid` from
  `ID / Student ID / SID / Banner ID`, `last` from `Last Name / Last / Surname`,
  `email` from `Email / Email Address / E-mail`;
- print the mapping it chose and stop for confirmation before writing, with
  flags to override any column;
- accept `.csv` and `.xlsx`, because the exports that arrive are both.

Report adds, drops and field changes as three counts. Never a silent merge.

### 12.3 Availability

Which skills are open for retake, and what the next assessment is. One file,
because the form push and the print job both need exactly this:

```toml
[assessment]
name   = "Skill Checkpoint Redo"
date   = 2026-09-18
due    = 2026-09-17T23:59:00
choose = 3                       # at most N

skills = ["W1", "W1-E", "D1", "D1-E"]
```

Descriptions are **not** stored here -- they come from `bank.xml`, which is
already the single source for the printed skill headers and for
`Skill Descriptions.tex`. Copying them into a second file is how they drift.

Availability is **global, not per student**. The form shows one list to
everyone; a student who has already passed W1 still sees W1. Per-student forms
are not possible in Google Forms without one form per student.

### 12.4 The print record

**The rule: if a human is the author, TOML. If the tool is the author, SQLite.**

Roster, seating, availability, course config, form config and publication are all
hand-edited or GUI-edited, bounded in size, and read by eye. The print record
is none of those things:

- it never stops growing -- 48 students times three papers times fifteen
  assessments is about 2,000 rows a term;
- every question asked of it is a query ("how many times has this student
  attempted W1", "what did she get on 9/17", "which skills has nobody passed"),
  which is one line of SQL or a hand-rolled index over TOML;
- two processes write it -- the CLI at build time, the GUI when marking the
  gradebook. SQLite takes a lock; two writers rewriting a TOML file race and
  the loser's write vanishes silently;
- `sqlite3` is in the standard library.

```sql
CREATE TABLE run (
    run_id  TEXT PRIMARY KEY,      -- the output folder name
    title   TEXT NOT NULL,
    date    TEXT NOT NULL,
    built   TEXT NOT NULL,
    seed    INTEGER NOT NULL,      -- so a replay is findable from the record
    output  TEXT NOT NULL
);

CREATE TABLE printed (
    printed_id INTEGER PRIMARY KEY,
    run_id     TEXT NOT NULL REFERENCES run(run_id),
    sid        TEXT NOT NULL,      -- never the name
    slug       TEXT NOT NULL,
    seed       INTEGER NOT NULL,
    version    TEXT NOT NULL,
    variant    TEXT
);
CREATE INDEX printed_by_student ON printed(sid, slug);
```

Written at build time from the manifest, which already records seed, version
and variant per paper -- the record is a second reader of a file that exists.

**Printed is not attempted.** The build cannot know who was in the room.
`SELECT COUNT(*) FROM printed WHERE sid=? AND slug=?` counts papers handed out,
which over-counts anyone absent. The **gradebook** -- pass, no pass, absent --
is a separate table added in a later stage, and until it exists the tool must
say "printed N times", never "attempted N times".

Tracking still does **not** feed back into printing (section 10). There is no
retake cap to enforce.

### 12.5 Google Forms

**printit owns the slots it can derive, and nothing else.**

| item in the form | owner |
|---|---|
| banner image, theme, title, description | instructor |
| email collection, response receipt | instructor |
| "You are selecting *three* skill(s)... on *NAME* on *DATE*" | **printit** |
| "I understand that I am selecting skills for *DATE*" | **printit** |
| "This form is due by *DUE*" | **printit** |
| "How do I decide what to choose?" -- grade cutoffs, syllabus links | instructor |
| "Choose At Most *THREE* Skills" and its options and validation | **printit** |

The "How do I decide" block holds grade cutoffs, a link to the skill list and a
link to the syllabus. No field in printit knows any of it, and it changes on the
instructor's schedule. A push that regenerated the form would delete it every
week.

If a slot printit owns has been deleted from the form, push **stops and says
so** rather than recreating it -- because recreating changes an id.

**Responses are stored against `questionId`.** That single fact drives the rest:

- recreating the *form* changes the `formId`, so the URL dies and every response
  already collected is stranded on a form nobody can reach, along with the
  banner image and every per-form setting;
- deleting and recreating a *question* changes its `questionId`, so answers
  already given stay attached to the old question. The skills question changes
  its options every week; recreating it weekly would leave fifteen half-empty
  columns in the export by December.

So the ids are recorded once and patched forever after:

```toml
[form]
id  = "1FAIpQLSc..."
url = "https://docs.google.com/forms/d/e/.../viewform"

[items]
selecting_for = "3f8a1b2c"
confirm_date  = "7d2e4a91"
due_notice    = "1a9c3e70"
choose_skills = "5b6f8d22"   # options rewritten weekly, id never
```

A push is one `batchUpdate` of `updateItem` requests. No creates, no deletes.

**Two entry paths.** *Adopt* reads an existing form, lists its items and asks
once which is which -- that is how an instructor's banner and wording survive.
*Create* builds one when there is no form yet and records the ids it gets back.

**To verify against the API reference before implementing**, rather than guess:
the exact shape of `updateItem` and its `updateMask`; whether `forms.create`
accepts only `info.title` at creation with everything else needing a follow-up
`batchUpdate`; and how "at most N" validation on a checkbox question is
expressed.

**Whether the Google Cloud path is open at all** is a university question, and
worth answering before writing any of it. Signed in on the institutional
account: create a project at `console.cloud.google.com`; then under
APIs & Services -> OAuth consent screen, check whether **Internal** is offered
as a user type. Internal apps in a Workspace skip Google's verification review
entirely, which is the difference between an afternoon and a fortnight. Then
enable the Google Forms API in the Library, and create an OAuth client ID of
type **Desktop app**.

A Workspace admin can also restrict third-party app access domain-wide, which
only shows up at the first token request.

**Settled 2026-09-20: the institutional account cannot create Cloud projects,
so Apps Script is the primary path and the Forms API is the alternative.** The
existing Control Center is already an Apps Script that writes this form, which
is proof the permission exists and that the approach works.

A **script bound to the form**, deployed as a web app executing as the
instructor, needs no Cloud project, no OAuth client, no consent screen and no
token. printit calls it over HTTPS.

**Correcting a claim made while reaching that conclusion:** a CLI *can* do an
interactive browser login. The OAuth installed-application flow opens the
system browser and catches the redirect on `http://localhost:<port>`;
`InstalledAppFlow.run_local_server()` is a dozen lines. What a CLI cannot do
without a Cloud project is *have an OAuth client to log in with*. So the web
app authenticates with a shared secret not because interactive login is
impossible, but because the alternative needs the unavailable thing. If the
access situation ever changes, this reverses.

A web app that can rewrite the form is a capability URL. It must require a long
shared secret in the request body and reject anything without it; the secret
lives in the course's `secrets/` directory.

**Deployment is not copy-and-paste.** `clasp`, Google's Apps Script CLI, clones
a script to local files and pushes them back:

```
clasp clone <scriptId>   # once
clasp push               # after every edit
clasp deploy             # publish a new version of the web app
```

The script source then lives in the printit repository as ordinary files, in
git and reviewable in a diff. `clasp login` uses clasp's own OAuth client, so
it needs no Cloud project -- but it does need the Apps Script API switched on
at `script.google.com/home/usersettings`, a per-user toggle an admin can lock.

**The CSV fallback survives the Sheet.** Google Forms exports responses to CSV
from the form itself, so the import path in 4.2 keeps working with no
spreadsheet in the picture.

**The CSV import path stays permanently.** Scopes lapse and admins change
policy; the CSV path is the whole pipeline minus one adapter and it works
today.

### 12.6 The GUI

**Written 2026-09-02 as "the seating chart", and not revisited while the CLI
grew to 22 commands.** The instructor's question on 2026-09-21 -- why is none
of this recorded -- was fair. What follows is derived from two sources rather
than from imagination: the CLI as it now stands, and the menu the retired
Control Center actually offered.

#### It is the front end for the whole tool, not a seating widget

The Control Center was a Google Sheet an instructor sat in front of all term.
Replacing it with a CLI plus one drag-and-drop page replaces the seating menu
and nothing else. Every other thing that used to be two clicks is now a
command line with a `-c` flag.

<!-- audit-ignore -->

**Load-bearing rule: the GUI calls the same functions the CLI calls.** No
second implementation of anything -- not the roster join, not the selection
modes, not the push payload. On 2026-09-21 the same fix had to be applied
three times in one day because three code paths did the same job (`"-w"` in
option definitions vs ` -w ` in messages vs `` `-w` `` in a table;
`_deploy_and_record` vs `form attach`'s own copy; `form connect` missing both).
A GUI that reimplements any rule doubles that problem permanently. The CLI
command bodies should be thin wrappers over functions the web handlers also
call, and anything currently living inside a `@click.command` body that the
GUI will need has to move out first.

#### The views

Derived from the CLI surface and the Control Center's menu. "CLI" names the
command that already does the work.

| view | what the instructor does | CLI |
|---|---|---|
| **Roster** | an editable table: the name, what it prints as, section, email, ids; mark dropped and undo it; import a class list and see the merge before it lands | `roster import`, `roster drop`, `roster restore` |
| **Skills** | toggle which skills are open for retake; set the assessment's name, date, due time, and the choose/limit rule; see the exact wording the form will show; push it | `skills open`, `skills set`, `skills preview`, `form push` |
| **Responses** | who has answered, who has not, what they chose; the addresses that matched nobody; pull into the roster | `form pull` |
| **Seating** | drag students between seats; randomise; swap two; see version letters and empty seats | *(none -- see below)* |
| **Print job** | the staging area for one sitting: each student's choices with a manual override, skills appended for everyone, defaults for non-responders, per-skill variant, title and date, extras, keys, names; preview the draw; build; open the PDF | `build`, `build --preview` |
| **Runs** | past runs: when, which seeds, drill in, reprint, delist | `record runs` |
| **Progress** | each student against each skill: passed, passes, attempts | -- |
| **Scans** | read marked papers back in and grade them | -- |
| **Cold call** | pick a random student, pick several, refresh the call list with its skip flags | *(none)* |
| **Setup** | create or attach the form, map items, course settings, bank path | `course init`, `form create`, `form attach`, `form map`, `form add-items`, `form connect` |

The last column is the useful part of this table: most of the GUI is a face on
code that exists and is tested. The two rows with no CLI are the genuinely new
work, and **seating is one of them** -- `randomizeSeating` and
`shuffleSelectedStudents` were Control Center features that have no printit
equivalent at all. That is worth knowing before estimating.

#### One name per view

Kept in one place because it has already drifted twice. The staging table
said **Skills** after the tab became **Update form**, and **Assessment**
after the app had settled on **Print job** -- both because a view was renamed
in the plan and not in the nav, or the reverse.

`Print job` beats `Assessment` for 8d on a collision: Update form already has
a panel headed "The next assessment", and `availability.toml` an
`[assessment]` table, and those are a different thing. "Print job" names what
comes out of it.

**The nav is the authority. When a view is renamed, this table is renamed in
the same commit.**

#### Settled, and what each one cost

All three decisions are closed.

**The preferred name prints, everywhere** (2026-10-01). Above.

**Responses is not a tab** (2026-10-01, built). The pull is Print job's
first card, so the weekly flow reads top to bottom on one page: pull, see
the choices, override, build. The failure modes the pull has of its own -- an
address matching nobody, a skill no longer in the bank, a response for
another day -- are reported in that card rather than given a view. "Who has
not answered" comes back as its own thing when *email missing students*
exists, which is the part of responses that is genuinely not about
assembling a print job.

The card reports counts and every reason a student might not get the paper
they asked for, and deliberately does not list who chose what -- the table
two cards down is the view of that, and two views of one set of facts is
the reason this is not a tab.

**Simply-print is a mode** (2026-10-01). A segmented control at the top of
the tab, chosen over radios, a dropdown-in-a-sentence and a checkbox by
rendering all four in the app's stylesheet and looking at them.

Segmented wins because the app already contains that control -- the view
nav is one -- so it adds no vocabulary, and switching mode changes which
cards exist, which is what a nav-shaped control is for. It is deliberately
smaller than the real nav, with "This run:" in front of it.

The layout half was only half the problem. `simply_print` replaced each
student's choices and killed `default_when_missing`, while the job folder
carried all three keys regardless -- so a saved `publication.toml` could say
one thing and hold settings for the other. `publication_text` now writes
only the half the mode uses, and a draft written before the mode existed
says which it is by whether `simply_print` has anything in it.

#### What the Print job table has to say for itself

Settled 2026-10-01, from six reports against the first build of the view.
Each is a case of the screen having to state a rule rather than the
instructor having to hold it.

**A default is shown by being selected, not by being listed twice.** The
version dropdown had a nameless first option carrying the seat's letter and
then the letters themselves, so a student at A saw "A" twice. The outline
already says when a row is off its default. A `↺` beside the control --
`U+21BA`, the glyph in common use -- appears only when it is, with one of
the same at the head of the column. Choosing the seat's own letter clears
the pin rather than recording one that changes nothing, so "off default"
and "has a pin" cannot drift apart.

**A new version is added where versions are chosen.** Each dropdown offers
the letter after the highest in play: `+ E`, and once E is taken, `+ F`.
Next-after-highest rather than first-unused, because a chart of A, B, D
would otherwise offer C, which reads as a mistake rather than as a new
version. Both ends had to agree -- the save stopped requiring a letter the
chart already had, and `assemble.versions_for` draws seeds for whatever the
pins name.

**Reset is an edit, not a command.** "Reset this print job" fills the draft
with the server's defaults and leaves saving to Save, so Discard puts the
old job back. A button that wrote the file directly would be a way to lose
a job in one click.

**A view that caches has to say when it has stopped.** Print job loaded
once per page load, so a name saved in Roster never reached it. It reloads
on every visit now, keeps any unsaved draft, and names what changed. The
original request was for a note saying the changes would merge at the next
Save; there was never a merge to wait for -- saving was simply the only
code path that re-fetched.

#### The roster is the course; choices belong to one sitting

Decided 2026-09-22, on seeing the first roster table. It had a "Chose" column
showing each student's current selections, which was wrong twice over: what a
student picked belongs to *one assessment*, and the roster outlives every
assessment. A column that changes meaning each week does not belong in the
table that holds who is enrolled.

So the **Roster** view is the course overall -- who exists, what they are
called, which section, who has left -- and never mentions an assessment.

Choices live in the **Print job** view instead, which is a staging area for
one sitting rather than a form with a Build button on it: each student's
choices shown with a manual override, skills appended for everyone, defaults
for whoever did not respond, the per-skill variant, the title and date, the
extras. It is where an instructor assembles the paper before printing it,
which is what `importStudentChoices` did in the Control Center.

#### What the GUI needs that the CLI does not

1. **Variants, per skill, in the print job view.** Eight of mat-106's
   twenty-nine outcomes declare variants, and the labels are not guessable:

   | skill | variants |
   |---|---|
   | `R2` | `beginning`, `add_sub_frac`, `mult_div_whole`, `int_pemdas` |
   | `W4`, `W4-E`, `W5` | `multiplication`, `no_multiplication` |
   | `W7` | `terminating`, `no_terminating` |
   | `N3`, `N4` | `any_method`, `listing_only` |
   | `D2` | `repeating`, `no_repeating` |

   On the command line this is `[variants] D2 = "no_repeating"` in
   `publication.toml`, typed from memory. In a GUI it is a dropdown that has
   to be **populated from the bank**, which means enumerating
   `Bank.variant(slug, seed)` across the print tier and caching it -- there is
   no declaration to read, the label is written into each version's data by
   the generator wrapper. `Bank.seeds_with_variant` already refuses a variant
   with no printable version; the GUI should never offer one.

2. **A job is currently a folder.** `build` reads `publication.toml` from a
   directory. A GUI has no directory -- the instructor sets options in a form
   and presses Build. Either the GUI writes a job folder and calls `build`
   on it (keeping one code path and leaving a folder to inspect, which is
   also what `--replay` needs), or `build` grows a non-folder entry point.
   **The first.** The folder is the artifact that makes a run reproducible,
   and inventing a second way in is exactly the duplication the rule above
   forbids.

3. **Long operations.** `build` compiles LaTeX and `form pull` crosses the
   network. Both need progress and a readable failure, not a spinner that
   ends in "something went wrong". The CLI's own messages are already written
   for a human; they should be streamed rather than rewritten.

4. **Confirmation before anything outward-facing.** `form push` rewrites what
   students see. The CLI has `--dry-run`; the GUI needs the equivalent as a
   visible diff, not a checkbox.

#### The form's fixed wording, and who owns it

Decided 2026-09-29. printit creates the form, so **printit is the source of
truth for every word on it** -- not whatever an instructor last typed into
Google. The alternative loses the wording the first time a form is rebuilt,
silently.

`src/checkit_printit/boilerplate.py` holds it: the form's title and
description, the heading above each item, and any section that stays the same
all term. The wording that changes weekly -- which assessment, which date,
which skills -- is still derived in `form.payload_for` and rewritten on every
push.

**Two items are required and appear on every instructor's form:**

| | why it cannot be left out |
|---|---|
| `confirm_date` | the scoping key. `form pull` decides which assessment a response belongs to by reading the date a student confirmed. A form without it cannot be read back at all |
| `choose_skills` | the question itself |

Their *wording* is editable; their *presence* is not. Everything else -- the
form description, "What am I selecting skills for?", "When is this form
due?", "How do I decide what to choose?" -- is optional, and an instructor
may reword it or leave it out.

The item titles used to live in `appsscript/Code.gs`, where `addItems_`
created them. They are in `boilerplate.py` now and passed across in the
payload, because a title in two places is a title that will disagree with
itself.

**Not yet supplied:** the text of "How do I decide what to choose?". It is on
the live MAT 106 form, added by hand, and printit has never had it. The
preview shows the section with a dashed border saying so, rather than
rendering it empty, which would read as "this section is blank on the form".

#### Still to build, in this area

**A boilerplate editor.** Change the fixed wording, and choose which optional
sections to include. Touched at the start of a semester or in an emergency,
which is the whole problem with placing it -- see below.

**Creating a form from the app.** `form create` exists on the command line
and does the whole job: form, bound script, deploy, items, recorded ids. The
GUI should offer it rather than sending an instructor to a terminal, with
somewhere to say which Drive folder it goes in.

#### Where the boilerplate editor goes

The question is real: it is edited perhaps twice a year, so a tab of its own
overstates it, and a sub-tab inside Update form buries a rare thing inside a
weekly one.

**Recommendation: it lives in Setup, with a door from the preview.**

Setup already exists on this roadmap for the things done once -- `course
init`, `form create`, `form attach`, `form map`, the bank path. The
boilerplate has exactly that cadence, and grouping by *how often you touch
it* is what keeps the weekly views uncluttered.

The second half matters as much. An instructor notices the wording is wrong
**while looking at the preview**, not while thinking "I should visit Setup",
so the Form preview panel carries an `edit wording` link that opens it. Put
it where the cadence says; provide a door where the need arises.

The tempting alternative -- make the preview itself editable, click a
sentence and change it -- is worth naming and rejecting. The preview is
consulted every week before a push, and making it editable invites an
accidental edit to something meant to be stable. Worse, it erases the
distinction the design is built on: some of that text is rewritten by every
push and some is not, and a preview where everything looks equally editable
teaches the opposite.

#### Architecture, unchanged

A local web app with a Python backend, bound to `127.0.0.1` and never
`0.0.0.0`, editing the same TOML files the CLI reads. It carries names, SIDs
and email addresses, so it lives outside every repository along with
everything else in `~/CheckItPrintIt/`.

Correcting the 2026-09-02 note again: it said "everything stays in git", which
is wrong for exactly that reason.

#### Staging within 8

Ordered so that the riskiest unknown is not last, and so each slice is usable
on its own:

| | slice | why here |
|---|---|---|
| 8a | **done** -- the shell: serve a course, switch views, read-only everywhere | proves the backend reads what the CLI reads |
| 8b | **done** -- **Roster** table, editable, with drop and restore | the most-wanted, and write-round-trip is the thing to get right early |
| 8c | **done** -- **Update form**: the open skills, the assessment, the wording preview, the push | replaces the most tedious CLI sequence |
| 8d | **done** -- **Print job**: choices with overrides, defaults, variants, then build | the first view that needs the bank, not just the course |
| 8e | ~~**Record**~~ -- became Runs, Progress and Scans; **see section 14**. The response pull landed inside the Print tab instead of becoming one | |
| 8f | **Seating**, drag and drop, plus randomise and swap | genuinely new code; the interaction needs prototyping rather than specifying |
| 8g | **Cold call** | new, and the smallest |
| 8h | **Setup**: create or attach a form from the app -- **done**; the boilerplate editor still to come | both are start-of-semester work, and the editor needs somewhere the weekly views do not |

Seating is deliberately not first. It was the whole of this section for three
weeks, it is the only view whose *feel* cannot be settled in writing, and it
is the one an instructor can most easily do by hand in the meantime.

#### Open

1. **Does the roster table edit in place, or stage a diff?** Editing in place
   is nicer; `roster import` already shows a merge before it lands, and a
   table that silently rewrites `roster.toml` on every keystroke removes the
   one moment where a bad import is catchable.
2. **How is a print job's history surfaced?** `record.db` knows every run, and
   the job folders are on disk. The GUI could list past runs and offer
   `--replay` on any of them, which would make reproducibility a button
   rather than a documented procedure.
3. **Multiple courses at once**, or one at a time with a switcher. An
   instructor running 820 and 830 as separate courses will want to see both.
4. **Email missing students** was a Control Center feature with a templated
   body and `$FIRSTNAME`-style substitutions. Deferred, but it is the obvious
   home for it once Responses exists, and the variable set is recorded in
   12.10.

### 12.7 Staging

| stage | state | ends with |
|---|---|---|
| 6a course + roster | **done** | one roster, jobs resolving it, class lists merging on id |
| 6b availability | **done** | a list the form push and the print job both read |
| 6c print record | **done** | SQLite written from the manifest; queries read-only |
| 7a form write | **done, verified** | create-or-attach, then push the derived slots |
| 7b form read | **done, verified** | responses pulled to the day's skills; CSV kept |
| 8 GUI | | a front end for the whole tool: roster, skills, responses, print job, record, seating, cold call. See 12.6 |
| 9 gradebook | | pass / no pass / absent, and the table editor for it |

### 7a ran against a real account on 2026-09-21

`form attach`, `form add-items`, `form push --dry-run` and `form push` all
work end to end against a scratch form on the institutional account. Seven
bugs were found, in code that had 220 passing tests. Full account in
`CODEBASE_NOTES.md`, "Stage 7a, against a real Google account".

**The largest open risk in this design is now closed.** An anonymous POST
from a terminal holding no Google credential is accepted, so the
open-with-a-secret transport works on this domain. The 403 that suggested
otherwise was an unauthorized script, not a policy block.

Neither predicted failure happened. `_deployment_id` parsed correctly first
time, and `.clasp.json` landed where `script_id()` expects. What actually
broke was elsewhere:

- `--type form` is not a type; it is `forms`. And `push-files` is not a
  command; it is `push`. Untestable at the old seam, because the tests
  assert on what the deployment replies and never on the argv.
- **clasp exits 0 on a refusal**, so `check=True` passed an invalid `--type`
  straight through.
- **`clasp create-script` overwrites `appsscript.json` in `--rootDir`**,
  dropping the `webapp` block, so the deployment had no entry point. `attach`
  was already immune because it re-stages over the cloned files.
- **Apps Script 404s a live deployment at random** -- measured at one in
  three. `call()` retries 404 and timeout, never 401/403.
- `--title` names the script project, not the form. A `rename` op fixes it at
  creation only; a push must never touch the title.

**Still to do in 7a:** `form create` has not been run to completion, only
`form attach`. A newly created form needs **one browser visit to authorize
the script** before any call succeeds -- the manual path gets this free from
the editor's deploy flow, and the clasp path does not. `form create` should
print the URL and wait.

### 7b read a real response on 2026-09-21

Checkbox answers are arrays, `getRespondentEmail()` is populated, and the
option text round trips as `SLUG - description`. Matching, date scoping and
the refusal-to-write were all exercised against that one live response, not
only against fixtures. See "7b against a real response" in the notes --
including the submission whose three dates (submitted 9/21 Eastern, recorded
9/22 UTC, for the assessment on 9/25) make the case for confirmation-based
scoping better than this document did.

### What 7b needed

Responses are scoped to an assessment **by the date the student confirms**,
not by a timestamp window -- see 12.10. The confirmation checkbox exists for
that. Latest response per student wins. Both behaviours come from the retired
script and are already matched by hand in the 2026-09-18 run.

The script needs a `responses` op returning email, timestamp and choices;
printit maps email to a student through `Student.all_emails()`, which is why
addresses accumulate rather than replace.

### 12.11 The seating tab, specified (2026-10-04)

Four ways of *rendering* a chart were drawn and all four rejected. What is
wanted is a way of **drawing a classroom** -- a seating-chart tool that
would work for any class anywhere, not a view of `seating.toml`.

#### What it is

A canvas per section, seen from above, showing an empty classroom before
anybody is placed in it.

* **Background shapes** are dragged on to match the real room: 2x2 tables,
  1x2, 1x3, single desks, hexagons, trapezoids, circles, ovals. A single
  desk is a 1x1 rectangle with one seat.
* **Each shape carries default seat positions**, and there is a mode for
  dragging those positions around, because a real table has a side against
  a wall.
* **Name cards** drop onto seats. First name on the top line, surname
  below, so the card is squarish rather than a long strip -- which is what
  sets the spacing of the whole room.
* **Group designators** -- a table number, a color, a letter -- sit in the
  middle of a table, or float in the gap for a room of loose desks. A shape
  can carry a label and a standalone label can be dropped anywhere.
* **Version letters toggle**, because this goes on the projector.
* **Sections are separate charts**, chosen from a picker, and the
  instructor says which section's papers print first.

#### Who owns what

The division is the instructor's, and it is the whole model:

| | owns |
|---|---|
| a desk or table | the seat positions on it |
| a group | its label, the version letters of its seats, and where it comes in the print order |
| a seat in no group | behaves as a group of one, in every one of those rules |

That last line is what makes a room of loose desks in rows work without a
second code path.

#### Versions are chosen here

The seating tab decides the version letters and writes them down.
`alternate()` stays only as the fallback for a chart this tool did not
write. Within a group the letters are dealt without repeats; where a group
is larger than the bag of letters, the repeat is placed as far away as it
can be. There is **one bag of letters for the whole course**, across
sections: a group of six with six available gets one of each, a pair gets
two of the six.

This is graph coloring -- see the notes of 2026-10-04 for the algorithm
and the measurements behind each part of it.

#### Print order is a mode

A mode that brings up the print order, in which the instructor clicks the
groups one at a time in the order they will hand papers out; in an
ungrouped room, individual students. Sections are ordered too, and the
stack is all of one section and then all of the next.

A group left unplaced is a **warning, not a refusal**: the instructor may
go ahead knowing that anyone unmarked will probably be printed out of
order.

#### Two files, and why

`seating.toml` stays exactly as it is, for CLI users and for the build.
The seating tab produces it. The app's own data -- geometry, shapes, seat
anchors, groups, the canvas size -- lives beside it in `room.json`.

JSON because it is deeply nested and nothing hand-edits it. Not SQLite,
despite the rule that tool-authored state goes there: that rule is for
something unbounded, queried, and written by two processes at once, and
this is one small document read whole and written whole, worth diffing
when a room changes.

A room holds each student's **id**; names appear only in the generated
chart. `seating.toml` is the last name-keyed join in the tool, and a room
cannot be broken by a rename.

**No migration.** The live 106 charts are being redrawn by hand, which the
instructor preferred to a converter nobody would run twice.

#### Staging

| | | |
|---|---|---|
| 1 | the model, the coloring, the chart writer | **done** 2026-10-04 |
| 2 | the canvas, read-only: shapes, cards, labels, section picker, toggles, zoom | **done** 2026-10-05 |
| 3 | dragging -- cards between seats, shapes around the room | **done** 2026-10-05 |
| 3b | the sizing pass: fit to content, a projector mode, click-to-place | **done** 2026-10-05 |
| 4 | the shape palette, and dragging seat anchors | next |
| 5 | the print-order mode | |
| 6 | randomise, and swap two | |

Stage 1 was invisible and decided everything after it. Stage 2 is
projectable on its own.

Stage 3 settled two things the plan had left open.

**The tab is three modes, not one canvas with handles.** *View* moves
nothing and is what goes on the projector; *People* drags names between
chairs; *Desks* drags the furniture, with the name cards inert so a table
can be grabbed through the people sitting at it. The mode is named on the
canvas element, so "cards are not targets while desks are being moved" is
one line of CSS rather than a condition at every handler.

**Save writes the chart as well, when that is safe.** A room nothing
reads is a toy -- `seating.toml` is what the build opens. So saving the
tab rewrites it, under two conditions: somebody has to be seated, so an
untouched course cannot replace a term's chart with an empty one; and the
chart on disk has to be one this tab wrote, which `to_toml` marks and
`seating.was_generated` reads. A chart that came from an import or a text
editor is left exactly alone and the save bar says so **before** the
button is pressed. That is the 10-02 lesson made structural.

**Three modes, and a fourth that is not a mode.** View, People and
Desks are what the canvas lets you move. *Present* is not one of them:
it is the same View on the whole screen with every toolbar gone,
because the limit on how large a name can be drawn is pixels of screen
and the chrome was a third of them. Escape leaves; the arrows change
section while presenting.

Sizing is the thing that nearly sank the tab and it was three separate
faults, not one: fit scaled a declared canvas twice the size of the
furniture in it, the card's type filled under half the card, and the
banner took a quarter of a short window. All three are measured in the
notes of 2026-10-05, along with why counting characters is not the same
as measuring text.

This also opened a hole that had been harmless until now: `set_dropped`
cleared the chart and knew nothing about `room.json`, so the next save of
this tab would have walked a dropped student back onto the printed list.
A drop now empties their chair in the room too. See the notes of
2026-10-05.

### 12.12 The seating app: a shell of its own (2026-10-06)

Everything in 12.11 assumed the seating tab was a page with controls
arranged around a canvas. It is not going to be that. The instructor's
framing, which settles the whole design:

> The fullscreen version **is** the regular version, except without
> checkit-printit's header bar stuff.

So the seating tab is **an application that happens to be embedded in
checkit-printit**. Its canvas runs edge to edge, its own controls float
over that canvas, and Present does exactly one thing: hide the host's
header. Nothing else moves, nothing else changes size, nothing appears
or disappears.

That is also what makes the eventual spin-off cheap. Seating and
Up Next are to become their own application; if every control already
lives inside the seating component, extracting it is deleting the host
header rather than rebuilding a UI.

#### Where this came from

Two canvas editors were read closely, because they have solved this:

* **Excalidraw** -- tools top centre, zoom bottom left, and a
  **contextual property island** that appears only when something is
  selected. The lesson taken: properties are about the selection and
  nothing else. There is no settings panel.
* **tldraw** -- tool strip **bottom centre**, style panel to one side,
  zoom bottom left, app menu top left. The lesson taken: the overall
  placement, and that every panel is a small floating "island" over a
  full-bleed canvas rather than a region docked into a page.

**Radix Colors** supplied the color model, and the classroom tools
surveyed in the notes of 2026-10-05 supplied click-to-place.

#### The islands, and what each one is for

Five fixed positions. Each answers one question, and nothing lands in a
position because there was room for it there.

| where | question it answers | holds |
|---|---|---|
| top left | *which room am I in, and is it saved* | the section switcher, and -- only when there are unsaved changes -- **Save** and **Discard** |
| top right | *how is the room being shown* | version letters, group labels, **Up Next**, **Projector mode** |
| bottom left | *what am I looking at* | zoom out, the percentage (click to fit), zoom in, **fullscreen** |
| bottom centre | *what am I doing* | the mode rail, which furls to the current mode below ~760 |
| just above the rail | *what is selected* | one thin strip, described below |
| bottom right | *one more of these* | the plus: a group in Groups, a seat in Seats |
| the right edge | *who is not seated yet* | the unseated rail, in People mode |

Three corrections to the first draft of this table, each from using it.

**The hamburger is gone.** It hid two switches, and two switches are
cheaper to show than to hide.

**Top right is not Present alone.** Getting the chrome out of the way
and putting the room on a wall are the same question, so the display
switches live there with it -- and fullscreen does not, because that is
a question about the view and belongs with the zoom, which is where
tldraw and Miro both keep theirs.

**No unsaved-changes dot.** It announced a state that the presence of
Save and Discard already announces.

**Up Next is not a mode.** The rail's test for belonging is whether an
entry changes what a click on the canvas means; Up Next never did, it
changes what the room is *showing*. It is a switch in the top right
with the other two, and it works while projecting because that island
is the one that survives.

**The accent color means one thing: the state you are in.** Not "look
at me". A switch that is lit while unused has nothing left to say when
it is used. The plus is the one exception, because it is the only
control that makes something that was not there.

#### The camera

The canvas does not scroll. There are no scrollbars at any size: the
room is panned by taking hold of the paper, and zoomed with the zoom
island. Two numbers say where the view is -- a scale, and a pan offset
in screen pixels from where Fit would put the room -- and one function,
`freeBand`, returns the rectangle the room is both **fitted into and
centred in**. Those must be the same rectangle or the room is neither.

Fit resets both. Zoom holds the middle of the window rather than the
room's centre, so what you were looking at stays in front of you.

**Save sits with the document, not with Present.** What is saved is this
room, and the room's identity -- the menu, which section -- is top left.
Figma puts the file name and the file's own menu in the same corner for
the same reason. Save is also **absent until there is something to
save**, which is the real answer to "why is that button there": most of
the time it should not be.

**Zoom is bottom left and Present is top right, at every width.** An
earlier draft moved zoom into the top right when the window got narrow,
so the same two controls were in two different places depending on the
window. The fix is not to move the control, it is to make the rail
narrower: below 760px the rail drops its words and keeps its icons,
which leaves the bottom edge wide enough for both.

#### The mode rail

Six modes, all of them visible at once, because the point of a rail is
that the whole verb list is the rail:

| | |
|---|---|
| **View** | nothing moves. The projector |
| **People** | names between chairs |
| **Groups** | the furniture: add, move, resize, turn |
| **Seats** | where the seats sit on a group, how many, and which group they belong to |
| **Order** | the order papers are handed out in |
| **Up Next** | pick somebody |

Modes only. **Shuffle is not on the rail** -- it is an action, and an
action among modes is a category error; it moves to the menu. The same
test keeps the rail honest as features arrive: if it does not change
what a click on the canvas means, it is not a mode.

#### A desk is a frame, and rotation lives in the chairs

A desk on the canvas is a wrapper carrying its position, its size and
its angle, with its silhouette, its eight resize grips, its rotation
handle and its nine label anchors inside it. They move and turn
together because they are one element's children -- the alternative,
a list of things to also update when a desk moves, is a list that
gets missed, which is how the anchors came to stay behind.

`shape.w`, `shape.h` and `shape.angle` are all optional and all
additive, so `room.VERSION` does not move.

**Rotating rewrites the chairs' own offsets** rather than storing an
angle for everything downstream to apply. `room.seats_of`, the
neighbour distances, the coloring and `seating.toml` therefore need
to know nothing about rotation: a seat is always simply where it says
it is. `angle` is kept only for the silhouette and for the next turn.

Resizing scales the chair offsets by the same factor, so a widened
table spreads its people out. It does not add chairs; adding one is a
button, and finding two new ones after dragging for room is a
surprise.

#### Bare, which is not the same as presenting

The top right holds two buttons, not one: an eye that hides every
control, and Present. They belong together because both are about how
the room is being shown rather than what is in it -- and it means
Present is not alone in an island of one.

The two states are separate. Presenting turns bare on; turning bare
off while still presenting is how every mode stays reachable on a
projector. **The top-right island is the one thing bare does not
hide**, because a mode with no visible way out is a trap. It rests at
low opacity when nothing is happening and returns on any movement.

The stage bar shows only while bare: with the islands back it is a
second answer to the same question.

#### Up Next, which used to be Cold call

The Cold call tab is **deleted**, not moved. Folded in as a mode it
stops being a list of names beside the room and becomes what it
actually is: **the room, with one chair lit up**. The chart is already
on the projector; picking somebody should light a chair, not replace
the screen with a different view.

Renamed because the students are looking at it. "Cold call" names the
teaching technique from the instructor's side and reads, to the person
whose name is on the board, as being put on the spot. **Up Next** is
the default -- it describes a state rather than pointing at somebody,
and it is short enough for the rail. "Who's Up" is the alternative and
is a one-word change.

#### The selection strip

The contextual panel in the first mockup was a tall island on the right
with four labelled sections, and it was wrong in both sizes. Most of it
was not needed:

* **The label-position picker is deleted.** Selecting a group already
  reveals the anchor points on its shape. Dragging the label pill onto
  one is the control; a nine-cell grid that does the same thing is a
  second way to say it.
* **Six color swatches in a row are deleted.** One filled dot showing
  the group's color, which opens the swatches when clicked.
* **The label does not need a text field and a heading.** The heading
  *is* the label; click it to edit it.
* **The print position does not need the words "Prints 2nd of 7".**
  `2/7`.

What is left is one thin strip above the rail, in both sizes, with no
expanded state:

```
  ●  Table 2            4 seats    2/7
  ^  ^                  ^          ^
  |  click to rename    read-only  print position
  color
```

Nothing in it needs opening, so there is no sheet to pull up and no
panel to collapse, which is what made it awkward at 515px.

#### The unseated are students, not a status line

They were a strip along the bottom labelled "2 standing". Two faults.
The strip said in words -- in slightly odd words -- what the design
should carry; and the cards in it were a different shape from the cards
in the room, so nothing about them suggested that one could be dragged
into a chair.

The rule: **an unseated student is the same object as a seated one.**
Same card, same size, same two lines. The only difference is that it
has no group, so it is drawn in the grey of the palette -- the same
three roles at zero chroma. Being grey *is* the status; no sentence is
needed.

It moves to **the right edge**, as a vertical rail, because a class
list is a list and because the left corners are already spoken for by
the document island and the zoom. The rail **has no header**, and
**hides itself when everybody is seated** -- except while a name is
being dragged, when it reappears as a drop target, because that is
exactly when somewhere to put a person is needed.

#### Under the menu

Everything that is neither a mode nor frequent:

* **Paper** -- the canvas color
* **Show** -- version letters, group labels
* **Deal the version letters again** -- the shuffle
* **Write the chart now** -- `seating.toml`, for when Save left it alone
* **Discard changes**
* **Room size**
* **Keyboard shortcuts**

The rule for the menu is the inverse of the rule for the rail: if it
changes what the canvas *is* rather than what a click *does*, and it is
not done every few minutes, it belongs here.

#### Color: one hue, three jobs

A group owns a hue. Three shades are derived from it, and they are
derived rather than chosen so that every group is the same design in a
different color. Radix Colors' twelve-step scale gives each shade a
job; the three the room needs are:

| drawn thing | job | step |
|---|---|---|
| the table or desk | the largest area, so it must recede | **3** surface, **6** border |
| a name card | sits *on* the table, so it must lift off it | **1-2** surface, **7** border |
| the group's pill | smallest, must be found instantly | **9** solid, white text |

Generated in OKLCH with lightness and chroma fixed per role and only
the hue varying -- `oklch(0.935 0.048 var(--hue))` and so on -- which is
about ten lines of custom properties and holds up on a light or a dark
canvas. An ungrouped seat uses the same three roles at **zero chroma**,
which is what makes the unseated rail consistent for free.

Color is never the only carrier: the pill still says "Table 2".

#### The canvas is a document; the chrome is a tool

The canvas gets its own light paper -- a very pale grey by default,
with other papers in the menu -- while the islands stay dark. That is
Figma's split, and it earns itself here twice over: it separates the
thing being made from the thing making it, and a light room is what a
projector wants.

It does mean **two visual languages inside checkit-printit**: Seating is
a canvas tool, the other tabs are forms and tables. That is deliberate,
and it is also the seam the spin-off will be cut along.

#### The label pill

Its silhouette is the point. Everything else in the room is a rounded
rectangle, so the one thing that is not reads as a label rather than as
another object: a full pill radius, solid, uppercase, and about 16 room
units rather than 11. Nine anchors per shape -- eight around the
perimeter and the centre -- shown as dots when the group is selected,
set by dragging the pill onto one. A group with no anchor set keeps the
present behaviour and floats at the middle of its seats, which is what
a room of loose desks needs.

#### What is narrow, and what changes

One breakpoint, at 760px. Below it:

* the rail keeps its icons and drops its words;
* the section switcher folds into the menu;
* the unseated rail narrows to one card wide;
* **nothing moves to a different corner.**

Zoom and pan is the accepted answer for a small pane, confirmed by the
instructor: the room is worked on zoomed in and read at Present. The
canvas does not try to show twenty-five legible names in 515px, because
it cannot.

#### What has to exist first

**There is no selection model.** Nothing in the app can currently say
"this group is selected", and the selection strip, the color dot, the
label anchors and the print position all hang off it. It is the
backbone and it comes before any of the features that need it.

#### Model changes, all additive

`group.hue`, `group.chroma`, `group.label_at`, `section.canvas.paper`.
Old rooms load with sensible defaults, so `room.VERSION` does not move
-- a version bump is for a change that would make an old file read
wrongly, not for one that makes it read incompletely.

**A color is two numbers and never three.** `hue` says which color,
`chroma` says how vivid, and lightness is not stored at all. The three
shades a group draws are built at fixed lightnesses chosen so a name
is readable on the card and the card is visible against the paper, on
a screen and on a projector and in print. Let the instructor set
lightness and the first dark color anybody picks makes a table whose
names cannot be read from the back of the room. The custom-color slot
therefore opens the platform's own `input type="color"` -- a visual
field, hex, RGB and an eyedropper, none of it to maintain -- and keeps
the hue and the chroma of whatever comes back.

#### Staging

| | | leaves it working |
|---|---|---|
| **A** | the shell: islands, mode rail, Present = host header off | **done** 2026-10-06 |
| **B** | selection, and the thin strip | **done** 2026-10-06 |
| **C** | the paper: light canvas, menu | **done** 2026-10-06; the choice of papers is still to come |
| **D** | group hue, three roles, grey for ungrouped | **done** 2026-10-06 |
| **E** | the pill and its anchors | **done** 2026-10-06 |
| **F** | the unseated rail moves right and becomes cards | **done** 2026-10-06 |
| **G** | Up Next folded in, the Cold call tab deleted | **done** 2026-10-06 |
| **H** | the camera: grab-to-pan, no scrollbars, one free band | **done** 2026-10-06 |
| **I** | Duplicate a group, with its seats, letters and label | **done** 2026-10-06 |
| **J** | the rail furls; hover to open; one motion vocabulary | **done** 2026-10-07 |
| **K** | nine hues and a custom one; `group.chroma` | **done** 2026-10-07 |
| **L** | Up Next out of the rail: one, a group, or one per group | **done** 2026-10-07 |
| **M** | Printing: the mode, seat letters split from print versions | **done** 2026-10-08 |
| **N** | the strip's two states: a group, or a seat | **done** 2026-10-08 |
| **O** | order numbers on the canvas, dragged or typed | **done** 2026-10-09 |
| **P** | versions: swap, shuffle, set the count | **done** 2026-10-09 |
| **Q** | click in order, and draw the route | **done** 2026-10-09 |
| **R** | per-section save and per-section print plan | **done** 2026-10-10 |
| **S** | band-select, move and delete; pan onto space and two fingers | **done** 2026-10-10 |
| then | 12.11's stages 4-6 land into the shell rather than beside it | |

#### What is actually left, 2026-10-10

In the order they would matter:

1. ~~By-seat ordering does not reach the paper.~~ **Done 2026-10-10**,
   with a format decision rather than a patch -- see 12.14 below and the
   notes of the same day. Everything in Printing now reaches the paper,
   verified against the written text and against the real room.
2. ~~The color swatches are the last unconverted disclosure.~~
   **Done 2026-10-10.** All four are now `.isle.drop`, built once and
   opened by a class, and `closeDrawers()` is the one place that knows
   what "everything is shut" means.
3. ~~12.11's stage 6.~~ **Done 2026-10-10**, as a shuffle and a pin --
   see 12.15. Swap-two was dropped: People mode already swaps two by
   clicking one and then the other, which is the gesture it would have
   duplicated. Stages 4 and 5 were already built: the palette and seat
   dragging, and the print-order mode is Printing.
4. ~~The paper color choice.~~ **Done 2026-10-10**, as
   `section.canvas.background` -- four named light values in the
   top-right island. Not called paper: in this tool that word is the
   sheet in the printer. See the notes of the same day.

Nothing on this list is open. What is left is whatever the next round
of use turns up.

A first because everything after it needs somewhere to live, C before D
because the colors have to be designed against the paper they sit on,
and G last because it is the only one that removes a tab.

Written as a self-contained `seating/` module with its own stylesheet
from the start. That is the difference between the spin-off being a
move and being a rewrite.

### 12.13 One disclosure, one behaviour

Written down because the inconsistency keeps coming back. By the time
anybody counted, this window had **four** ways of opening a thing that
holds other things, and no two of them agreed:

| | opened by | closed by | motion |
|---|---|---|---|
| mode rail | hover | leaving | 0.28s in, 0.2s out |
| furniture drawer | click | click, or outside | 0.28s / 0.2s |
| save menu | click | outside **only** | none |
| color swatches | click | outside | none |

Three of those are defensible on their own. Together they are a window
that has to be learned four times, and the save menu's missing
press-again-to-close was a bug nobody would have written if it had
been the same code as the drawer.

**The rule.** Anything that opens to reveal more:

* **opens on a press, never on hover.** There is no hover on a touch
  screen, which is the same argument that ruled out a right-click
  menu for the Printing commands. Hover-open also fires when somebody
  is on their way somewhere else, and the usual patch for that -- an
  intent delay -- is a timer that makes the interface feel slow in
  exactly the case it was added for.
* **closes on a second press of the same control**, on a press
  outside it, and on Escape. All three, always.
* **uses `--in-time` / `--in-curve` arriving and `--out-time` /
  `--out-curve` leaving.** Those exist so that nothing has to choose
  a duration, and anything that chooses its own is wrong twice: once
  for being different, and again the next time the pair is tuned.
* **is built once and shown by a class**, not created on demand. A
  popup made at the moment it is needed has nothing to animate from,
  and -- the save menu's actual bug -- a second press builds a second
  one on top of the first instead of closing it.
* **is one at a time.** Opening any of them shuts the others.

**And the enforcement, which matters more than the rule:** these
should share an implementation, not a convention. Four places
independently deciding to behave the same way is four places that can
independently stop. The CSS is now one `.drop` / `.palette` pair of
rules over shared tokens; the open state is a boolean per surface
cleared in one place.

Where this bites next: the color swatches (`openHues`) are still the
fourth way -- created on demand, no motion, outside-press only. They
should become a `.drop` like the rest.

**A second rule, learned the hard way on 2026-10-10.** Sharing the CSS
was not enough: the rail still snapped open where the others eased,
because pressing it called `renderSeating`, which *rebuilds the rows* --
and a brand new element has no previous value to transition from.
Opening something is not a change to the document. `showOpen` sets the
three open-states on the live elements and redraws nothing. Anything
that animates must be told, not rebuilt.

### 12.8 Decisions taken

| | |
|---|---|
| Persistent state lives in a course folder outside every repo | student data must never enter a repository, and copies drift |
| A course folder is named by the instructor, not derived from the course code | one instructor wants both sections together, another wants them apart, and `course init` will make as many as they like |
| A job names a course; an explicit path still wins | one place to fix a name, and no existing job folder breaks |
| The job's pointer is `[course] folder`, a key, not a `[course]` table | a publication file already has a `[course]` table for the printed header, and TOML refuses a duplicate. `name` prints, `folder` resolves |
| TOML for human-authored state, SQLite for the print record | unbounded, machine-written, queried, and written by two processes |
| Legal name and preferred name are separate fields | the seating chart uses preferred names; Banner will not |
| SID joins, email is the fallback, name is never a key | SIDs do not change |
| `dropped` is a flag; a missing row in an import sets it | the print record has to survive |
| Availability is global, not per student | one form for everyone; per-student would mean per-student forms |
| printit owns only the form slots it can derive | the rest is pedagogy the tool cannot regenerate |
| Patch recorded item ids; never recreate form or question | responses are keyed to `questionId` |
| Printed and attempted are different facts | the build cannot know who was in the room |
| No retake cap | none exists in the course |
| Courses live in `~/CheckItPrintIt/courses/<name>/` | beside the job folders and the output, all outside every repo; configurable later if anyone needs it |
| `course init` offers to adopt the newest job's roster and seating | there are already three copies on disk and none of them should be retyped; it prints which files it read |
| `openpyxl` is added as a dependency | Banner and the seating charts both arrive as `.xlsx`, and requiring a save-as-CSV first defeats an importer whose purpose is removing manual steps |
| Responses stay scoped by the confirmed date | it is what the current system does, it survives a late submission that a timestamp window would miss, and the confirmation question already exists |
| The cold-call system waits for the seating GUI | it belongs at the top of that window, and it is far down the road |

### 12.9 Still open

0. ~~Nothing in stage 7 has run against a real Google account.~~
   **Settled 2026-09-21: 7a works.** One thing remains open --
   `form create` needs to prompt for the one-time browser authorization that
   the editor's deploy flow does automatically. See the staging table.

1. ~~Whether the Google Cloud path is open on the institutional account.~~
   **Settled 2026-09-20: it is not.** No Cloud projects on that account, so
   Apps Script is the path. See 12.5.
2. ~~The exact Banner export shape.~~ **Settled 2026-09-20 against three real
   exports**, and it changed the model. There are *two* id systems -- a Banner
   student id (`806...`) and a Global id the LMS calls OrgDefinedId (`20...`)
   -- and an export carries one, the other, or both, so a student record keeps
   both and a merge matches on whichever it has. An LMS export also contains
   an instructor and a mentor row, so role filtering is not optional. A Banner
   summary workbook puts its header on row fifteen under a course-information
   block. And **email is only a weak key**: one student appears under two
   different addresses in two exports downloaded the same day, and the Google
   Form only ever saw the first -- so addresses accumulate rather than
   replace. Implemented in `classlist.py`.
3. ~~Whether `.xlsx` support is worth a dependency.~~ **Settled 2026-09-20:
   yes, `openpyxl`.** Banner and the seating charts both arrive as `.xlsx`.
4. ~~Whether `availability.toml` should carry the "how many skills" wording, or
   derive it.~~ **Settled 2026-09-20: derive it**, reusing the Control Center's
   own number-word table (0-40, where 0 means "any"). See 12.10.
5. ~~Whether the Apps Script API toggle is available on the institutional
   account.~~ **Settled 2026-09-20: it is, and it is now on.** `clasp` is the
   deployment path; the script lives in this repo and pushes from the command
   line.

### 12.10 The Control Center, and what replaces it

The existing system is a Google Sheet with a bound Apps Script. **It is being
retired.** Going forward there is a Google Form with a script attached to it,
and printit does everything else the Sheet was doing.

The script is the specification for the half that stays with Google, and a
useful record of behaviour that exists nowhere else.

| Apps Script function | what it does | where it goes |
|---|---|---|
| `coreCallSystem`, `refreshCallList` | rotating cold-call list with a per-student skip flag, re-inserting unchecked students at random positions | **GUI** -- a feature not previously on any list here |
| `randomizeSeating` | shuffle the roster into seats, filtered by section and by dropped | GUI, writing `seating.toml` |
| `shuffleSelectedStudents` | swap two selected seats, or shuffle more than two | GUI |
| `importStudentChoices` | join seating + roster + responses + the three selection modes + extras | printit, built -- minus the response join |
| `generateTexFile` | build `main.tex` | printit, built |
| `printAndReset` | append the run to a Printed sheet, then clear the settings | printit: the manifest and `record.db`; "reset" becomes "a job is one-shot" |
| `updateSelectionsForm` | push the week's slots into the form | the form-bound script, driven by printit |
| `emailMissingStudents` | templated mail to non-responders, substituting `$FIRSTNAME`, `$ASSESSMENT`, `$DUEDATE` and friends | later; the variable set is the spec |

**What `updateSelectionsForm` establishes:**

1. **It locates items by type and index** -- `getItems(CHECKBOX)[0]` and `[1]`,
   `getItems(SECTION_HEADER)[0]` and `[1]`. Inserting one section header above
   them silently retargets every write. This is the concrete argument for
   recording ids in `form.toml`; `FormApp` items expose `getId()`.

2. **Number words 0-40, where 0 means "any"**, in both lower case (body text)
   and upper case (the question title).

3. **Three limiter modes, not one** -- "At Most", "At Least", and exactly --
   each with a matching `requireSelectAtMost` / `AtLeast` / `Exactly`
   validation and its own help text. So `availability.toml` carries a `limit`
   alongside `choose`:

   ```toml
   [assessment]
   choose = 3
   limit  = "at most"     # at most | at least | exactly
   ```

4. **The no-skills-available state is deliberate.** One option reading "(No
   skills are available yet. Check back later!)" plus
   `requireSelectAtLeast(100)`, which makes the form unsubmittable. Preserve
   it rather than rediscovering it.

5. **The auto-attached explanation suffix is dead.** The script appends
   "(X will be included on the back side automatically.)" to a skill with an
   associated explanation. Section 10 deprecated that -- explanations are
   standalone outcomes now -- so it is not carried forward.

**What `importStudentChoices` establishes:**

6. **Responses are scoped to an assessment by date, not by a time window.**
   `filterArrayBySingleDateCriterion(responses, 0, 2, GetDate)` matches the
   month and day of the response's date column against the assessment date.
   That is what the "Confirm Skill Checkpoint Date" checkbox is *for*: it is
   the scoping key, not merely a nudge. A form accumulates responses all term,
   so `form pull` has to scope the same way.

7. **Latest response wins** -- sorted by timestamp descending, first match per
   student. This is what the 2026-09-18 run did by hand, so the tool inherits
   existing semantics rather than inventing them.

8. **Extras cycle through the version letters** (`allVariants[i % length]`).
   printit shuffles instead, which is what section 10 chose. Noted so the
   difference reads as intentional.

**Two more things the script settles, which were open questions here:**

9. **Response validation is already on.** `updateSelectionsForm` builds a
   `requireSelectAtMost(n)` validation and attaches it, so students cannot
   over-select today. The push must keep setting it, since the limit and the
   skill list change together.

10. **Nothing caps a response on the way back in.** `importStudentChoices`
    takes every choice in the response, appends the "append for everyone"
    skills, de-duplicates, and prints the lot. If a response somehow carries
    more than the limit -- a stale submission from a week when the limit was
    higher, say -- the existing behaviour is to print all of it. Keep that,
    and let the preview show the count rather than silently truncating.

**The script is kept verbatim** at `reference/control_center.gs` in the
`checkit-printit` repository, with a README saying what it is. It carries no
student data; that was checked rather than assumed.

**The Sheet also held state that now belongs to the course**: the roster
with dropped flags, the seating charts, the available-skills list with its
tick boxes, the Printed log, the email templates, and the run settings
(title, date, key count, extras count, the three selection modes). Those map
onto `roster.toml`, `seating.toml`, `availability.toml`, `record.db` and the
job's `publication.toml` respectively -- which is what 12.1 through 12.4
describe.

### 12.14 What the chart says about order (2026-10-10)

`seating.toml` is a flat sequence of `[[group]]` tables, each holding a
list of seats, and that list was being asked to mean three things at
once: the order the papers print, who is sitting next to whom, and
which chair at the table a seat is. One list can only do one of those
honestly.

It did not matter until the print order could differ from the seating
order. Then it contradicted itself in both directions at once: a table
seated A B A B round its four sides is fine, but printed 1 3 2 4 the
file reads A A B B, so the check reported two clashes nobody in that
room can see -- and the real pairs, the ones along the sides, were no
longer written down anywhere to check.

**The decision.** A `[[group]]` is the *table*. Its seats are listed in
the order they sit, which is the clockwise sweep from the top left, and
that order is never touched for printing. The stack is a separate thing
each seat carries:

```toml
[[group]]
seats = [{name = "Ada Lovelace", version = "A", at = 1},
         {name = "Alan Turing", version = "B", at = 3}]

[[group]]
seats = [{name = "Grace Hopper", version = "A", at = 2},
         {name = "Katherine Johnson", version = "B", at = 4}]
```

Ada still sits with Alan; the stack still alternates tables.

Three properties were wanted and all three hold:

* **An untouched room writes the file it always did.** `at` appears only
  where the stack is not the order the file already reads in. Handing
  out table by table with nothing reordered, those are the same list.
* **Every hand-written chart still loads unchanged.** The sort is
  skipped entirely when no seat claims a place, so the key is not merely
  handled but absent from the code path.
* **`print_by = "seat"` reaches the paper.** It means one walk round the
  room, which crosses tables, and no ordering of `[[group]]` blocks can
  express that.

Rejected: flattening every seat into one `[[group]]`. It would encode
the order and destroy the meaning, since `group` is what `collisions`
reads, and one group of twenty-five would call every neighbour a clash.

Two rules fall out of it. **The numbering is one sequence for the whole
file**, because a chart has no sections in it, only a comment saying
where one begins -- and all-or-nothing, because a seat with no number
prints last and a bare section ahead of a numbered one would be dragged
behind it. And **a seat with no `at` among seats that have one prints
last**, which is the rule an unplaced group and an unspotted seat
already follow.

### 12.15 The pin, and the shuffle (2026-10-10)

Two halves of one thing. A shuffle is only usable if some people can
be exempt from it: students with accommodations sit where they sit,
and a button that threw them across the room would be a button nobody
dared press.

**The pin is on the seat, not the student.** `seat.pinned`, optional
and boolean. What it means is "whoever is in this chair stays in it",
which is the thing an accommodation is actually about -- a place, not
a person. It is not the same word as `seating.Seat.pinned` in the
chart, which says a version letter was written down rather than
worked out.

**Where it lives on screen.** The bottom-right corner of the name
card, opposite the version letter and in the same `--solid` color:
both corners are the room having decided something about that card.
Only People mode draws one, because no other mode moves people. It
shows when set, on hover, and on the card currently in hand -- the
last of those being the one a finger can reach, since a touch screen
has no hover. Twenty-five permanently visible grey pins would be
noise nobody is looking for.

**One refusal, not four.** A person can be moved by dragging a card,
dropping onto a card, clicking a name, or clicking a chair. All four
reach `movePerson`, so that is where a pinned seat is refused; the
affordances are also turned off at each gesture, so the move never
looks available in the first place. A pinned card simply does not
drag, rather than springing back -- springing back looks like a
missed drop, and the point is that the drop was never on.

**What a shuffle touches.** The people already sitting down, into the
chairs nobody has pinned. Not the unseated rail, which is somewhere a
person was put on purpose. Empty chairs shuffle like anybody, or
every gap collects at one table. The version letters stay on the
chairs, because the coloring is of the room -- so the arrangement is
still legal afterwards and nothing needs re-coloring.

It runs on the server for the same reason the coloring does: a button
calls the function a command would, and these rules are worth a test.
Nothing is written -- the room comes back changed and unsaved, so an
instructor who dislikes the result presses Discard.

**Randomising only a selection was considered and is not needed.** It
is pinning everybody else, which already exists, inverted. Swap-two
was dropped for the same kind of reason: People mode already swaps two
people by clicking one and then the other.

**Where they live.** Both are rows in the corner button's drawer,
which People mode now has like Groups and Printing -- the same
contextual surface with different contents, which is what 12.13
asked for. The wand rather than a plus, because the rule is that a
wand means "asking the room to work something out", and that is what
a shuffle is.

**That last sentence is wrong as of 2026-10-11, and the wand is
gone.** See 12.17: the corner button is a `+` where the mode has one
primary action and a `⋯` where it has a list, and People has a
list. The wand was a symbol for a category -- "the room works
something out" -- which is a thing a reader has to be taught, and the
two apps anybody compares this to teach the opposite.

### 12.16 Say it in two words (2026-10-11)

**A control is labelled with a verb and its object, and nothing
else.** "Seat all". "Unseat all". "Shuffle room". "Unpin all". Not
"Seat all 6 standing", not "Clear every chair", and never a sentence.

Written down because it has now been asked for three times, each time
after a round of new controls arrived carrying explanations in their
labels. The pull is understandable -- a label is the only place the
writer is sure the reader will look -- and it is wrong, because a
menu of five rows is read as a shape before it is read as words, and
five sentences have no shape.

The rules that follow from it:

* **No counts in a label.** "Seat all", not "Seat all 6 standing".
  The count belongs in the tooltip, where it answers "all of how
  many?" for somebody who wondered.
* **No grammatical variation on a count.** A label that is "Unpin the
  one pinned seat" at one and "Unpin all 3 seats" at three is two
  labels, and the row appears to change identity as the room does.
* **A tooltip is a fragment, not a sentence.** "3 pinned stay put".
  It is a footnote to the label, so it says the thing the label left
  out and stops.
* **The house word wins over the plain one, once there is a house
  word.** The rail "unseats"; so does the menu, and so does the drop
  target. "Clear every chair" was a third way of saying it.
* **A caption on a drop target is one word** -- "Unseat" -- because it
  is read in the half second while something is held over it.

The test: read the menu as a column with the icons covered. If any
row takes longer than a glance, it is too long.

### 12.17 The canvas obeys canvas conventions (2026-10-11)

A fortnight of use found one kind of complaint over and over: the
canvas was *nearly* like every other canvas, and the gap was where
the friction lived. These are the decisions that closed it. The
common thread is that a design canvas is a genre with conventions
already, and inventing inside it is a cost paid by the reader.

#### The canvas has no edges

It used to be fenced to a box a little larger than the content, which
could not be dragged out of. The reason was good and the effect was
not: a room could not be laid out across the width of a screen,
because the fence arrived first.

**So: coordinates may be negative, and nothing clamps.** The model
never minded. Fitting and centring measure the content's own box, so
they work the same at any offset, and `section.canvas` is a record of
how far the room reaches rather than a limit on it.

What makes that safe is that **fit is the recovery, not a wall.** A
drag that throws a table somewhere surprising is undone by the thing
the user already knows -- press fit, see everything, drag it back.
A fence prevents the surprise at the cost of making the surface feel
small all of the time, which is the worse trade, and "I can't even
place things fully from one side of the screen to the other" is what
it sounds like from the outside.

#### The wheel zooms, about the pointer

Scroll up is in, scroll down is out, and the point under the cursor
stays under the cursor. Ctrl-click (cmd on a Mac) adds to a selection.
Neither of these is a feature so much as **the absence of a defect**:
a canvas without them reads as a prototype, because every tool the
user has ever zoomed in does it this way.

Holding the point under the cursor is worth one note, because the
obvious implementation is wrong in a way that only shows up after ten
clicks. Solving for the new pan in closed form requires being right
about every rectangle in the chain, and being an eighth of a pixel
wrong each time walks the subject visibly off the cursor. **Measuring
where the point actually landed and correcting by the gap is a fixed
point**, converges in one or two passes, and does not care which of
the measurements was the inaccurate one. See the notes of 2026-10-11.

#### One grey for everything the canvas marks

`--mark`. The accent color belongs to the chrome, where it means "the
state you are in"; on the paper it is just another color, landing
beside whatever the groups happen to be. Five things were wearing it
there -- a band, the desk a dragged seat would move to, the two hover
marks in the click-in-order quasimode, the badge a version would
trade with -- and each had invented its own inset, radius and dash
along the way, so there were four selection rectangles that looked
like four different ideas.

**One geometry as well as one color**, `--pick-out` and `--pick-line`
on `.deskwrap`. A reparent target is now visibly the same gesture as
a selection, asking a question.

#### Selection color answers "which one", and only when there is one

* **A single selected group wears its own color.** That is the
  question a selection answers -- which of these have I got hold of --
  and the group's color is the only thing on screen that already
  means that group.
* **A multiselection is grey**, and the members lose their handles and
  their own selection styling entirely. With more than one there is no
  "which one", so the question changes to "what is in the set", and a
  set is one shape with one ring. `isSelected` returns false while
  more than one thing is banded, which is what makes the handles
  disappear in one place rather than eight.
* **The ring is feathered**, tapering out the same distance a seat's
  selection does, because the two now had to look like one idea.

#### Glue and unglue

A group is **a set of seats**, not a shape. That was already true and
merging is the first feature that makes it obvious: `merge_groups`
folds two seat lists together, `split_group` regroups by desk, and
**nothing moves either way**. Two tables merged while apart stay
apart; they are one group that happens to span two desks.

What follows without any new code:

* one label, one color, one strip, one set of grips
* a drag moves the whole thing; a rotation turns it about the common
  middle
* **the seat letters need no special case.** A letter is swept
  clockwise from its *group*, so a merged group sweeps its whole
  arrangement as one ring and the lettering is already right

The strip carries the merge icon when more than one group is selected
and the split icon when the selection is a merged group. Drawn as the
two inner edges of adjacent tables with a filled arrow pushing in or
pulling out, after `]  [` and `}  {` -- because the first drawing was
legible at full zoom and a smudge at arm's length, and a strip is
read at arm's length.

#### A control exists only where the thing it edits exists

The by-seat print plan made this concrete. Ordering by seat, **a group
has no place in the stack** -- the stack crosses tables, and a
group's position in it is not a number that exists -- so that control
is simply absent from the group strip in that mode. A seat gains one
instead, because by seat a single seat is exactly the thing that has
a place.

The general rule, which is cheaper than it sounds: a control that
would edit something nothing reads should not be drawn. Greying it out
says "not now"; absence says "not a thing", which is the truth.

#### A strip field is editable exactly when it is stored

* `seat.version` is stored, so it is typable, and validated against
  the room's own version list -- a letter nothing prints would put a
  version in the chart that the build has never heard of.
* The **seat letter is derived** and is therefore not editable, and
  should not become so. It is swept from where the seat sits, which is
  the whole reason "re-letter when a seat moves" needs no bookkeeping.
  Making it typable would mean storing an override, and the room would
  have two answers to the same question.

Both are regular weight now rather than bold. Two bold characters
side by side shout at each other and say nothing about which is
which; the chair and the printer icons beside them already say that.

#### The corner button is two controls in one place

A `+`, accent filled, where the mode has one primary action, which is
always adding a thing. A quiet `⋯` where it has a short list
instead. This is Material's own rule -- a floating button carries one
action, and overflow belongs in a menu -- and it resolves the thing
that looked like a conflict: People wants an "add person" *and* a
menu, so add person is the first row of the menu. In this app it
redirects to the Roster tab, because adding a person is roster work.

#### What is actually left, 2026-10-11

The four items on the 2026-10-10 list are all struck through above;
this replaces it.

1. ~~Pinch zoom does not anchor the way the wheel now does.~~
   **Done 2026-10-11**, and it was three faults rather than one. The
   guess that it needed real hardware to confirm was wrong: synthetic
   touch pointers drive the handler, and measuring first found that
   neither `panPaper` nor `bandPaper` filtered `pointermove` by
   `pointerId`, and that nothing called off the one-finger gesture
   when a second finger landed. The anchoring is now one named
   function, `holdPoint`, which both the wheel and the pinch call.
   117 pixels of drift before, 0.03 after. See the notes of the same
   day.
2. **Nothing in Seating has been used on a phone.** Two-finger pan and
   pinch are written and have never been under a thumb. The layout was
   checked at 530px in a desktop browser, which is not the same test.
3. **Record** was the one view still entirely unstarted. It is now
   three -- Runs, Progress and Scans -- and is specified in section
   14. **Setup**
   still wants its boilerplate editor.
4. **The TOMLs want a pass.** They were designed before the GUI, in
   preparation for it; now that the GUI has settled there is almost
   certainly shape in them that no longer earns its place. The
   instructor's own words: more there needs reconsidering than the one
   `at` key that 12.14 added.
5. ~~One unexplained measurement.~~ **Explained 2026-10-11, and
   there was nothing wrong with the room.** `MouseEvent.clientX` is a
   `long`, so the browser truncates wheel coordinates to whole pixels;
   the harness was measuring a point up to a pixel away from the one
   the zoom anchored on, and such a point is *supposed* to move when
   the picture scales. Rounding the measuring point gives 0.03 pixels
   over fifteen clicks. The clue was the thing recorded as the puzzle:
   **a number that does not change when you change what it measures is
   measuring something else.**

## 13. The look of the app (2026-10-13)

**Status: in force.** Stages 1 to 3 are built and every tab now shares
one structure; stage 4 is the remainder. What is marked *settled* has
been decided by the instructor and should not be relitigated. What is
marked *open* is still a judgement call and belongs to him, not to
whoever is editing this file.

Section 14 is written against these rules and assumes them.

### 13.1 The problem this exists to fix

The GUI was designed end to end by Claude, and it reads that way. The
diagnosis is not that it breaks rules -- it mostly does not. It is that
**uniform treatment was applied where a designer would have made
judgements.**

Every section is a card. Every card is the same weight. Every
explanation is the same size as every other piece of text. Nothing is
emphasised, because nothing was *chosen* to be emphasised. The giveaway
on the old Overview tab was eight identical boxes in which the largest
word on screen was "yes".

Three secondary tells, all of the same kind: native OS form controls
left unstyled in a custom dark theme; explanatory prose everywhere a
human would have trusted the reader and cut; a three-column grid
holding eight items.

**The through-line of the instructor's own reactions to a dozen
reference applications**: everything he liked was row-based with
comfortable spacing (Linear, Things 3, TrueNAS). Everything he disliked
was either boxes-with-gaps (Sonarr, Sublime Merge, Home Assistant, our
Overview) or crushed rows (TablePlus). The target is **rows with air.**

### 13.2 What we take from Material and Fluent, and what we refuse

Both frameworks were consulted. They converge on five structural
points, and those are worth having:

1. Navigation placement follows destination count and window width.
2. Layout should change *shape* at breakpoints, not merely reflow.
3. Elevation is a ladder of surfaces, not a binary.
4. One accent-filled action per view.
5. Density is a named global setting, not improvised per screen.

**We take their structure and refuse their surfaces.** Their visual
defaults are precisely what makes software look like everyone else's --
boxy and dated in Fluent's case, spartan in stock Material's. Adopting
the reasoning without the skin is the whole point.

### 13.3 Settled

**The rail.** Navigation moves from a centred top bar to a left
navigation rail, with icons, collapsible to icons only. This is not a
preference: with seven destinations at desktop width it is what both
frameworks specify, and Material 3 Expressive has since dropped the
navigation drawer in favour of exactly this collapsible rail.

**No top navigation at all.** What survives at the top of a page is the
page's own title.

**No dashboard.** The Overview tab is removed. Its contents are
redistributed by *where you would act on them*: counts go in the
relevant page's header, configuration facts go to Setup, and anything
wrong becomes a warning -- a dot on the rail, and a strip at the top of
the page that owns the problem.

**Rows, not cards.** Cards are for a group that genuinely needs a
boundary. Lists are bordered rows. Nothing gets a card merely for being
a section.

**Filled checkboxes**, not outlines. Outline checkboxes read as too
much negative space at this density.

**Save state is a bar that appears only when dirty** (option c of three
tried). Absent when there is nothing to save.

**The page title is the editable field.** The Print tab had the job's
name and date rendered twice -- once as uneditable page furniture, once
as form fields further down, with a button between them that depends on
the date. One editable title carrying name and date removes the
duplication and puts the date above the control that needs it. The
section heading "This run" dies with it: every setting on that tab is
about this run.

**A second hue, with one meaning.** Amber means *something needs your
attention* -- the rail dot, the page-top strip, the unsaved badge. It
is not used decoratively. Green stays the accent.

**No jet black in dark mode**, and more grey steps than the two the app
has now.

**The greys are warm.** Measurably: the first drafts came out violet --
`#a6a2ac` is R166 G162 B172, blue highest and green lowest, and the
whole ladder carried that cast. The light theme has always been warm
(`#fbfaf8`), so a warm dark ladder makes the two modes siblings rather
than strangers. Neutral was the alternative and is still defensible;
violet was nobody's choice, it was an accident.

**Figtree**, over Inter, Source Sans 3, Atkinson Hyperlegible and IBM
Plex Sans. It is the roundest of the candidates without being a
consumer-app face, and it is the one that answers "inviting" -- the
numerals in particular soften a dense grid at no cost to legibility.

**The gutter is for settings-shaped sections only.** Not a layout for
the whole app. See 13.5.

### 13.4 Writing, which is where the character is

§12.16 already governs control labels: a verb and its object, nothing
else. It extends to the whole GUI.

**Never run facts together with separators.** `45 students · 22 in 820
· 23 in 830` is the single most recognisable tic in this codebase, and
it is the writer reaching for a separator because no layout was
designed. Three facts in a row with dots between them is a sentence
pretending to be an interface.

What to reach for instead, roughly in order: **an icon with a number**,
which costs no words at all; **small grouped pills** where the facts
are peers; **colour or weight** where one of them is the one that
matters and the others are context; and **putting the fact next to the
thing it describes** rather than collecting facts into a strip at the
top. A count that belongs to a section belongs in that section's
header row, not in a run-on with two other counts.

The run-on is occasionally right -- for genuinely equal, genuinely
minor metadata, three items at most. It is not the default, and it
must never be the first thing reached for.

**Plain underlined text is not how a function looks.** The
instructor's rule, and a standing one: an underline says *this
navigates*, and every control in this app does something instead. A
column of underlined words reads as a paragraph that has been marked
up rather than as a set of controls. Quiet buttons -- no border at
rest, a surface on hover -- and for an action that repeats down every
row, an icon: grey at rest so the column stays quiet, the accent only
on the row under the pointer. `tests/test_gui_markup.py` enforces it.

**An action outranks reference data.** When a table runs out of width
the instinct is to protect the data, because data is what a table
looks like it is for. It is not: Email and SID are reference, and
dropping a student is the one thing the Roster *does*. Columns carry a
`rank` that says what survives a squeeze, and the actions sit second,
below only the name.

**Skill names come from the bank.** Each outcome in `bank.xml` carries
*two* strings: a short `<title>` ("Divisibility Statements") and a long
`<description>`, the "I can..." statement. **Titles belong in tables
and headers; descriptions belong in tooltips.** Nothing in the GUI
should invent, abbreviate or paraphrase either. `bank.description()` is
currently the only accessor printit has, which is why the long form
leaks into places that wanted the short one -- that is a gap to close,
not a style to follow.

**Explanations do not sit in the open.** The long paragraphs on the
Print tab were an AI's instinct to over-explain. An explanation belongs
behind a `?`. A short subtitle is permitted where the section genuinely
needs one; a paragraph is not.

**Say the consequence, not the event.** "17 will take the default" is
worth more than "17 did not answer", because what the reader needs is
what will print. Where two numbers are a pair, make the grammar
parallel: *28 answered / 17 didn't*.

**Empty states are the one place a utility may have a voice**, and the
cheapest source of the warmth this app lacks. "Inviting" here means
microcopy, empty states and the typeface -- not colour, not rounder
corners, not illustration scattered about. Those read as decoration,
which is the opposite of charm.

### 13.5 Structure

**Settings-shaped sections are annotated**: the section's name and its
`?` sit in a left gutter, the controls to the right. This is Polaris's
settings layout, and it works because the header is distinguished by
*position* rather than by shouting. **At narrow widths the gutter
collapses and the header moves above its controls.**

**Table-shaped tabs get no gutter.** Roster, Runs, Progress and Scans
are not settings
and must not pretend to be. The gutter costs about 120px of width
permanently, which a form does not miss and a table does: drawn both
ways, the same Roster column went from carrying a real skill name to
carrying a bare digit.

So the consistency this app keeps is **consistency of rule, not of
appearance**: a section whose content does not want horizontal space
gets a gutter; a section whose content does, does not. Two structures,
one reason, stated here so neither looks like an oversight later.

**Counters never live inside a heading.** "Open for retake — 0 to 29"
jammed three ideas into one line. The name goes in the heading, the
count sits right-aligned on the same row, the range belongs to the
control it governs.

**A long table scrolls inside the window, not the page.** With 45
rows the Roster's scroller was 2158px tall, which put its horizontal
scrollbar 1362px below the fold: sideways movement was shift-and-wheel
only, and the rightmost column -- the drop button -- could not be
reached at all. The table gets the window and scrolls within it, so
both bars are on screen and the headings stay put.

**Name and the actions are pinned**, left and right. Those are the two
a row cannot do without: which student this is, and the thing you came
to press. Everything between them scrolls.

**Spare width goes into the table.** A 1100px header above an 867px
table looked like the table had failed to load. Columns marked `grow`
take the slack up to their own maximum; Section does not, because a
300px Section is a worse table and not a bigger one.

**An empty column is sized for its heading.** `min` is what a column
wants when it holds something; `floor` is what it may be squeezed to,
and a column with no values anywhere starts there. `Prints as` is
empty on every roster here and was reserving 200px -- a fifth of the
table -- while Email was clipped.

**Slow work starts at boot, not at the click.** Measured on the real
course: `/api/skills` is ~700ms warm and 1.2s cold, `/api/google` is
**six seconds** the first time because it shells out to clasp. Both
now start when the app opens, behind the Roster, so the tab that needs
them usually finds the answer already there -- a warm switch to Update
form went from about a second to **3ms**. A request is kept as a
promise, not as data, so a second caller joins the first one instead
of making its own.

**Where a wait is unavoidable, show the shape of what is coming.**
Placeholder rows the height of real ones and as many as the list will
have, so the page has its layout before it has its content and nothing
jumps when the answer lands. Never a spinner, which says only that
something is happening somewhere.

**And they move.** 13.4's line about decoration names colour, rounder
corners and scattered illustration; a loading shimmer is none of
those, and it is not decoration, because it is carrying the one
distinction that matters here. A still grey bar is indistinguishable
from a real empty row -- "nothing is open for retake" reads exactly
like "this has not arrived yet", and on this tab the first is a
plausible state. The movement is what says which. Slow, low-contrast,
and off under `prefers-reduced-motion`.

Recorded because the opposite was briefly written here, as though the
instructor had ruled against animation. He had not: he had ruled
against underlined text for functions, and against decoration meaning
colour and corners and illustration. **Do not generalise one of his
rules into a neighbouring one he did not make.**

**A table's header row has its own surface**, so it reads as a header
without extra spacing.

**Columns collapse rather than disappear.** The variant column shows a
real editable control at full width and folds to a single icon when the
table is narrow.

**Numerals are tabular** everywhere a number sits in a column.

### 13.6 What Seats gives us, and what it does not

Seats is a canvas sandbox. The rest of the app is text and tables.
Importing its look wholesale would be a category error -- and the
instructor's own reaction proves it: Seats's floating islands are cards
with space around them, which is exactly what he disliked in Home
Assistant. They work over a canvas because the room must stay visible
underneath. In a text view there is nothing underneath.

| from Seats | verdict |
|---|---|
| two-word labels; tooltip carries the rest | **take** |
| a control exists only where the thing it edits exists | **take** |
| editable exactly when stored; derived things are not | **take** |
| an empty state is a door, not a sign | **take** |
| one neutral for what the system marks; accent reserved | **take, translated** -- accent marks the primary action and current location, never decoration |
| a ladder of surfaces | **take, translated** -- no canvas to float over, but one `--panel` is not enough |
| floating islands | **refuse** -- nothing to see through to |
| modes | **refuse** -- tabs are different data, not different verbs on one object |
| the corner plus | **refuse** -- a form has a natural home for its primary action |
| the geometric icon set | **refuse** -- those glyphs depict spatial operations; "Pull responses" has no picture |

### 13.7 The stages, and where they stopped

The work is staged so that payoff comes early and risk late. Direct
on `main`: the instructor is the only user, and asks for the usual
branch-and-merge procedure to be skipped.

| stage | what | state |
|---|---|---|
| 1 | token layer: surfaces, spacing, radius, type, font, native controls | **done** |
| 2 | the shell: left rail, no top nav, no Overview | **done** |
| 3a | a skill shows its `<title>`, not its description | **done** |
| 3b | Print tab: editable page title, `This run` dies, annotated sections, prose behind `?` | **done** |
| 3c | Roster: the counts question, and the `colgroup` arithmetic | **done**, with comments outstanding |
| 3d | Form, Setup | **done** |
| 3e | Record | **superseded by section 14** -- it became three tabs |
| 4 | save bar, warning strips, empty states, a microcopy pass | next |

**Settled in 3b:** an annotated section is a `.annot` grid -- a 200px
gutter holding the name and its `?`, the controls to the right, a
hairline between sections and no card. `annot-full` drops the gutter
for content that wants the width, which on this tab is the table and
nothing else; it buys the table 220px. The `?` toggles a `.hint-text`
and is wired by one delegated listener, so a section added later gets
the behaviour without being remembered. Below 860px the gutter
collapses and the header goes back above its controls.

**Settled in 3c:** the page header carries only the whole-table
total (`Roster` left, `45 students` right); the per-section counts
ride **section bands** inside the table, a thin full-width row
reading `820` with `22` right-aligned above that section's rows.
Bands are drawn only while the rows are actually grouped by section,
tested on the sorted rows rather than on `sorts[0].key`, so they
survive a descending sort and vanish when a sort interleaves the
sections. The table scrolls inside the window rather than making the
page tall, with the heading row, the Name column and the actions
column all pinned; columns carry a `rank` that decides what survives
a squeeze, and **an action outranks reference data**.

**Settled in 3d:** Setup's "needs your attention" panel stays a card
while everything around it became an annotated section -- a boundary
is what says something is blocking you. The rule between sections is
visibility-aware, because Setup and Print both hide sections
depending on state.

**Settled during the build, beyond 13.3:** Figtree is vendored, not
linked. The greys are OKLCH 260, Seating's own hue, several steps
lifted unchanged. The rail is `.navrail` and carries the course name
at body size, matched to Seating's section toggle; its labels are
body size and its glyphs 21px. The count has left the rail.

### 13.8 Still open

* **The Roster's remaining comments.** The counts question is
  answered -- see "Settled in 3c" above -- and the instructor has
  further notes on that tab which he has parked in order to get all
  the tabs looking alike first. They are not written down here
  because they have not been given yet.
* **Section header treatment.** Six have now been tried across two
  rounds and all six were rejected. Parked deliberately: the
  instructor wants to judge it with a whole tab on screen, not in
  isolation, and it may turn out to need nothing at all.
* **Exact density**: row height and padding. `--t-base` is still 15px
  because turning it reflows every view; the midground target is
  roughly 36-40px rows, untested against 45 students.
* **The rail's collapse threshold.** It folds to icons below 900px,
  which on a narrow window means the labels are never seen. Right
  number unknown until it is used at a real window size.
* **A top strip, or none.** The top bar is gone and nothing replaced
  it. Whether the app wants a thin one for global state is open;
  three save-state placements were shown and (c), a bar that appears
  only when dirty, was chosen, which may be all that is needed.

---

## 14. Runs, Progress and Scans (2026-10-22)

Three new tabs, agreed with the instructor in a design round on
2026-10-21/22. His answers are recorded as decisions; what he did not
decide is in 14.8 and should not be guessed at.

This is the realisation of **6c**, which anticipated "a table-style
editor in the eventual GUI" and is otherwise unchanged -- including its
rule that the record **does not feed back into printing**. Progress
tells the instructor what has happened. It does not skip a skill
somebody has passed, and it does not prioritise one they keep failing.

### 14.1 Why three, and the order they depend on

They are three questions with three shapes, which is why the single
"Record" tab never got drawn:

* **Runs** -- what was printed, when, with which seeds.
* **Progress** -- where each student stands against each skill.
* **Scans** -- read the marked papers back in.

The dependency runs one way. Scans needs Runs, to know what a paper
should be. Progress needs Scans, because of the decision below.

**An attempt is logged when a paper is graded, never when it is
printed.** A printed paper for an absent student is not an attempt.
*Taken* means *present in the scan*, and it is the instructor's job to
pull absentees' and empty papers out of the stack before scanning.
That is a deliberate division: the app does not guess at attendance,
and the person holding the stack already knows.

So Progress shows nothing real until Scans works. The instructor has
his own system for this semester and is content to wait.

### 14.2 Runs

The old "Record" tab, renamed. It is about past runs.

**The data already exists.** `record.db`'s `run` table stores
`built` -- the real timestamp, which genuinely differs from the date
printed on the paper (the 10-19 run is dated the 19th and was built at
10:43:37) -- plus the run seed, the title, the date and the output
folder. Per-skill version seeds come out of the `printed` table; the
Extravaganza has 57 distinct skill/version/seed combinations. Two new
columns are needed and nothing else: **delisted** and **graded**.

**The list** is every run, newest first, showing title, date, build
time, run seed, papers, students, and whether it has been graded.

**Drilling in replaces the list with that run's page**, with a back
link, and previous/next so a run can be stepped through without going
back each time. Not an expanding row -- the detail is 50+ rows of
seeds and would push the list a screen and a half down. Not a side
panel -- the content column is about 900px and a split leaves too
little for the seed table. The same drill-in serves a single student
in Progress, so it is one pattern used twice.

The detail shows which skills were in the run, how many papers of
each, how many versions, and the version seeds per skill.

**Two actions, deliberately separate**, because merging them is how
somebody reprints last month's papers by accident:

* **Reprint exactly** -- the existing `build --replay`. Same students,
  same seeds.
* **Start a new run from these settings** -- the selection, variants
  and extras, drawn fresh against today's roster. **Warns** if the
  Print tab has unsaved work.

**Delisting** moves a run into a collapsed group at the bottom of the
list rather than hiding or deleting it. **A graded run cannot be
delisted** -- the option is not offered at all, rather than offered
and refused.

A graded run also offers **open in Scans**, to review what was read.

### 14.3 Progress

Students down the left, **all of the bank's skills** across the top --
not only the ones offered so far. Both sections together for now; an
app-wide section filter, shared with Roster, is a later job.

**Up to three facts per cell**: passed or not, how many passes, how
many attempts. 45 students by 29 skills is about 1,300 cells, so a
number in every one is a wall. Two rules cut it down:

* **A pass count only appears where the threshold is above 1.** Where
  one check passes a skill, "how many passes" says nothing that
  "passed" does not. This semester that is every skill, so the third
  fact disappears entirely -- and the design still holds next
  semester, when some skills need two.
* **An attempt count only appears when it is surprising.** Passed
  first time needs no number. Four attempts and still not passed is
  the thing worth seeing from across the room.

| state | the cell |
|---|---|
| never taken | empty |
| passed, first attempt | a tick, quiet |
| passed after several | a tick with a small count |
| not passed, one attempt | an empty box |
| **not passed, several** | **an empty box with the count, and the loudest thing on screen** |
| threshold 2, one so far | a half state and `1/2` |

**Passing is quiet.** The instructor's call, and the right one: a
gradebook is scanned for trouble, and 1,300 green cells would drown
it. **With an option to highlight recently passed skills** in the
accent, for the pass that has just come back from a grading run.
"Recently" is not yet defined -- see 14.8.

**Thresholds live with the course, not the bank.** They change from
semester to semester and `bank.xml` is the shared, published file.
Default 1, overridable per skill.

**A single student drills in**, the same way a run does: their
history, when each skill was attempted, at which seed, with a link to
the scan.

### 14.4 Scans

The largest of the three and the one with real risk in it.

#### What arrives

Not a tidy stack. From the instructor:

* **Several PDFs**, because one is too large for the printer to email.
* **Both sides**, but not always -- **fronts and backs may land in
  different batches**.
* **Blank pages may be included.**
* **The papers are all mixed up.**

So page order carries no information whatsoever, and the two halves of
one sheet may not even be in the same file. **Every page has to
identify itself on its own.** That is what 14.5 is for, and it is why
the print change is on the critical path rather than being a nicety.

#### What a page already says

`printit.sty` prints, today: the student's name at the top left, `v`
and the version seed at the bottom centre, and -- **on the first page
of a skill only** -- the skill slug and the rounded box in the outer
bottom corner. The continuation style deliberately omits the box, with
a comment saying one skill should be ticked once. The box swaps
corners between left and right according to the page's side.

Two consequences:

* **Identity does not need handwriting recognition.** It needs a
  printed slug and seed read from a known corner, in a known font.
* **The mark does not need finding.** Its position is known, so the
  job is to crop a known region and classify it, which is far smaller
  than reading a page.

But a name printed at the top is not enough on its own, for two
reasons the instructor raised: a run can be printed with **blank name
lines**, and **a student can sit a skill without being in the run's
manifest** -- they pick up a spare. Both are handled in 14.5.

Blank padding pages use `\pagestyle{empty}` and so carry no footer at
all, which makes them identifiable by what they lack.

#### Reviewing

A grid of students against the skills in that sitting, which is close
enough to the Progress grid to share its parts. Each cell shows **the
cropped image of the actual box** beside the reading, so the
instructor confirms against the paper rather than against the
classifier's confidence. (This was already in the prototype; it is
recorded here because it is the thing that decides whether the tab is
trusted.)

#### Marks

The instructor uses exactly two: **a check whose tail comes out past
the box**, and **a `?` beside the box**. `?` is its own state, not a
note on a failure.

Other instructors will use other marks, so **states are configurable
per course** and a mark maps to a state. Every correction the
instructor makes during review is a labelled example, which is where
training data comes from without anyone being asked to produce any.

Starting simple is fine: a tick against an empty box, inside a known
rectangle, is close to a pixel-density question. Store the crops from
day one so a classifier can be trained later on real marks rather than
synthetic ones.

#### Saving

One action, with the rest following from it:

1. Attempts recorded for each student and skill.
2. Passes recorded, against the course's threshold.
3. The runs involved marked **graded**, which also makes them
   undeletable and gives them the "open in Scans" action.
4. *(stretch)* Per-student PDFs into their own shared Drive folder,
   set up once a semester.
5. *(stretch)* An email to each student with the results and a link.

#### Storage

The original PDFs are kept untouched. Per-student output is **PDF**,
not images, because that is what gets shared and what a student can
read; images are a working step for the classifier and belong beside
the crops, not in front of the instructor.

### 14.5 What a printed page must carry

The print-side change this all rests on, and **the one piece that must
land before the first run of next semester** -- a paper printed
without it can only be scanned by reading text.

* **A machine-readable code in the footer**, carrying the run seed,
  the skill, the version seed and the page's index within that skill,
  plus the student id when the run has names. Splitting then needs no
  OCR at all, and a double-feed or a missing page is **detected**
  rather than silently filed under the wrong student.
* **The run seed, visible**, as a dashed suffix on the version in the
  bottom centre -- `v617-398621586`. The instructor's idea, and it
  means a loose sheet can be traced to its run by eye.
* **A student id field at the top**, beside the name: filled
  automatically when the run is named, and left blank to be written in
  when it is not. Printing it as one box per digit is worth doing;
  separated digits are the most reliable handwriting there is, and
  this is the only handwriting the system has to read.

That last one is what lets an unnamed spare be graded at all, and it
is why the manifest cannot be the only source of truth about who sat
what.

### 14.6 Brightspace

Researched rather than guessed. Brightspace matches a grade column
**by the grade item's name**, not by a numeric id:

* The identifying column comes first: **`OrgDefinedId`**, or
  **`Username`**, or both.
* Each grade column is headed **`<Item name> Points Grade`**. The
  header may carry bracketed metadata (max points, weight, category);
  the `Points Grade` text itself must be exact.
* The last column must be **`End-of-Line Indicator`**, with `#` in
  every student row.

Every institutional guide gives the same advice: **create the grade
items in Brightspace, export the CSV, and fill that file in** rather
than building one from headers. A hand-built file fails with an
unhelpful "can't read the file".

**So the export should take his exported CSV as a template and fill
it**, rather than generating headers of its own. That removes the
entire class of name-matching bugs and is the only version that
survives an instructor renaming an item.

Open: whether `OrgDefinedId` is the SID the roster already holds, and
whether `Username` is the email's local part. Both look right and
neither is confirmed; one round-trip with a real export settles it.

### 14.7 Build order

1. **Runs.** The data already exists; this is a list, a detail page
   and two flags.
2. **The page marks (14.5).** Out of order on purpose -- it has to be
   printing before next semester's first run or Scans starts from a
   worse position permanently.
3. **Scans.**
4. **Progress.**

### 14.8 Still open

* **What "recently passed" means** for the highlight: since the last
  grading run, within N days, or until acknowledged.
* **Where thresholds are stored** -- a new course file, or a table in
  an existing one.
* **How a custom state maps to Brightspace.** A tick is a pass and a
  blank is not; `?` and anything an instructor invents need a stated
  answer before export can be trusted.
* **The Brightspace identifiers**, per 14.6.
* **How much classifier to build.** The honest first version is
  geometric, with crops stored so a trained model can replace it on
  real data later. Where that line sits is not decided.
* **Whether Scans can place a page whose run is unknown** -- an old
  paper with no code, from before 14.5 ships.

---

## 15. Roadmap (2026-10-22)

What is left, in the order it should happen. Dates are a semester, not
a schedule: the only hard deadline is 14.5, which has to be printing
before the first run of next term.

| # | what | why here | size |
|---|---|---|---|
| 1 | **Stage 4** of section 13 -- save bar, warning strips, empty states, a microcopy pass | finishes what is half-done before starting something new; every new tab inherits it | small |
| 2 | **Runs** (14.2) | the data already exists; two columns and a list | small |
| 3 | **The page marks** (14.5) -- code in the footer, run seed on the version, an id field | **deadline: before the first print of next semester.** Everything in Scans rests on it | small, but touches `printit.sty` and the theme both banks load |
| 4 | **Scans** (14.4) | the big one. Import, split, classify, review, save | large |
| 5 | **Progress** (14.3) | cannot show anything true until 4 feeds it | medium |
| 6 | **Brightspace export** (14.6) | needs Progress, and one round-trip with a real export file | small |
| 7 | Drive folders and student emails | explicitly a stretch; the rest has to work first | -- |

Two things worth saying about the order.

**Stage 4 first, not last.** It is the smallest item here and three
new tabs will each need a save bar, an empty state and warning
strips. Doing it after would mean doing it four times.

**Item 3 is out of dependency order on purpose.** Nothing else needs
it to exist, and it needs to exist before paper is printed. A term's
worth of papers without a code can only ever be scanned by reading
text off them.

### Outstanding comments

The instructor has further notes on the Roster that he parked in order
to get every tab looking alike first. They should be collected before
stage 4 rather than after, since stage 4 is the last pass over the
existing tabs.
