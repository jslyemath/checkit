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


def run_generators(bank_path=".", only=None, seeds=DEFAULT_SEEDS):
    """Yield (slug, traceback_or_None) for each generator found.

    `only` is a set of slugs, or None for all of them.
    """
    root = pathlib.Path(bank_path)
    for path in sorted(root.glob("outcomes/*/generator.py")):
        slug = path.parent.name
        if only is not None and slug not in only:
            continue
        namespace = dict(GENERATOR_NAMESPACE)
        # The bank root and the generator's own folder, matching load_generator.
        sys.path.insert(0, str(path.parent))
        sys.path.insert(0, str(root.resolve()))
        try:
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
            generator_class = namespace["Generator"]
            # Construct it properly: BaseGenerator.__init__ sets `variant`, and
            # stubbing around it produces false AttributeError failures on any
            # outcome that declares `variants`.
            labels = list(generator_class.variants) if generator_class.variants else [None]
            for seed in seeds:
                for label in labels:
                    random.seed(seed)
                    generator = generator_class()
                    generator.seed = seed
                    generator.variant = label
                    generator.data()
            yield slug, None
        except Exception:
            yield slug, traceback.format_exc()
        finally:
            sys.path.pop(0)
            sys.path.pop(0)
