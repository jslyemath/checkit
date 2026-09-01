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

Today: a CSV exported from a Google Sheet, located by a Tk file dialog, parsed
by finding the literal string `Full Name:` and reading right and down.

Proposed: a **roster adapter** interface with two implementations from the
start —

- `CsvRoster` — the current export, so nothing breaks on day one;
- `GoogleFormsRoster` — pulls responses directly (§7).

Both produce the same structure:

```python
Student(name, section, variant, skills=["W1", "N3", "F2"])
```

### 4.3 Seating chart

Currently a second Google Sheet, and currently **not used by the tool at all** —
students print in roster order.

It determines three things:

- the **order** students are printed in, so a stack of paper matches a room;
- how many **distinct versions** are needed, which is a property of the seating
  (neighbours must differ), not of the class size;
- how versions are **shuffled** across seats.

Proposed input, deliberately simple:

```toml
[seating]
rows = [
  ["Alice", "Bob",   "Carol"],
  ["Dave",  "Erin",  "Frank"],
]
```

or a CSV of the same shape. The tool then derives the version count from the
layout rather than being told it.

**Longer term** this becomes a feature of the print tool: give it a room shape
and a roster, and let it assign seats and versions to satisfy "no two adjacent
students share a version". That is a small constraint-satisfaction problem and
is much better solved in code than in a spreadsheet.

---

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

---

## 9. Staging

Each stage ends with something that works.

**1 — Package the existing tool.** `pdfgenerator.py` cleaned up, importable,
tested, reading the same CSV. Same output. Establishes the repo, the theme's
home, and a golden-PDF comparison to protect everything after.

**2 — Pregenerated seeds.** Swap generator-at-print-time for seeds 400–999.
First point at which printing needs no generator environment.

**3 — Publication file.** Replace the named cells. Implement or drop the three
dead settings.

**4 — Seating and extras.** Ordering, version count, extras with blank names,
optional keys.

**5 — Output guarantee.** The folder compiles standalone; a test asserts it.

**6 — Google.** Read first, then write.

**7 — SpaTeXt fallback.** Skills with no `textemplate.tex` render through
`latex.xsl`. Optional, and last, because nothing needs it until a new bank is
authored without print templates.

---

## 10. Open questions

Collected for the review conversation rather than answered here.

1. Whether the theme ships in the print package with a bank override (as agreed
   for `bank_helpers.sty`), and what happens to the two banks' identical copies.
2. Whether "how many versions" should be derived from seating or stated
   outright.
3. Whether extras are per-skill or per-packet.
4. Whether the roster's variant column survives, given variants now mean
   something specific in CheckIt.
5. What a hand-authored bank looks like end to end, since MAT 206 is one.
6. Whether output should be reproducible byte-for-byte given the same inputs.
