# Writing generators

A generator produces the *data* for one version of an exercise. The template
decides what to say with it.

```python
# outcomes/W1/generator.py
import random


class Generator(BaseGenerator):
    def data(self):
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        return {"a": a, "b": b, "product": a * b}
```

```xml
<!-- outcomes/W1/template.xml -->
<knowl mode="exercise" xmlns="https://spatext.clontz.org" version="0.3">
    <content><p>Compute <m>{{a}} \times {{b}}</m>.</p></content>
    <outtro><p><m>{{product}}</m></p></outtro>
</knowl>
```

Every key you return is available in the template. Nothing else is.

---

## Generation is reproducible

CheckIt seeds `random` before each call, so **the same seed always produces the
same data**. That is what makes a version stable: "W1 version 137" means one
specific exercise, today and next semester.

Two consequences worth internalising:

- `checkit generate -r` on an *unchanged* generator rewrites byte-identical
  output. It changes nothing.
- Editing a generator and *then* running `-r` moves every version. If students
  are mid-assignment, that is the thing to avoid — see
  [freezing](checking.md#freezing-an-outcome).

Do not seed `random` yourself, and do not read the clock, the filesystem, or
anything else that varies between runs.

---

## What a generator can reach without importing

The generator runs in a prepared namespace. These are already defined:

| | |
|---|---|
| `BaseGenerator` | the class to subclass |
| `PUBLIC_SEEDS`, `BUNDLE_UNTIL` | the seed-range boundaries (see below) |
| `randrange`, `shuffle`, `choice`, `sample` | from `random` |
| `provide_data` | decorator for figure methods |
| `CheckIt`, `var`, `latex`, `matrix`, `plot`, … | the SageMath-flavoured helpers |

You may `import` anything installed as normal — `random`, `fractions`,
`decimal`, third-party packages listed in your `requirements.txt`, and your own
`bank_helpers`.

---

## `self.seed` — branching on which version this is

The three seed tiers mean something, and a generator can act on them:

| seeds | meaning |
|---|---|
| below `PUBLIC_SEEDS` | a student browses this version on the site |
| `PUBLIC_SEEDS` and above | this version feeds an assessment — printed or exported |

```python
class Generator(BaseGenerator):
    def data(self):
        studying = self.seed < PUBLIC_SEEDS
        return generate(pool="self_study" if studying else "assessment")
```

Use this when the *purpose* differs: a self-study version might carry a worked
explanation where an assessment version leaves blanks. Do not use it for
anything about how the exercise looks — that is what SpaTeXt elements and
stylesheets are for.

---

## `variants` — pregenerating an axis

Some exercises vary along an axis that is not randomness: which topic a word
problem uses, whether multiplication has been covered yet, whether the answer
may be a repeating decimal.

Declare the axis and CheckIt deals it across the seed space:

```python
class Generator(BaseGenerator):
    variants = ["no_repeating", "repeating"]

    def data(self):
        return generate(allow_repeating=self.variant == "repeating")
```

- Labels are dealt by a shuffle bag under a fixed RNG seed, so the split is
  even and reproducible. Two labels across 1000 seeds gives exactly 500 each.
- The label is recorded in each version's data as `__variant__`, so anything
  reading `seeds.json` later can filter on it.
- Weight an axis by repeating a label: `["easy", "hard", "hard"]` makes two
  thirds hard.

**Why this rather than a setting.** A parameter chosen at generation time bakes
one answer into the whole bank — advancing the semester then means editing files
and regenerating. A variant pregenerates *every* case, so a later consumer picks
what it wants without touching the bank.

Check that both labels actually change the output. A variant that changes
nothing is decoration, and it doubles the seed space for no reason.

---

## Figures

Return TikZ source from `tikz_graphics`, keyed by name:

```python
class Generator(BaseGenerator):
    def data(self):
        return {"n": 3}

    @provide_data
    def tikz_graphics(data):
        return {
            "p1_prob_model": tikz_number_line(data["n"], mark=None),
            "p1_ans_model":  tikz_number_line(data["n"], mark=data["n"]),
        }
```

Each key becomes `assets/<slug>/generated/<seed>/<key>.tikz`, and
`<key>.png` when `-i` is passed. Reference them from the template:

```xml
<content>
    <p><image source="assets/W1/generated/{{__seed__}}/p1_prob_model.png"
              description="a number line"/></p>
</content>
<outtro>
    <p><image source="assets/W1/generated/{{__seed__}}/p1_ans_model.png"
              description="the same line, marked"/></p>
</outtro>
```

**The `_prob` / `_ans` pair is the convention worth following.** When a figure
*is* the answer — a marked point, a shaded region — emit two figures rather than
one, and put the second in the `<outtro>`. The viewer then hides and shows it
like any other answer, and print can pick whichever it needs.

`graphics` works the same way for matplotlib or Sage plots. `.tikz` is written
for every seed regardless of `-i`, so LaTeX output never depends on
rasterisation.

---

## SageMath

Name the file `generator.sage` and it runs under `sage` instead. Nothing else
changes; the class and `data()` are identical.

Three Sage-isms fail *silently* under plain Python, so they are worth knowing if
you are converting one:

- `choice(a, b)` — Sage's takes two arguments, Python's does not.
- Sage integers stringify differently from Python `int` in some contexts.
- `^` is exponentiation in Sage and XOR in Python.

`checkit check --no-built` runs every generator in-process and shows the real
traceback, which is the fastest way to find these.

---

## Debugging

`checkit generate` runs generators in a subprocess and reports only that one
failed. To see the actual exception:

```
checkit check --no-generators=false --no-built
```

or just `checkit check --no-built`, which runs every generator across a spread
of seeds and every declared variant, and prints the traceback with line numbers.
It needs no build and takes seconds.
