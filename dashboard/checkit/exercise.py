from lxml import etree
from latex2mathml.converter import convert
import pystache
from .static import read_resource

STX_NS = "{https://spatext.clontz.org}"
IMAGE_TAGS = (STX_NS + "image", STX_NS + "tikz-image")

# Consumers that cannot run JavaScript and therefore need MathML rather than
# LaTeX delimiters. Mirrors the viewer's `mathMode` argument in utils/index.ts.
MATHML_CONSUMERS = ("canvas", "brightspace")


def tex_to_mathml(tex, display="inline"):
    """One LaTeX string as a MathML element, ready to splice into a tree."""
    return etree.fromstring(convert(tex, display=display))


def _has_images(spatext_ele):
    return any(
        True
        for tag in IMAGE_TAGS
        for _ in spatext_ele.iter(tag)
    )


def _mathml_in_place(ele):
    r"""Replace every math span's contents with MathML.

    The viewer does this after its transform, with KaTeX:

        ele.querySelectorAll('[class~="math"][data-latex]').forEach((math)=>{
            katex.render(math.getAttribute("data-latex"), math,
                         {output:'mathml', displayMode: ...})
        })

    Same shape here, using latex2mathml. Tested against every LaTeX string the
    mat-106 and mat-206 banks emit (805 distinct): no failures, and the only
    divergences from KaTeX are two glyph choices -- U+25FB vs U+25A1 for \Box,
    U+2015 vs U+203E for \overline. Structure (mfrac/mover/msup/msub/mtable)
    matches, including the columnlines attribute that carries an augmented
    matrix's vertical rule.

    One deliberate difference: KaTeX wraps its output in <span class="katex">.
    That is a styling hook for KaTeX's own stylesheet, which is not present in
    an exported quiz, and emitting a class named after a library we do not use
    would mislead the next reader. The <math> element is attached directly.
    """
    targets = [
        el for el in ele.iter()
        if "math" in (el.get("class") or "").split()
        and el.get("data-latex") is not None
    ]
    for el in targets:
        classes = (el.get("class") or "").split()
        display = "block" if "display-math" in classes else "inline"
        mathml = tex_to_mathml(el.get("data-latex"), display=display)
        el.text = None
        for child in list(el):
            el.remove(child)
        el.append(mathml)
    return ele

class Exercise:
    def __init__(self, data=None, seed=None, outcome=None):
        self.data = data
        self.seed = seed
        self.outcome = outcome

    def spatext_ele(self, remote=None):
        """The exercise as SpaTeXt.

        `remote` is stamped onto every <image> and <tikz-image> as the base URL
        that html.xsl prepends to @source. The viewer does the same thing from
        location.href; here it must be supplied, because a build has no page to
        read it from. Passing None leaves the attribute unset, which yields
        root-relative <img src> values.
        """
        renderer = pystache.Renderer()
        xml_string = renderer.render_path(self.outcome.template_filepath(),self.data)
        try:
            ele = etree.fromstring(bytes(xml_string, encoding='utf-8'))
        except etree.XMLSyntaxError as e:
            lined_xml = "\n".join([f"{i+1:04d}: {l}" for i,l in enumerate(xml_string.split("\n"))])
            e_text = str(e)+"\n"+lined_xml
            raise Exception(e_text) from e
        # remove comments
        etree.strip_tags(ele,etree.Comment)
        if remote is not None:
            base = remote.rstrip("/")
            for tag in IMAGE_TAGS:
                for image in ele.iter(tag):
                    image.set("remote", base)
        return ele

    def spatext(self):
        return str(
            etree.tostring(self.spatext_ele(), pretty_print=True), 
            encoding="UTF-8"
        )

    SUBSETS = ("all", "statement", "answer")

    CONSUMERS = ("basic",) + MATHML_CONSUMERS

    def html_ele(self,subset='all',consumer='basic',remote=None):
        """This exercise as an HTML element tree.

        `consumer` selects how mathematics is represented: 'basic' leaves LaTeX
        in \\( \\) delimiters, while 'canvas' and 'brightspace' convert it to
        MathML, since an LMS renders imported HTML without CheckIt's JavaScript.

        `remote` is the absolute base URL for images. It is required rather than
        defaulted, because guessing it wrong produces dead <img> links that
        nothing detects until a student sees them.
        """
        if subset not in self.SUBSETS:
            raise ValueError(
                f"subset must be one of {self.SUBSETS}, not {subset!r}"
            )
        if consumer not in self.CONSUMERS:
            raise ValueError(
                f"consumer must be one of {self.CONSUMERS}, not {consumer!r}"
            )
        src = self.spatext_ele(remote=remote)
        if remote is None and _has_images(src):
            raise ValueError(
                "This exercise contains images, so its HTML needs an absolute "
                "base URL, but remote= was not given. Pass the URL of the "
                "directory that contains assets/, e.g. "
                "remote='https://checkit.clontz.org/demo'. Without it every "
                "<img src> is root-relative and resolves against whatever host "
                "displays the HTML -- an LMS or a chatbot -- where it will 404. "
                "bank.xml's <url> is deliberately not used as a default: it "
                "names the bank's home page, which need not be where assets/ "
                "lives (the demo bank declares https://checkit.clontz.org but "
                "publishes under /demo/). Pass remote='' to keep the old "
                "root-relative behaviour."
            )
        transform = etree.XSLT(etree.fromstring(read_resource("html.xsl")))
        ele = transform(
            src,
            subset=f"'{subset}'",
            ).getroot()
        if consumer in MATHML_CONSUMERS:
            _mathml_in_place(ele)
        return ele

    def html(self,subset='all',consumer='basic',remote=None):
        return str(etree.tostring(self.html_ele(
            subset=subset,
            consumer=consumer,
            remote=remote,
            ),pretty_print=True), 'utf-8')

    def pretext_ele(self,subset='all',consumer='basic'):
        # pretext.xsl implements neither parameter, and nothing asks it to: the
        # viewer's outcomeToPtx() takes no subset either. Rather than keep
        # accepting values that are silently discarded, refuse them. Dropping
        # <statement> from a PreTeXt <exercise> would also emit structurally
        # invalid PreTeXt, so this is not merely unimplemented -- it needs
        # designing before it is built, and has no consumer to design against.
        if subset != 'all':
            raise NotImplementedError(
                f"pretext output does not support subset={subset!r}, only 'all'. "
                "Subset filtering is implemented in html.xsl only."
            )
        if consumer != 'basic':
            raise NotImplementedError(
                f"pretext output does not support consumer={consumer!r}, only 'basic'."
            )
        transform = etree.XSLT(etree.fromstring(read_resource("pretext.xsl")))
        ele = transform(self.spatext_ele()).getroot()
        return ele

    def pretext(self,subset='all',consumer='basic'):
        return str(etree.tostring(self.pretext_ele(
            subset=subset,
            consumer=consumer
            ),pretty_print=True), 'utf-8')

    def latex(self):
        transform = etree.XSLT(etree.fromstring(read_resource("latex.xsl")))
        return str(transform(self.spatext_ele()))

    def to_dict(self):
        return {
            "seed": self.seed,
            "data": self.data,
        }
