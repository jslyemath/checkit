# Checking a build

```
checkit check                  # generators, then the built bank
checkit check --no-built       # generators only; needs no build
checkit check --no-generators  # the built bank only
```

Exits non-zero on findings, so it works in CI. Both halves run by default;
`--generators` and `--built` are the explicit positive forms.

Every check here exists because a real build shipped the fault it catches while
everything else looked healthy. That is also the reason for the warning at the
bottom of this page.

---

## Generators

Runs every generator in-process across a spread of seeds — either side of both
range boundaries — and every declared variant.

```
generators
  ok   D1
  FAIL W4

===== W4
Traceback (most recent call last):
  File "outcomes/W4/generator.py", line 3, in data
    return {"x": undefined_name}
NameError: name 'undefined_name' is not defined
```

**This is the only way to see that traceback.** `checkit generate` runs each
generator in a subprocess and surfaces only `CalledProcessError` with the argv,
so a failing generator is near-undiagnosable from a build log.

It needs no build and takes seconds, which makes it the right thing to run after
editing a generator — before spending a rebuild to find out.

---

## The built bank

| check | catches |
|---|---|
| `missing-data` | a template field the generator never sets, which renders as nothing |
| `escaped-markup` | markup injected with `{{double braces}}`, showing `&lt;m&gt;` to a student |
| `raw-tex` | TeX rendering as literal text — commands *and* single-character escapes like `\%` |
| `control-char` | non-raw Python literals turning `\textpmhg` into TAB + `extpmhg` |
| `nested-in-m` | an `<m>` containing other elements, whose content both stylesheets drop |
| `math-punctuation` | sentence punctuation pulled inside inline maths, italicising a full stop |
| `relative-img` | root-relative `<img src>`, which 404s anywhere off-site |
| `latex-braces` | LaTeX that will not compile |
| `bundle` | the same, over seeds 50–399, which `bank.json` says nothing about |

Findings look like:

```
built bank
  FAIL [missing-data] D1-E: template uses {{units_block_a}}, which the
       generator never sets; it renders as nothing (x4)
```

Three of these have a design point worth not undoing if you ever edit them:

- **`raw-tex` matches single-character escapes too.** Requiring two or more
  letters after the backslash is what once let `27.6\%` and `\$770.13` ship in
  300 versions while the check reported clean.
- **`nested-in-m` reads the SpaTeXt, never the HTML.** The dropped content does
  not exist by the time there is HTML to inspect.
- **`latex-braces` deliberately does not flag `\text`, `\textbf` or `\mbox`
  inside maths.** All three are legal in math mode and used on purpose;
  flagging them produced 976 findings against a correct bank, which is how a
  check teaches people to ignore it.

---

## Freezing an outcome

Regenerating an outcome replaces every version of it. If students are working
through those versions, the problems change underneath a half-finished
assignment — and it is unrecoverable without the previous `seeds.json` from git.

Mark the outcome in `bank.xml`:

```xml
<outcome>
    <title>Converting between numeration systems</title>
    <slug>W1</slug>
    <path>outcomes/W1</path>
    <description>…</description>
    <frozen/>
</outcome>
```

`checkit generate -r` then refuses, by name:

```
SKIPPING W1: marked <frozen/> in bank.xml. Its existing seeds are kept.
To regenerate it anyway: --thaw W1
```

To regenerate it anyway:

```
checkit generate -r -a 1000 --thaw W1
```

`--thaw` is repeatable, and refused for a slug that is unknown *or* not actually
frozen — believing an outcome is protected when it is not is the failure this
prevents. There is deliberately no blanket `--force`, because that would be
typed reflexively.

### What freezing does and does not do

- **Blocks regeneration, not rendering.** A plain `checkit generate` still
  re-renders a frozen outcome, so a stylesheet fix reaches its published HTML
  without thawing. The problems do not change; only how they are drawn.
- **Keeps the outcome in `bank.json`.** Frozen means "keep these versions", not
  "drop this outcome".
- **Does not make an outcome immutable.** A stylesheet change can still alter
  how a frozen problem renders. If you need the stronger guarantee during an
  assignment, do not republish `docs/` at all.

Remember that generation is reproducible: `-r` on an *unchanged* generator
rewrites identical data. What freezing actually guards against is editing a
generator and *then* rebuilding.

---

## What this does not tell you

**A clean run is not a substitute for looking at the page.**

Three of these checks were written *after* a human spot-check found what the
automated checks had passed, and one of them had been passing an outcome that
rendered "is a multiple of" with both of its numbers missing.

These checks catch documents that will not compile and markup that will not
render. They say nothing about whether an exercise is *right*, whether its
wording is clear, or whether it breaks lines in a sensible place. Open the
viewer and read a few versions.

When investigating a problem, run the checks against the **previous** build as
well as the new one. The useful output is rarely "there are findings" — it is
"which of these are new today".
