"""Run every generator in-process, to get at the traceback.

`checkit generate` runs each generator in a subprocess and lets
`subprocess.CalledProcessError` propagate, so a failing generator reports the
argv and an exit status and nothing else. The child's actual exception and its
line number are lost, which turns a one-line naming bug into a guessing game.

This exec's each generator in the same namespace the wrapper builds and calls
`data()` directly, so the real exception surfaces. It checks every generator in
seconds and needs no build, which makes it the cheapest thing to run after
editing one.

It is a smoke test, not a correctness test: it proves a generator *runs*, not
that what it produces is right.
"""

import pathlib
import random
import sys
import traceback

from .wrapper.wrapper import GENERATOR_NAMESPACE

# Seeds either side of both boundaries: the public range the viewer shows, the
# bundle range assessments draw from, and one above it.
DEFAULT_SEEDS = (0, 1, 7, 49, 50, 399, 400)


#: Yielded in place of a traceback for a generator this cannot run: a Sage
#: one, which needs the `sage` interpreter, not this process.
NOT_RUN = "not run: a generator.sage needs Sage; `checkit generate -o` runs it"


def run_generators(bank_path=".", only=None, seeds=DEFAULT_SEEDS):
    """Yield (slug, traceback_or_None) for each outcome the bank declares.

    `only` is a set of slugs, or None for all of them. A Sage generator
    yields `NOT_RUN` instead of a traceback.

    Every outcome in bank.xml, where bank.xml says it is. This used to glob
    `outcomes/*/generator.py` and take the folder name as the slug, so a
    generator one folder deeper -- seven of the demo bank's eleven -- was
    never run at all (RV-14, 2026-11-16).

    Each seed is run the way the wrapper runs it -- `roll_data`, then the
    data made JSON-ready, then `tikz_graphics` -- because a generator can
    fail at either later step, and calling `data()` alone never saw it.
    """
    from .bank import Bank
    from .wrapper.wrapper import json_ready

    root = pathlib.Path(bank_path).resolve()
    for outcome in Bank(str(root)).outcomes():
        slug = outcome.slug
        if only is not None and slug not in only:
            continue
        path = pathlib.Path(outcome.generator_path())
        if path.suffix == ".sage":
            yield slug, NOT_RUN
            continue
        namespace = dict(GENERATOR_NAMESPACE)
        # The generator's own folder and the bank root, *appended*, which is
        # what load_generator does and explains: prepending lets a bank file
        # shadow the standard library. This used to insert at 0 while its
        # comment said it matched.
        added = [p for p in (str(path.parent), str(root)) if p not in sys.path]
        sys.path.extend(added)
        try:
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
            generator_class = namespace["Generator"]
            # Construct it properly: BaseGenerator.__init__ sets `variant`, and
            # stubbing around it produces false AttributeError failures on any
            # outcome that declares `variants`.
            labels = list(generator_class.variants) if generator_class.variants else [None]
            for seed in seeds:
                for label in labels:
                    generator = generator_class()
                    generator.roll_data(seed=seed, variant=label)
                    json_ready(generator.get_data())
                    generator.tikz_graphics()
            yield slug, None
        except Exception:
            yield slug, traceback.format_exc()
        finally:
            for p in added:
                sys.path.remove(p)
