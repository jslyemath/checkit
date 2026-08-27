import click
from trogon import tui
import os
from . import static, VERSION, bank, PUBLIC_SEEDS

@tui()
@click.group(
    short_help="CheckIt command line interface",)
def main():
    pass

# checkit new
@main.command(
    short_help="Generates boilerplate for using the CheckIt Dashboard to author a new bank.",
)
@click.argument('directory', default='new-checkit-bank')
def new(directory):
    """
    Generates boilerplate for using the CheckIt Dashboard
    to author a new bank.
    """
    # create directories
    try:
        os.makedirs(directory)
    except FileExistsError:
        print(f"Warning: directory `{directory}` already exists")
    # copy sample outcome template/generator
    example_outcome_dir = os.path.join(directory,'outcomes','EX1')
    os.makedirs(example_outcome_dir, exist_ok=True)
    for filename in ["template.xml","generator.py"]:
        with open(os.path.join(example_outcome_dir,filename),"w") as f:
            f.write(static.read_resource(filename))
    # copy devcontainer stuff
    devcontainer_dir = os.path.join(directory, ".devcontainer")
    os.makedirs(devcontainer_dir, exist_ok=True)
    for filename in ["setup.sh","devcontainer.json"]:
        with open(os.path.join(devcontainer_dir,filename),"w") as f:
            f.write(static.read_resource(filename))
    # copy bank manifest, README, and the shared-helpers module every generator
    # in the bank can import (see bank_helpers.py's own docstring)
    for filename in ["bank.xml","README.md","bank_helpers.py"]:
        with open(os.path.join(directory,filename),"w") as f:
            f.write(static.read_resource(filename))
    # copy gitignore
    with open(os.path.join(directory,".gitignore"),"w") as f:
        f.write(static.read_resource("gitignore.txt"))
    # generate requirements.txt
    #
    # Deliberately NOT `checkit-dashboard == {VERSION}`. That would resolve on
    # PyPI, where checkit-dashboard is Steven Clontz's upstream package -- so a
    # bank made with this fork would silently install different code that merely
    # shares a version number. Point at the fork's own release wheel instead.
    #
    # A wheel is used rather than a git URL because viewer.zip, the compiled
    # browser app, is a build artifact that is not committed: pip installing
    # from git would produce a package with no viewer in it.
    wheel = f"checkit_dashboard-{VERSION}-py3-none-any.whl"
    release_url = (
        "https://github.com/jslyemath/checkit/releases/download/"
        f"v{VERSION}/{wheel}"
    )
    with open(os.path.join(directory,"requirements.txt"),"w") as f:
        f.write(
            "# The CheckIt platform, from the jslyemath fork.\n"
            "#\n"
            "# Not `checkit-dashboard == <version>`: that name on PyPI is the\n"
            "# upstream project, which is different code.\n"
            "#\n"
            "# Working on the platform itself? Install it editable instead, so\n"
            "# your edits take effect without rebuilding a wheel:\n"
            "#     pip install -e /path/to/checkit/dashboard\n"
            f"checkit-dashboard @ {release_url}\n"
        )
    print(f"Successfully created new CheckIt bank in `{directory}`")


# checkit generate
@main.command(
    short_help="generate bank json",
)
@click.option(
    "-a",
    "--amount",
    default=1_000,
    help="Amount of exercises to generate.",
)
@click.option(
    "-r",
    "--regenerate",
    is_flag=True,
    help="Force regeneration of previously generated seeds.",
)
@click.option(
    "-i",
    "--images",
    is_flag=True,
    help="Rasterize images to PNG. (TikZ .tikz source is written either way.)",
)
@click.option(
    "--image-seeds",
    default=None,
    type=int,
    help="Rasterize images for only the first N seeds (default: all). "
         "Applies to PNGs only -- TikZ .tikz source is written for every seed, "
         "so LaTeX/print output is unaffected by this cap. "
         f"The HTML viewer shows {PUBLIC_SEEDS} seeds and LMS export uses seeds "
         "100-999, "
         "so a low value produces broken images for those endusers.",
)
@click.option(
    "-o",
    "--outcome",
    default="ALL",
    help="Outcome to generate. \"ALL\" generates all outcomes",
)
@click.option(
    "--remote",
    default=None,
    help="Absolute URL of the directory containing assets/, e.g. "
         "https://example.org/my-bank . Used to build <img src> in precomputed "
         "HTML. Required when the bank has images, because a root-relative src "
         "would 404 wherever the HTML is displayed (an LMS, a chatbot).",
)
@click.option(
    "--no-precompute",
    is_flag=True,
    help="Skip precomputing HTML/LaTeX/PreTeXt. Faster, but the viewer needs "
         "them once browsers drop XSLT (Chrome 158, 2026-11-17).",
)
def generate(amount,regenerate,images,image_seeds,outcome,remote,no_precompute):
    if amount < PUBLIC_SEEDS:
        # The viewer's version picker always offers PUBLIC_SEEDS versions, and
        # the assessment builder draws from seeds at or above it -- with fewer
        # than that generated, the picker offers versions that do not exist and
        # `Math.random() * (exercises.length - PUBLIC_SEEDS)` goes negative.
        # Neither fails loudly in the browser, so refuse here instead.
        raise click.BadParameter(
            f"--amount must be at least PUBLIC_SEEDS ({PUBLIC_SEEDS}), not {amount}. "
            f"The viewer exposes {PUBLIC_SEEDS} versions of every exercise, so a "
            "smaller bank leaves the version picker pointing at seeds that were "
            "never generated. Use 1000 for a real build.",
            param_hint="--amount",
        )
    b = bank.Bank()
    only = None
    if outcome != "ALL":
        # Resolve to slugs and hand them to generate_exercises, rather than
        # narrowing the Bank. write_json() serialises every outcome the Bank
        # holds, so a narrowed Bank writes a bank.json missing the others --
        # and skips the missing-`remote` preflight for them too.
        only = {o.slug for o in b.outcomes() if o.slug.lower() == outcome.lower()}
        if not only:
            # Silently regenerating nothing on a typo'd slug looks exactly like
            # a successful run.
            raise click.BadParameter(
                f"no outcome with slug {outcome!r} in this bank. "
                "Available: " + ", ".join(o.slug for o in b.outcomes()),
                param_hint="--outcome",
            )
    b.generate_exercises(regenerate=regenerate,images=images,amount=amount,
                         image_seeds=image_seeds,only=only)
    b.write_json(remote=remote,precompute=not no_precompute)

# checkit viewer
@main.command(
    short_help="generate bank viewer",
)
def viewer():
    bank.Bank().build_viewer()


if __name__ == "__main__":
    main()
