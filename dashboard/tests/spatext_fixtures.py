"""Hand-written SpaTeXt documents covering the structural cases that matter to
subset filtering.

Deliberately not taken from demo-bank: a bank's `assets/**/generated` is
gitignored, so a fresh clone has no seeds.json and any bank-backed test would
need a full `checkit generate` before it could run. These fixtures need nothing
but lxml, so the suite is runnable the moment the repo is cloned.

Shapes follow real templates (see demo-bank/outcomes/EX/EX1 and EX2): nested
knowls are *direct children* of the outer knowl, not wrapped in <content>.
"""

NS = 'xmlns="https://spatext.clontz.org" version="0.2"'

# intro + content + outtro, the ordinary single-part exercise (cf. EX2)
SIMPLE = f"""<knowl mode="exercise" {NS}>
    <intro><p>Differentiate the following.</p></intro>
    <content><p><m>f(x) = x^2</m></p></content>
    <outtro><p><m>f'(x) = 2x</m></p></outtro>
</knowl>"""

# nested knowls, each with its own answer, plus an outer intro and outtro.
# This is the case that breaks if the <ol> wrapper is guarded (cf. EX1).
TASKS = f"""<knowl mode="exercise" {NS}>
    <intro><p>Identify the <em>slope</em> of each line.</p></intro>
    <knowl>
        <content><p><m>y = 3x + 1</m></p></content>
        <outtro><p><m>3</m></p></outtro>
    </knowl>
    <knowl>
        <content><p><m>y = -5x</m></p></content>
        <outtro><p><m>-5</m></p></outtro>
    </knowl>
    <outtro><p>Both lines are linear.</p></outtro>
</knowl>"""

# a title, which must survive every subset -- the viewer never removes it
TITLED = f"""<knowl mode="exercise" {NS}>
    <title>Slopes</title>
    <intro><p>Read carefully.</p></intro>
    <content><p><m>y = 2x</m></p></content>
    <outtro><p><m>2</m></p></outtro>
</knowl>"""

# no outtro at all: subset='statement' must remove nothing and still be valid
NO_OUTTRO = f"""<knowl mode="exercise" {NS}>
    <content><p>State the definition of a limit.</p></content>
</knowl>"""

# no intro, and a list inside the content, to exercise stx:list under filtering
LIST_CONTENT = f"""<knowl mode="exercise" {NS}>
    <content>
        <list>
            <item><p>First <m>a</m></p></item>
            <item><p>Second <m>b</m></p></item>
        </list>
    </content>
    <outtro><p>Either order is fine.</p></outtro>
</knowl>"""

# inline and display mathematics, for the MathML consumer.
# Written as a raw string with %-substitution rather than an f-string: LaTeX is
# full of braces, and \frac{1}{3} inside an f-string would be read as a
# placeholder.
MATH = r"""<knowl mode="exercise" %s>
    <content>
        <p>Simplify <m>\frac{1}{3}</m> and then solve:</p>
        <p><m mode="display">x^2 + y^2 = z^2</m></p>
    </content>
    <outtro><p><me>a = b</me></p></outtro>
</knowl>""" % NS

# an image, whose src depends on the @remote base URL
IMAGE = f"""<knowl mode="exercise" {NS}>
    <content><p>What does this show? <image source="assets/IMG2/2.png" description="The digit two."/></p></content>
    <outtro><p>The digit two.</p></outtro>
</knowl>"""

# characters that need a different typeface per medium (W1's Egyptian numerals)
GLYPHS = f"""<knowl mode="exercise" {NS}>
    <content><p>Write <glyphs font="egyptian">&#x13000;&#x13001;</glyphs> in modern numerals.</p></content>
    <outtro><p>3,502</p></outtro>
</knowl>"""

# a run that must not break across lines, wrapping maths (W4's equations)
NOBREAK = f"""<knowl mode="exercise" {NS}>
    <content><p>State the property: <nobreak><m>k + (j + u + 0) =</m></nobreak> <nobreak><m>k + (j + u)</m></nobreak></p></content>
    <outtro><p>Identity (Addition)</p></outtro>
</knowl>"""

ALL = {
    "SIMPLE": SIMPLE,
    "TASKS": TASKS,
    "TITLED": TITLED,
    "NO_OUTTRO": NO_OUTTRO,
    "LIST_CONTENT": LIST_CONTENT,
    "MATH": MATH,
    "IMAGE": IMAGE,
    "GLYPHS": GLYPHS,
    "NOBREAK": NOBREAK,
}

# viewer `solutions` value -> (subset value, the classes utils/index.ts removes)
CASES = {
    "show": ("all", []),
    "hide": ("statement", ["stx-outtro"]),
    "only": ("answer", ["stx-intro", "stx-content"]),
}
