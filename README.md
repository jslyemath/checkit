# CheckIt Platform

Author randomized exercises once, and publish them for practice, assessment,
and printing.

A bank is a folder of *outcomes*. Each outcome has a **generator** (Python that
produces the numbers) and a **template** (what the exercise says). CheckIt runs
the generator across a thousand seeds, renders every version to HTML, LaTeX and
PreTeXt, and publishes a browsable site.

This is [jslyemath's fork](https://github.com/jslyemath/checkit) of
[StevenClontz/checkit](https://github.com/StevenClontz/checkit). See
[Differences from upstream](#differences-from-upstream).

## Install

```
pip install "checkit-dashboard @ https://github.com/jslyemath/checkit/releases/download/v0.2.8.5/checkit_dashboard-0.2.8.5-py3-none-any.whl"
```

> **Do not `pip install checkit-dashboard`.** That name on PyPI is the upstream
> project — different code that happens to share a version number. None of the
> features below exist there. `checkit new` writes a `requirements.txt`
> pointing at the right wheel, so a bank scaffolded by this fork installs
> correctly.

Python 3.10+. SageMath is **optional** — generators are plain Python unless you
name one `generator.sage`.

## A bank in four commands

```
checkit new my-bank
cd my-bank
checkit generate -a 1000
checkit viewer
```

That leaves a static site in `docs/`. Serve it with
`python -m http.server --directory docs`, or push it to GitHub Pages.

## Documentation

| | |
|---|---|
| [Getting started](guide/getting-started.md) | install, first bank, publishing |
| [CLI reference](guide/cli.md) | every command and option |
| [Bank format](guide/bank-format.md) | `bank.xml`, the files a bank can contain, override points |
| [Writing generators](guide/generators.md) | `data()`, variants, seeds, figures |
| [SpaTeXt reference](guide/spatext.md) | the template vocabulary, and its traps |
| [Checking a build](guide/checking.md) | `checkit check`, and freezing an outcome |

[`CODEBASE_NOTES.md`](CODEBASE_NOTES.md) is the developer-facing companion: why
things are the way they are, what has been tried, and what is still open. It is
long and is not a user guide.

## What this fork adds

Beyond upstream, all documented in the guide above:

- **Plain-Python generators.** SageMath is optional rather than required; the
  file extension picks the runtime.
- **A TikZ image backend.** Figures are drawn as `.tikz` and rasterised to PNG;
  print uses the TikZ source directly.
- **Precomputed output.** Every version is rendered at build time, so the viewer
  does not depend on in-browser XSLT — which browsers are removing in late 2026.
- **`checkit check`.** Structural checks on a built bank and its generators,
  including the ones that fail silently.
- **`<frozen/>`.** Mark an outcome whose seeds must not be regenerated, so a
  rebuild cannot change problems students are working through.
- **`variants`.** Pregenerate several versions of an axis (topic, difficulty,
  what the course has covered) across the seed space, and filter later.
- **`<glyphs>` and `<nobreak>`.** SpaTeXt elements for content whose screen and
  print forms genuinely differ.
- **50 browsable versions** per exercise, up from 20.

## Package development

Dependencies install automatically in a Codespace: click "Code" → "Codespaces" →
"Create codespace on main". Locally, run `.devcontainer/setup.sh`.

```
pip install -e dashboard          # editable, for platform work
python -m unittest discover -s dashboard/tests -t dashboard/tests
python build_docs.py              # rebuild the demo site in docs/
```

> Under an editable install, `pip show checkit-dashboard` reports whatever
> version was current when you installed and never updates. To see what is
> actually running:
> `python -c "import checkit; print(checkit.__file__, checkit.VERSION)"`.

Releases are GitHub release assets, not PyPI uploads — see "Cutting a release"
in `CODEBASE_NOTES.md`. If you change anything under `viewer/src/`, run
`dashboard/update_viewer.py` first: `viewer.zip` is a gitignored build artifact
and a stale one ships silently.

## Differences from upstream

Recorded in full under "Local divergences" in `CODEBASE_NOTES.md`, so an
upstream merge does not silently revert them. The version is `0.2.8.N` rather
than `0.2.8` so `pip show` can tell you which one you have.

Homepage for the upstream project: [checkit.clontz.org](https://checkit.clontz.org).

## License

See [LICENSE](LICENSE).
