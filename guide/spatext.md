# SpaTeXt reference

`template.xml` is written in SpaTeXt: a small XML vocabulary that says what an
exercise *means*, which three stylesheets then render as HTML, LaTeX and
PreTeXt. You write the exercise once.

Namespace: `https://spatext.clontz.org`.

```xml
<?xml version='1.0' encoding='UTF-8'?>
<knowl mode="exercise" xmlns="https://spatext.clontz.org" version="0.3">
    <intro>
        <p>Determine whether each statement is true.</p>
    </intro>
    <knowl>
        <content><p><m>{{a}}</m> divides <m>{{b}}</m>.</p></content>
        <outtro><p>{{answer}}</p></outtro>
    </knowl>
</knowl>
```

---

## Structure

| element | meaning |
|---|---|
| `<knowl mode="exercise">` | the root. `mode="exercise"` marks it as an exercise for PreTeXt output |
| `<title>` | optional heading |
| `<intro>` | shown before the question(s) |
| `<content>` | the question |
| `<outtro>` | the answer — hidden until the student asks |
| nested `<knowl>` | multi-part exercises. A knowl with child knowls uses them as parts and ignores its own `<content>` |
| `<list>` / `<item>` | an unordered list |

Nesting is how you get numbered tasks. The outer knowl's `<intro>` becomes the
shared instruction; each child knowl becomes one numbered part with its own
answer.

---

## Inline elements

| element | HTML | LaTeX |
|---|---|---|
| `<p>` | `<p>` | a paragraph |
| `<m>` | `\( … \)`, rendered by KaTeX | `\( … \)` |
| `<m mode="display">`, `<me>` | display maths | `\[ … \]` |
| `<em>` | `<em>` | `\textbf{…}` |
| `<c>` | `<code>` | `\texttt{…}` |
| `<q>` | `"…"` | ` ``…'' ` |
| `<url href="…">` | `<a>` | `\href` / `\url` |
| `<image source="…" description="…">` | `<img>` | `\includegraphics` |
| `<tikz-image source="…">` | `<img>` at `source.png` | `\input{source.tikz}` |

`<m>` content is raw LaTeX. It is **not** escaped, and it must not contain other
elements — see the trap below.

---

## Per-medium elements

Two elements exist for content whose screen and print forms genuinely differ.

### `<glyphs font="…" latex="…">`

Characters that have no single form working in both media.

```xml
<glyphs font="egyptian" latex="\Hone\Hten">&#x13000;&#x13001;</glyphs>
```

Screen gets the Unicode characters in a sized span; print gets the `latex`
attribute, or a font command chosen by `@font`. An unknown font falls through
to plain text rather than emitting an undefined macro that would fail the whole
document.

Holds **characters, not markup**.

### `<nobreak>`

Content that must not be broken across lines.

```xml
<p><nobreak><m>k + (j + u) =</m></nobreak> <nobreak><m>k + j + u</m></nobreak></p>
```

HTML gets `white-space: nowrap`; LaTeX gets `\mbox{…}`. Use two of them, as
above, when a break *between* the sides is fine but a break inside either is
not.

Unlike everything else here, `<nobreak>` **wraps other elements**.

### Where the line is

An element belongs in SpaTeXt if it asserts something about *meaning* that each
medium honours differently — "these characters are Egyptian", "these belong
together". It does not if it asserts something about *appearance*: there is no
`<pagebreak>` or `<vspace>`, deliberately, because there is no reading of those
that is about the mathematics.

---

## Substituting generator data

Templates are Mustache. **The number of braces matters.**

| | |
|---|---|
| `{{value}}` | escaped — safe for text, turns markup into visible `&lt;m&gt;` |
| `{{{value}}}` | raw — required when the generator emits markup |
| `{{__seed__}}` | this version's seed, zero-padded (`0007`) — used in figure paths |
| `{{__variant__}}` | this version's variant label, if the generator declares `variants` |
| `{{#key}}…{{/key}}` | section: rendered only when `key` is truthy |

A section tag inside an XML comment is a working idiom — the comment keeps the
XML valid while Mustache still sees the tag:

```xml
<!-- {{#has_figure}} -->
<p><image source="…{{__seed__}}/fig.png" description="{{caption}}"/></p>
<!-- {{/has_figure}} -->
```

---

## Traps

These have all cost real time. `checkit check` catches every one of them.

### A field the generator never sets renders as nothing

Mustache substitutes an absent key with the empty string. The sentence around it
survives and the value vanishes:

> "Which model best explains the &nbsp; to an elementary student?"

Nothing fails; the build is clean; the exercise is unanswerable. `checkit check`
compares each template's keys against the data its generator produces.

### `<m>` swallows any element inside it

Both `html.xsl` and `latex.xsl` render `<m>` with `normalize-space(text())`,
which reads **direct text children only**. Any element inside is silently
discarded and the surrounding prose survives, typeset as mathematics:

```xml
<!-- generator emits: <m>12</m> is a multiple of <m>4</m> -->
<p><m>{{{statement}}}</m></p>     <!-- WRONG -->
```

renders as the words "is a multiple of" in italics, **with both numbers gone**.

If a generator emits markup, the template must not wrap it:

```xml
<p>{{{statement}}}</p>            <!-- right -->
```

This is the one to watch when converting a generator from emitting plain TeX to
emitting `<m>` elements — the wrapper that was correct yesterday is now
destructive.

### Bare TeX in a text field renders literally

A field holding `\dfrac{5}{7}` or `\text{VIII}`, injected outside a maths
context, shows the backslashes. Either wrap the slot — `<m>{{value}}</m>` — or
have the generator emit `<m>` markup and use triple braces. Which one depends on
whether that slot ever receives markup: if it does, the wrapper will swallow it.

Single-character escapes count too: `\%` and `\$` reach the page as
backslashes just as `\text` does.

### Non-raw Python strings eat LaTeX commands

```python
"\Large\textpmhg{...}"     # \t is a TAB. Output: \Large<TAB>extpmhg{...}
r"\Large\textpmhg{...}"    # right
```

`\L` is an invalid escape and warns; `\t` is a valid one and does not. Use raw
strings for anything holding LaTeX.

---

## Adding an element

Four files, and three of them fail silently:

1. `dashboard/checkit/static/html.xsl` — the rule, **and** naming it in the
   `parseDisplay` select
2. `latex.xsl` — likewise
3. `pretext.xsl` — likewise
4. `viewer/src/spatext/NodeList/ParagraphNodes.svelte` — the viewer builds DOM
   from SpaTeXt directly and never sees the XSLT

`apply-templates` with an explicit `select` processes only what is listed, so a
rule that is never selected renders **nothing**, in every format, without an
error. `dashboard/tests/test_subset.py` asserts both halves for `<glyphs>` and
`<nobreak>`; copy that pattern.

Then rebuild `viewer.zip` with `dashboard/update_viewer.py`, and cut a release —
a bank using a new element needs a platform that knows it, because the
"kill undefined elements" rule drops an unknown element *and its contents*.
