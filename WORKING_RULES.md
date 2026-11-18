# House rules

Shared by `checkit`, `checkit-printit` and `mat-106-checkit`. Each repo's
`CLAUDE.md` pulls this file in with an `@` import, so this is the **one
copy**: change a rule here, not in a map. Every rule below cost something
real at least once; the story behind each is in `CODEBASE_NOTES.md`.

## First, before anything else: student names

**On the first interaction in any of these repos, check whether names are
masked:**

```bash
echo "masking=[$CHECKIT_PRINTIT_MASK_NAMES]"
```

**If it does not print `masking=[1]`, stop and ask the instructor whether to
turn it on**, before running any printit command or opening any course
file. It is turned on by `"env": {"CHECKIT_PRINTIT_MASK_NAMES": "1"}` in the
repo's `.claude/settings.json` (both `checkit` and `checkit-printit` have
it as of 2026-11-17). This comes before the task you were given.

What it does: everything printit's command line prints passes through the
course vault on the way out, so a real name, id or address arrives as that
student's pseudonym. The instructor reads anything you quote back with
`checkit-printit vault unmask -c <course>`. It fails closed: an unreadable
vault stops the command and names no one. Design: `privacy.py`.

**What it does not cover -- these are on you:**

- **Reading a file yourself.** `Read`, `cat`, `grep` on `roster.toml`,
  `seating.toml`, `room.json`, `record.db`, a class list or an export shows
  real names. Ask printit instead (its output is masked), or make a twin
  with `vault mask` and read that.
- **The web app's pages.** They are the instructor's view. Reading a page of
  a real course in the browser pane shows real names; use `Demo` or
  `Scratch 48` for anything visual.
- **Scripts you write.** A probe that prints a value prints the real value.
  Print counts, booleans and redacted lines (`####` for the value), as the
  probes in the notes do.

Where real names live: every course under `~/CheckItPrintIt/`,
`mat-106-checkit/TeX Outputs/` and `PDF Outputs/` (gitignored), and
`../FundCheck` (not a repo). **Never commit them, never paste one into chat.**
Test fixtures are invented on purpose; keep them that way.

## What this project believes

The decisions the history kept arriving at. When a choice comes up that
these settle, they settle it.

1. **Fail loudly.** A refusal with a sentence beats a quiet default. A
   wrong guess written into a gradebook, a twin, or a printed paper is
   found by a student, weeks later. An error path that prints nothing is
   worse than one that prints the wrong thing.
2. **One copy of each rule.** A second copy is how fixes ship to one path
   and not the other -- it has happened with option names, deploy helpers,
   the gradebook export, the TOML writer. Where two copies are deliberate
   (`Roster.live()` in two places, the seat sweep in Python and JS), a test
   holds them together and the code says so.
3. **Make the tool enforce it.** A paragraph saying "never" has been
   ignored here every time it mattered; a test, a trigger, a hook or a
   refusal has not. When a rule is broken twice, turn it into code.
4. **The record is the only account of who held which paper.** A run with
   marks is never deleted or rebuilt; delisting hides and never deletes;
   printed is not attempted.
5. **Ids, never positions, never a name alone.** Join on student id, then
   the other id, then email. Store form answers against a question's id.
6. **If a human is the author, TOML; if the tool is, SQLite.** TOML files
   carry hand-written comments, so edit their lines -- never parse and
   re-dump them.
7. **His own tools and words are the specification.**
   `apply_to_brightspace.py`, the retired `control_center.gs`, and what he
   said in chat outrank an invented rule. Where they disagree with the
   code, the code is wrong.
8. **List what is needed, not what is known to be bad.** The import file
   carries the identifier and the skills written; nothing else. A
   blocklist was never finished.
9. **Absence means the old behaviour.** A file written before a key
   existed describes a run that did not have it.
10. **Restraint.** Offered a louder and a quieter version, he takes the
    quieter. Layout over sentences, two-word labels, no control beside
    another control, explanations behind a `?`.
11. **Decide in writing before building.** A design agreed in
    conversation goes into the design document first; a one-line summary
    of a mockup is not a spec.

## Checks that have failed silently here

Each shipped something wrong while reporting success.

- **Never a heredoc, never `sed` on code.** A heredoc turns `\n` in a
  Python string into a real newline; `sed` reads `\u` as an escape and
  breaks every `\usepackage`. Write the script with the Write tool, put
  `assert text.count(old) == 1` in it, run it. **A hook now refuses any
  Bash command containing a heredoc, or `sed -i`** (`.claude/hooks/
  no_heredoc.py`, wired into all three repos), because this paragraph
  alone did not stop it. A commit message goes in a file written with the
  Write tool, then `git commit -F <file>` -- never `-m "$(cat <<EOF`, and
  never backticks inside a double-quoted `-m`, which are command
  substitution. Replace by anchor, never by index.
- **`command | tail` reports tail's exit code.** Redirect to a file, check
  `$?` alone, read the file.
- **A test that passes proves nothing until you have watched it fail.**
  Break the code on purpose. The test for the bug just fixed is the
  likeliest to be vacuous. A break-check that "noticed" because pytest ran
  no tests (a wrong test id) noticed nothing.
- **A clean result can be clean because nothing was shown.** A leak test
  passes on withheld output; a zero diff passes when the old code ran.
  Check the result is real before believing it is right.
- **Run it on real data** -- copies of it, with output that names no one.
  Many bugs here lived in code whose tests passed and appeared only
  against his actual files. Real files: `~/Downloads`, `~/CheckItPrintIt`.
- **Verify the artifact, not the dry run.** `build --preview` and `build`
  draw independently unless given the same `--seed`.
- **Operate the control.** Calling the endpoint tests the endpoint, not
  the button; `element.click()` skips hit testing and capture. Click it.
- **A fix applied to one path is not applied to the others.** When shared
  behaviour does not change, ask "is there a second copy", not "did it
  deploy".
- **A fake built from your own vocabulary cannot fail like the boundary.**
  Spell a fixture the way the far side spells it (clasp clones `.js`, not
  `.gs`).
- **A fixture small enough to be convenient hides what you measure.** Use
  `Scratch 48` for anything about size or layout.
- **A hand-built run is not the run he set up.** Start from
  `courses/<name>/job.toml` through `printjob.publication_text`, never from
  what was said in chat.
- **A surprising timing is the harness until proven otherwise** -- a
  hidden browser pane throttles; `getComputedStyle` returns stale values
  within a turn.
- **Do not declare something impossible without checking.** "A CLI cannot
  sign in to Google" was said twice and was wrong both times.
- **A merge is not done when tests pass.** Diff the commit against what you
  meant to merge.
- **A PDF existing is not a clean compile.** pdflatex writes one anyway.
- **Counting seeds is not counting figures.**
- **A build against a real job writes the real record**, and a test with no
  `CHECKIT_PRINTIT_HOME` of its own writes the real home.
- **After `generate -r`, republish the same day.** A deploy left undone is
  invisible from both ends: R1's site was five weeks stale.
- **`gh` defaults to a fork's parent.** Check `--repo` on anything that
  writes.

## Writing things down

| file | job | read it |
|---|---|---|
| each repo's `CLAUDE.md` | the **map**: what exists, which Python, the footguns of that repo | automatically |
| this file | the house rules, once | automatically, through the maps |
| `checkit/ROADMAP.md` | **everything still to do**, every repo, in one list | before saying what is left |
| `checkit-printit/DESIGN.md` | printit's design record: decisions and their reasons, by section number | before changing what it covers |
| `checkit/CODEBASE_NOTES.md` | the **history**: dated, append-only | `grep -n "^## "` and read a section |

**A change with reasoning behind it gets a dated `##` section in
`CODEBASE_NOTES.md`; the commit message is not the record.** Write what
was actually wrong, how it was found, what was ruled out, and what was
verified rather than assumed. Writing to a map is not writing to the
notes -- twenty-six commits once went unrecorded that way.

**A map holds what is true now**, in a few lines per thing, and points at
the notes for the story. It does not list what is open -- that goes in the
roadmap, which is the only list. When an item is done, move it to the
roadmap's "Done" with a date and a pointer to its notes section.
