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
   are no longer identical: mat-106 and the printit package carry a colour fix
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
| **Roster** | an editable table: preferred name / nickname, section, email, ids; mark dropped and undo it; import a class list and see the merge before it lands | `roster import`, `roster drop`, `roster restore` |
| **Skills** | toggle which skills are open for retake; set the assessment's name, date, due time, and the choose/limit rule; see the exact wording the form will show; push it | `skills open`, `skills set`, `skills preview`, `form push` |
| **Responses** | who has answered, who has not, what they chose; the addresses that matched nobody; pull into the roster | `form pull` |
| **Seating** | drag students between seats; randomise; swap two; see version letters and empty seats | *(none -- see below)* |
| **Print job** | choose skills and per-skill variant, extras, keys, names; preview the draw; build; open the PDF | `build`, `build --preview` |
| **Record** | what has been printed, to whom, when, at which seed; per-student and per-skill views | `record runs`, `record student`, `record skills` |
| **Cold call** | pick a random student, pick several, refresh the call list with its skip flags | *(none)* |
| **Setup** | create or attach the form, map items, course settings, bank path | `course init`, `form create`, `form attach`, `form map`, `form add-items`, `form connect` |

The last column is the useful part of this table: most of the GUI is a face on
code that exists and is tested. The two rows with no CLI are the genuinely new
work, and **seating is one of them** -- `randomizeSeating` and
`shuffleSelectedStudents` were Control Center features that have no printit
equivalent at all. That is worth knowing before estimating.

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
| 8a | the shell: serve a course, switch views, read-only everywhere | proves the backend reads what the CLI reads |
| 8b | **Roster** table, editable, with drop and restore | the most-wanted, and write-round-trip is the thing to get right early |
| 8c | **Skills** and the form push, with a visible diff | replaces the most tedious CLI sequence |
| 8d | **Print job**, including the variant dropdowns | the first view that needs the bank, not just the course |
| 8e | **Record** and **Responses**, both read-mostly | cheap once the shell exists |
| 8f | **Seating**, drag and drop, plus randomise and swap | genuinely new code; the interaction needs prototyping rather than specifying |
| 8g | **Cold call** | new, and the smallest |

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

