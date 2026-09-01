# Getting started

## Install

```
pip install "checkit-dashboard @ https://github.com/jslyemath/checkit/releases/download/v0.2.8.5/checkit_dashboard-0.2.8.5-py3-none-any.whl"
```

> **Not `pip install checkit-dashboard`.** That name on PyPI is the upstream
> project — different code sharing a version number. None of the features in
> this guide exist there.

Python 3.10 or later. A LaTeX installation is needed only if your bank has TikZ
figures. SageMath is optional.

## A first bank

```
checkit new my-bank
cd my-bank
pip install -r requirements.txt
```

`checkit new` writes a `requirements.txt` already pointed at the right wheel, so
that second step installs the matching platform version.

You now have one example outcome, `EX1`. Generate it:

```
checkit generate -a 1000
```

That runs the generator a thousand times and renders every version. Then build
the site:

```
checkit viewer
python -m http.server --directory docs
```

Open <http://localhost:8000>. You will see the bank, one outcome, and a picker
offering 50 versions.

**Both commands are needed.** `generate` writes `assets/`; only `viewer` copies
it into `docs/`. Running the first without the second is the most common reason
a site looks stale, and it fails silently.

## Adding an outcome

Two files and a manifest entry.

```
mkdir -p outcomes/W1
```

```python
# outcomes/W1/generator.py
import random


class Generator(BaseGenerator):
    def data(self):
        a = random.randint(2, 12)
        b = random.randint(2, 12)
        return {"a": a, "b": b, "product": a * b}
```

```xml
<!-- outcomes/W1/template.xml -->
<?xml version='1.0' encoding='UTF-8'?>
<knowl mode="exercise" xmlns="https://spatext.clontz.org" version="0.3">
    <content><p>Compute <m>{{a}} \times {{b}}</m>.</p></content>
    <outtro><p><m>{{product}}</m></p></outtro>
</knowl>
```

```xml
<!-- in bank.xml, inside <outcomes> -->
<outcome>
    <title>Multiplication facts</title>
    <slug>W1</slug>
    <path>outcomes/W1</path>
    <description>I can multiply two single- and double-digit numbers.</description>
</outcome>
```

Then:

```
checkit check --no-built     # does the generator run? seconds, no build needed
checkit generate -a 1000
checkit viewer
```

Get in the habit of `checkit check` before `generate`. It catches a broken
generator in seconds and shows the real traceback, which `generate` does not.

## Figures

Return TikZ source and it becomes a file per seed:

```python
    @provide_data
    def tikz_graphics(data):
        return {"fig": r"\begin{tikzpicture}\draw (0,0)--(%d,1);\end{tikzpicture}"
                       % data["a"]}
```

```xml
<p><image source="assets/W1/generated/{{__seed__}}/fig.png"
          description="a line"/></p>
```

Rasterising needs `-i`:

```
checkit generate -a 1000 -i --remote https://you.github.io/my-bank
```

`--remote` becomes required once a bank has figures: the precomputed HTML is
read outside your site — in LMS exports and the AI payload — where a
root-relative `<img src>` 404s. `generate` refuses up front rather than
several minutes in.

For a quick preview, `--image-seeds 5` rasterises only the first five. Do not
ship that: the viewer shows 50 versions, and the rest would have broken images.

## Publishing

`docs/` is a plain static site. On GitHub, enable Pages and point it at the
`docs/` folder on your default branch.

```
checkit generate -r -a 1000 -i --remote https://you.github.io/my-bank
checkit viewer
git add -A && git commit -m "rebuild" && git push
```

Two things to know:

- **`docs/` is a committed build artifact.** Nothing regenerates it when you
  push, so the site is only as fresh as the last `checkit viewer` you committed.
- **The front page shows the build date.** If it looks old, it *is* old — that
  is not a display bug.

## What students see

- A **version picker** offering 50 versions of each exercise.
- **Show answer** toggles, per part.
- A **code cell** revealing the underlying data, for the curious.
- **Copy for AI Chatbot** — the exercise *and its answer*, with absolute image
  URLs a model can fetch, plus a prompt you can set per bank or per outcome via
  `<ai-prompt>`.

## What you get as an instructor

- An **assessment builder** that draws versions students cannot browse.
- **LMS export** to Canvas, Brightspace, Moodle and plain text.

## Next

| | |
|---|---|
| [CLI reference](cli.md) | every command and option |
| [Bank format](bank-format.md) | `bank.xml` and the files a bank can contain |
| [Writing generators](generators.md) | variants, seeds, figures, SageMath |
| [SpaTeXt reference](spatext.md) | the template vocabulary, and its traps |
| [Checking a build](checking.md) | `checkit check`, and freezing an outcome |
