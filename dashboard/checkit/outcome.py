from .exercise import Exercise
import os, json, random
from html import escape as escape_html
import pystache
from . import (PUBLIC_SEEDS, BUNDLE_UNTIL, INLINE_FORMATS, BUNDLE_FORMATS,
               BUNDLE_FILENAME)
from .utils import atomic_write
from .wrapper import run_generator
from .wrapper.tikz import compile_tikz_for_outcome
import re

#: An <image> or <tikz-image> in template or data text, before rendering.
_IMAGE_TAG = re.compile(r"<\s*(image|tikz-image)\b")
_XML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strings_in(value):
    """Every string in a generator's data, however deeply nested."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings_in(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings_in(v)


class Outcome():
    def __init__(self, title=None, slug=None, path=None, description=None, bank=None, ai_prompt=None, frozen=False):
        self.title = title
        self.slug = slug
        self.relpath = path
        self.description = description
        self.bank = bank
        # None means "inherit the bank's ai_prompt"; see Bank.__init__
        self.ai_prompt = ai_prompt
        # <frozen/> in bank.xml: students are working through these versions
        # right now, so the seeds must not move under them. Blocks regeneration
        # only -- see Bank.generate_exercises.
        self.frozen = frozen
    
    def abspath(self):
        return os.path.join(self.bank.abspath(),self.relpath)
    
    def full_title(self,max_length=None):
        ft = f"{self.slug}: {self.title}"
        if (max_length is not None) and (len(ft)>max_length):
            return ft[:max_length]+"…"
        else:
            return ft

    def template_filepath(self):
        return os.path.join(
            self.abspath(),
            "template.xml"
        )
    
    def template(self):
        # UTF-8, never the locale's. Read in cp1252 here, so the text the
        # viewer renders a student's page from was published garbled --
        # an em dash as three characters -- while the precomputed HTML,
        # which pystache reads as UTF-8, was right (RV-6, 2026-11-16).
        with open(self.template_filepath(), encoding="utf-8") as f:
            return f.read()

    def parsed_template(self):
        """`template.xml`, read and parsed by pystache once per edit.

        Every exercise used to read and parse the file again -- a thousand
        times per outcome per format. Keyed by the file's modification time
        and size, so editing the template between two renders in one
        process is still seen.
        """
        stat = os.stat(self.template_filepath())
        key = (stat.st_mtime_ns, stat.st_size)
        cached = getattr(self, "_parsed_template", None)
        if cached is None or cached[0] != key:
            cached = self._parsed_template = (key, pystache.parse(self.template()))
        return cached[1]

    # Preference order when an outcome directory holds more than one. The
    # extension is what selects the runtime -- see wrapper/__init__.py RUNTIMES.
    GENERATOR_FILENAMES = ("generator.py", "generator.sage")

    def generator_path(self):
        for filename in self.GENERATOR_FILENAMES:
            path = os.path.join(self.abspath(), filename)
            if os.path.isfile(path):
                return path
        # None present. Return the preferred name so the FileNotFoundError
        # raised downstream names a real, expected location.
        return os.path.join(self.abspath(), self.GENERATOR_FILENAMES[0])

    def to_dict(self,regenerate=False,remote=None,precompute=True):
        self.generate_exercises(regenerate)
        exs = self.exercises()
        exercises = []
        for e in exs:
            d = e.to_dict()
            # Only the public seeds are inlined; the rest live in the bundle, so
            # bank.json does not grow by a factor of ten for data no student
            # will ever request.
            if precompute and e.seed < PUBLIC_SEEDS:
                d.update(e.derived(remote=remote, formats=INLINE_FORMATS))
            # A print-only version keeps its seed and loses its data.
            #
            # Nothing published can render one: the inlined formats stop at
            # PUBLIC_SEEDS and the bundle stops at BUNDLE_UNTIL. The raw data
            # was shipped anyway, and it carries the answers -- so a student
            # who read the version number off a printed footer could look it
            # up. The entry itself stays, because the viewer indexes
            # `exercises[seed]` by position.
            if e.seed >= BUNDLE_UNTIL:
                d.pop("data", None)
            exercises.append(d)
        return {
            "title": self.title,
            "slug": self.slug,
            "description": self.description,
            "ai_prompt": self.ai_prompt,
            "template": self.template(),
            "exercises": exercises,
        }

    def has_images(self):
        """Whether this outcome's exercises reference images at all.

        Used to decide whether a missing `remote` is fatal: a bank with no
        figures can precompute HTML perfectly well without one.
        """
        exs = self.exercises()
        if not exs:
            return False
        # Every version, not the first. Rendering seed 0 alone missed a figure
        # that only some versions draw, so the build went ahead without
        # --remote and those versions published dead links (2026-11-17).
        #
        # Read from the template and the data, without rendering: this runs
        # as a preflight, before minutes of rendering, and rendering every
        # seed here would be most of those minutes. A figure can only come
        # from one of the two -- written in the template, or pasted in by a
        # {{{triple brace}}}. A tag inside an XML comment is not counted (the
        # comment is stripped before rendering), but one inside a section no
        # version enables is: such a template asks for --remote, which costs
        # a flag and is the safe side to be wrong on.
        if _IMAGE_TAG.search(_XML_COMMENT.sub("", self.template())):
            return True
        return any(_IMAGE_TAG.search(text)
                   for e in exs for text in _strings_in(e.data))

    def write_derived_bundle(self,remote=None):
        """The non-public seeds, pre-rendered, as one file per outcome.

        Fetched only when an instructor builds an assessment or exports to an
        LMS. About 1.4 MB raw per outcome for a 1000-seed bank, which is ~51 KB
        over the wire -- this content compresses roughly 28x.
        """
        exs = [
            e for e in self.exercises()
            if PUBLIC_SEEDS <= e.seed < BUNDLE_UNTIL
        ]
        payload = {
            "slug": self.slug,
            "first_seed": PUBLIC_SEEDS,
            "last_seed": BUNDLE_UNTIL - 1,
            "formats": list(BUNDLE_FORMATS),
            "seeds": {
                str(e.seed): e.derived(remote=remote, formats=BUNDLE_FORMATS)
                for e in exs
            },
        }
        path = os.path.join(self.build_path(), BUNDLE_FILENAME)
        atomic_write(path, json.dumps(payload))      # RV-10
        return path

    def preview_exercises(self):
        preview_json = os.path.join(self.build_path(),"preview.json")
        run_generator(self,preview_json,preview=True,images=True)
        # preview mode generates PUBLIC_SEEDS seeds (see run_generator's
        # amount_s), so cap compilation to match -- otherwise a preview taken
        # after a full build would recompile every seed in the outcome.
        compile_tikz_for_outcome(self,image_seeds=PUBLIC_SEEDS)
        with open(preview_json, encoding="utf-8") as f:
            data = json.load(f)['seeds']
        return [Exercise(d["data"],d["seed"],self) for d in data]

    def html_preview(self,pregenerated=False):
        if pregenerated:
            exs = random.sample(self.exercises(),1)
        else:
            exs = self.preview_exercises()
        html = "<h2>Preview:</h2>\n"
        for ex in exs:
            # remote='' keeps this preview's root-relative <img src> values,
            # which is what it has always produced. An absolute URL would point
            # at the published site rather than the bank being previewed.
            html += ex.html(remote='')
            html += "\n"
            html += "<h3>Data</h3>"
            html += "<pre>\n"
            html += escape_html(json.dumps(ex.to_dict(),indent=4))
            html += "</pre>\n"
            html += "\n"
            html += "<h3>SpaTeXt</h3>"
            html += "<pre>\n"
            html += escape_html(ex.spatext())
            html += "</pre>\n"
            html += "\n"
            html += "<h3>HTML</h3>"
            html += "<pre>\n"
            html += escape_html(ex.html(remote=''))
            html += "</pre>\n"
            html += "<h3>LaTeX</h3>"
            html += "<pre>\n"
            html += escape_html(ex.latex())
            html += "</pre>\n"
            html += "<h3>PreTeXt</h3>"
            html += "<pre>\n"
            html += escape_html(ex.pretext())
            html += "</pre>\n"
        return html

    def build_path(self):
        p = os.path.join(self.bank.build_path(),self.slug,"generated")
        os.makedirs(p, exist_ok=True)
        return p
    
    def seeds_json_path(self):
        return os.path.join(self.build_path(),"seeds.json")

    def generate_exercises(self,regenerate=False,images=False,amount=1_000,image_seeds=None,
                           thawed=False):
        # <frozen/> is enforced here, on the outcome, so that every way in
        # respects it. It lived only in Bank.generate_exercises, and two
        # other paths regenerated a frozen outcome without a word: the
        # deprecated Jupyter panel, which calls this directly, and
        # write_json(regenerate=True), through to_dict (RV-14, 2026-11-16).
        # `thawed` is how `--thaw SLUG` gets past it -- naming the outcome
        # is deliberately the only way.
        if regenerate and getattr(self, "frozen", False) and not thawed:
            print(
                f"SKIPPING {self.slug}: marked <frozen/> in bank.xml. "
                f"Its existing seeds are kept. To regenerate it anyway: "
                f"--thaw {self.slug}"
            )
            regenerate = False
        if not regenerate:
            try:
                self.load_exercises()
            except RuntimeError:
                pass # generation is necessary
            else:
                # The seeds are already here, so nothing needs generating --
                # but the images might still be missing, and returning now
                # ignored --images entirely. Asking for figures and silently
                # getting none is how a bank ends up published with images for
                # the first handful of versions and nothing after.
                #
                # The .tikz files were written during generation, so they can
                # be rasterized without regenerating anything; figures whose
                # PNG is already current are skipped, making this cheap when
                # there is nothing to do.
                if images:
                    compile_tikz_for_outcome(self,image_seeds=image_seeds)
                return
        run_generator(self,self.seeds_json_path(),preview=False,images=images,amount=amount,image_seeds=image_seeds)
        if images:
            compile_tikz_for_outcome(self,image_seeds=image_seeds)
        self.load_exercises(reload=True)


    def load_exercises(self,reload=False,strict=True):
        if not reload:
            try:
                self._exercises
                return            # already loaded and not a forced reload, so skip the file read (originally a bug?)
            except AttributeError:
                pass # load is necessary
        try:
            with open(self.seeds_json_path(), encoding="utf-8") as f:
                data = json.load(f)
            seed_list = data['seeds']
            self._exercises = [Exercise(d["data"],d["seed"],self) for d in seed_list]
            self._generated_on = data['generated_on']
        except FileNotFoundError as e:
            if strict:
                raise RuntimeError("Exercises must be generated before being loaded in strict mode.") from e
    
    def generated_on(self):
        try:
            return self._generated_on
        except AttributeError as e:
            return "(never generated)"
    
    def exercises(self,all=True,amount=300,randomized=False):
        try:
            exs = self._exercises
            if all:
                return exs
            if randomized:
                indices = sorted(random.sample(range(len(exs)),amount))
            else:
                indices = range(amount)
            return [exs[i] for i in indices]
        except AttributeError as e:
            raise RuntimeError("Exercises must be generated/loaded before being requested.") from e
