from lxml import etree
import os, json, datetime, zipfile, shutil
from pathlib import Path
from . import static
from .outcome import Outcome
from .xml import CHECKIT_NS, optional_text
from . import (PUBLIC_SEEDS, BUNDLE_UNTIL, INLINE_FORMATS, BUNDLE_FORMATS,
               BUNDLE_FILENAME)

class Bank():
    def __init__(self, path="."):
        # read manifest for bank
        self._abspath = os.path.abspath(path)
        xml = etree.parse(os.path.join(self.abspath(),"bank.xml")).getroot()
        if xml.get("version") != "0.2":
            raise Exception("ERROR: Bank configuration doesn't match CheckIt version 0.2")
        self.title = xml.find(f"{CHECKIT_NS}title").text
        self.slug = xml.find(f"{CHECKIT_NS}slug").text
        self.url = xml.find(f"{CHECKIT_NS}url").text
        # Optional prompt prepended to the viewer's "Copy for AI Chatbot"
        # payload. Bank-level default; an outcome may override it.
        self.ai_prompt = optional_text(xml, "ai-prompt")
        # create each outcome
        self._outcomes = [
            Outcome(
                ele.find(f"{CHECKIT_NS}title").text,
                ele.find(f"{CHECKIT_NS}slug").text,
                ele.find(f"{CHECKIT_NS}path").text,
                ele.find(f"{CHECKIT_NS}description").text,
                self,
                ai_prompt=optional_text(ele, "ai-prompt"),
            )
            for ele in xml.find(f"{CHECKIT_NS}outcomes").iter(f"{CHECKIT_NS}outcome")
        ]
        for o in self._outcomes:
            o.load_exercises(strict=False)
    
    def abspath(self):
        return self._abspath
    
    def outcomes(self):
        return self._outcomes
    
    def generate_exercises(self,regenerate=False,images=False,amount=1_000,image_seeds=None):
        for o in self.outcomes():
            print(f"Generating {amount} exercises for outcome {o.slug}")
            o.generate_exercises(regenerate=regenerate,images=images,amount=amount,image_seeds=image_seeds)

    def build_path(self):
        p = os.path.join(self.abspath(),"assets")
        os.makedirs(p, exist_ok=True)
        return p

    def to_dict(self,regenerate=False,remote=None,precompute=True):
        olist = [
            o.to_dict(regenerate=regenerate,remote=remote,precompute=precompute)
            for o in self.outcomes()
        ]
        d = {
            "title": self.title,
            "slug": self.slug,
            "url": self.url,
            "ai_prompt": self.ai_prompt,
            "generated_on": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "outcomes": olist,
        }
        if precompute:
            # Declared, not implied. A consumer can ask "was this seed/format
            # emitted?" and get an answer, instead of discovering a hole by
            # rendering nothing. An older bank simply has no such key, which is
            # how the viewer tells "not precomputed" from "precomputed and
            # missing".
            d["precomputed"] = {
                "inline_formats": list(INLINE_FORMATS),
                "inline_below": PUBLIC_SEEDS,
                "bundle_formats": list(BUNDLE_FORMATS),
                "bundle_from": PUBLIC_SEEDS,
                "bundle_until": BUNDLE_UNTIL,
                "bundle_path": "assets/{slug}/generated/" + BUNDLE_FILENAME,
            }
        return d

    def write_json(self,regenerate=False,remote=None,precompute=True):
        if precompute and remote is None:
            # Checked before any rendering so the failure is immediate rather
            # than arriving several minutes into a build.
            with_images = [o.slug for o in self.outcomes() if o.has_images()]
            if with_images:
                raise ValueError(
                    "Precomputing HTML needs an absolute base URL for images, "
                    f"and these outcomes have images: {', '.join(with_images)}. "
                    "Pass --remote with the URL of the directory containing "
                    "assets/, e.g. --remote https://jslyemath.github.io/checkit/demo . "
                    "Use --no-precompute to skip precomputation entirely."
                )
        build_path = os.path.join(self.build_path(),f"bank.json")
        with open(build_path,'w') as f:
            json.dump(self.to_dict(regenerate=regenerate,remote=remote,
                                   precompute=precompute),f)
        for o in self.outcomes():
            if precompute:
                o.write_derived_bundle(remote=remote)
            else:
                # Leaving a stale bundle beside a bank.json that says
                # "not precomputed" is a trap for anything that looks for the
                # file instead of reading the declaration.
                stale = os.path.join(o.build_path(), BUNDLE_FILENAME)
                if os.path.exists(stale):
                    os.remove(stale)

    def build_viewer(self):
        docs_path = Path(self.abspath()) / "docs"
        if docs_path.exists() and docs_path.is_dir():
            shutil.rmtree(docs_path)
        docs_path.mkdir()
        archive = zipfile.ZipFile(static.open_resource("viewer.zip"))
        archive.extractall(docs_path)
        # Copy the assets the site actually serves. seeds.json and .tikz are
        # build inputs: the viewer fetches only assets/bank.json and the
        # per-outcome bundles, and the print tool reads seeds.json from the
        # bank's own assets/ rather than from docs/. Publishing them duplicated
        # every exercise's data into the repo a second time -- 23 MB of a
        # 28-outcome bank, changing wholesale on every rebuild.
        shutil.copytree(
            self.build_path(),
            docs_path / "assets",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("seeds.json", "*.tikz"),
        )

    def generated_on(self):
        try:
            with open(os.path.join(self.build_path(),f"bank.json"),'r') as f:
                return json.load(f)["generated_on"]
        except:
            return "(never generated)"
