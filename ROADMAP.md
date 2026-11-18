# Roadmap

**The one list of what is still to do, for every repo.** It replaced
section 15 of the design document on 2026-11-17, and before that six
"Still open" sections had to be read together to find it. When an item is
done, move it to **Done** at the bottom with a date and the notes section
that records it -- do not leave it struck through here.

References: `DESIGN n.n` is a section of `checkit-printit/DESIGN.md`;
"notes, X" is a `##` section of `CODEBASE_NOTES.md`.

## Real work

| | what | repo | where written up | blocked on |
|---|---|---|---|---|
| 1 | **One real gradebook round-trip.** The export is built, rewritten against his own `apply_to_brightspace.py`, audited against the record, and byte-identical to the old CLI path on his 11-13 exports. What it has never had is an upload and a re-download to compare | printit | DESIGN 14.6, 18 | him, at the next grading |
| 2 | **A second, independent plan** for the export, as his script has. `verify_export` and the audit catch a stray or unbacked write, not a wrong plan written faithfully | printit | DESIGN 18 | nothing; only worth it if the export ever runs unattended |
| 3 | **Read marks in, one way**, to seed a record from an existing gradebook | printit | DESIGN 18 | a decision: what a mark with no printed paper behind it looks like on Progress |
| 4 | **Publish `F5-E`** as a real `<outcome>` in mat-106's `bank.xml`. The slug appears only inside `<associates>`, which nothing reads, so it generates and publishes nothing | mat-106 | DESIGN 14.8 | nothing |
| 5 | **The Settings tab's boilerplate editor.** A form can be created or attached from the app; editing its fixed text cannot | printit | DESIGN 12.6 (stage 8h) | nothing |
| 6 | **Make the four renderers agree.** The student page (Svelte) and `html.xsl` / `latex.xsl` / `pretext.xsl` differ on: a knowl with both content and parts; several outtros (print keeps the first); an element inside `<m>` (the stylesheets keep the first text only); `<em>` in a title. Proposed ruling: show everything, everywhere. Touches upstream code and what students see, and the student page has no JS tests, so it is checked in a browser. `checkit check` now reports every case (`dropped`, `nested-in-m`); mat-106 hits none | platform | notes, "The renderer check" | **his ruling on each case** |
| 7 | **A corpus of real, masked crops** for the scan thresholds, so a change to one is checked against every stack so far rather than the latest | printit | notes, "The whole codebase, read by a different model" | masked crops from a second stack |
| 8 | **The re-scan glyph.** The chip reuses the `record` glyph; a circular arrow of its own needs the measured harness (r >= 5.8 was solved at 21px; a chip draws at 18) | printit | -- | his eye |
| 14 | **Ask GitHub Support to purge the rewritten commits.** The force-push of 2026-11-17 replaced 206 commits in `checkit` and 231 in `checkit-printit`, but GitHub still serves the old ones by id, and `checkit` shares storage with its upstream's fork network. Only Support can remove them and their cached views. The ids are in `~/CheckItPrintIt/history-rewrite-2026-11-17.txt` -- never in a repo, since each leads straight to an old commit | all | notes, "Real students in the public history" | **him** -- it is a request from the owner |
| 9 | **Tests must not reach the real home.** A module-scoped fixture in `test_scans.py` wrote a vault into `~/CheckItPrintIt` on 2026-11-17. A session-wide `CHECKIT_PRINTIT_HOME` in `conftest.py` would stop every such fixture at once; check which tests rely on the default first | printit | notes, "Pseudonyms in everything the command line prints" | nothing |

## Decisions that are his

| | question | where written up |
|---|---|---|
| 10 | **Can Scans place a page with no footer code?** Every paper printed before the codes shipped is one | DESIGN 14.8 |
| 11 | **Where do the thresholds live?** The code reads `[passing]` in `course.toml` today, so this may already be settled -- confirm rather than re-decide | DESIGN 14.8 |
| 12 | **Does a run number need its course?** Unique within a course today, and Scans is course-scoped | DESIGN 14.12 |
| 13 | **What does a hand-authored bank's `bank.xml` look like?** Waits on MAT 206's rebuild, which is not scheduled | DESIGN 11.4 |

## Never run, so not known to work

- **`wrapper.sage`** was changed to match the Python wrapper (RV-11) and
  has never been run: there is no Sage on this machine.
- **The wheel.** `appsscript/` is listed as package data (RV-9) but no
  wheel has been built to check it is inside. In `checkit-printit`:
  `pip wheel . --no-deps --wheel-dir dist`, then look in the `.whl` (a zip) for
  `appsscript/`. Needs a `setuptools` download.

## Small, known, not urgent

- **`svelte-check` fails** on `Jumbotron.svelte`, which imports a
  `./dropdowns/Bank.svelte` that does not exist. Pre-existing.
- **The Demo course's Skills view answers 400**, because Demo has no
  `availability.toml` and the view reads it unguarded. A course without
  the file should get an empty view.
- **`drop_columns` pads a line above the header** with empty cells when a
  file with a preamble is trimmed for import. Nothing reads that line.
- **The demo bank's EX3 puts an HTML `<ul>` in an intro**, which all three
  stylesheets drop. Upstream's example; `checkit check` reports it.

## Waiting on the world, not on work

- **Nobody but its author has driven the Scans tab.** The save path, the
  re-match and the clash warning are tested and have run against real
  pages, but not in someone else's hands.
- **Four calibration numbers**, each fitted to one stack off one copier,
  each wrong on a different one. They want a second scanner or a second
  term's stack, not another guess:
  - `INK_FLOOR` (0.005) -- below it, a page with no code is blank rather
    than unreadable. Made against simulated scans.
  - `BESIDE_MAX` (0.60) -- more ink beside the box than this is working,
    not his `?`. Fitted to the 62 pages of 2026-10-26.
  - `digits.ACCEPT` (-4.5) and `digits.MARGIN` (2.3) -- the id grid's
    floor and lead. Four pages, two pens, thirty-six digits.
  - `scans.ID_INK` (240) -- paper versus printed rule when finding the
    grid. His copier: rules 205-235, paper 250-255.

## Look and feel, parked deliberately

Each is his call, and each was parked for a reason (DESIGN 13.8).

- **Section bands vanish under any sort that is not by section**, so the
  820/830 split goes invisible. The trade of the design; not ruled on.
- **Section header treatment.** Six tried, six rejected; to be judged
  against a whole tab on screen.
- **Row height.** `--t-base` is 15px; the 36-40px row target is untested
  against 45 students.
- **The rail folds to icons below 900px**, so a narrow window never shows
  labels. The right threshold is unknown until used at a real size.
- **A thin top strip, or none.** Nothing replaced the top bar.
- **One student always reads in natural order**: a two-word surname the
  splitter returns as one. Making a split correctable is a roster feature
  nobody has asked for.
- **`Last, First` makes the Name column read-only**, because the filed form
  is derived.
- **The glyph pass** (opened 2026-11-08): the Settings gear, the door and
  the Runs glyph are done. Ask him whether the pass continues.
- **The Roster's "remaining comments"** were never enumerated (2026-10-20)
  and are not recoverable. The items above are what he could react to
  instead; do not go looking for a list that does not exist.

## Stretch

- Drive folders and student emails. Explicitly last.

## Done

Newest first. Older work is in the notes; search them by date.

- **2026-11-17** -- real students scrubbed from the history of `checkit`
  and `checkit-printit` and force-pushed; git hooks in all three repos
  refuse a commit or push that adds one. Notes, "Real students in the
  public history".
- **2026-11-17** -- the documents reorganised: house rules in one shared
  file, this roadmap, printit's map cut from 2,191 lines to a map, the
  design document moved into the repo it describes. Notes, "The documents,
  reorganised".
- **2026-11-17** -- pseudonyms in everything printit's command line
  prints, switched on for these repos. Notes, "Pseudonyms in everything
  the command line prints".
- **2026-11-17** -- `checkit check` reports SpaTeXt the stylesheets drop
  (`dropped`), over every version, print-only ones included. Notes, "The
  renderer check".
- **2026-11-17** -- prose escaped in `latex.xsl`; the review's "from
  reading" list and duplication table. Notes, "Prose escaping, and the
  review's smaller items".
- **2026-11-17** -- RV-1 to RV-14, all fixed and break-checked; mat-106
  republished (R1 had been stale five weeks); W7 in maths; figures in the
  viewer's assessments. Notes, "Fixing what the review found" and "His
  answers, and what was done with them".
- **2026-11-16** -- the whole codebase reviewed by a different model.
  Notes, "The whole codebase, read by a different model".
- **2026-11-10** -- Progress opens section-then-surname; the section band
  pins left; each table keeps its own name order.
- **2026-11-09 to 11-13** -- the gradebook profile, `gradebook map` and
  `gradebook export`; the import file cut to what Brightspace reads.
  Matching is on `OSW_ID`, so no LMS ids need importing; printit never
  replaces a pass; Brightspace recalculates the subtotals itself.
- **2026-11-08** -- `checkit-printit vault`, and `vault mask-course`.
- **2026-11-03** -- the handwritten id; the Scans tab rebuilt.
- **2026-10-22 to 10-27** -- stage 4, Runs, the page marks, Scans,
  Progress.
- Struck as not wanted: a section filter on Progress (a misreading of the
  table sorting, which is built).
