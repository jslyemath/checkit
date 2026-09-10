import os, shutil, subprocess, tempfile

PREAMBLE = r"""\documentclass[tikz,border=4pt]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
"""
# To use a custom preamble, place a tikz_preamble.tex file in the bank root directory.

# Max seconds any single figure may take to compile or convert. A normal figure
# takes 1-2s; this only trips on a genuinely stuck process (e.g. pdflatex caught
# at an interactive prompt despite nonstopmode, or a runaway computation).
COMPILE_TIMEOUT = 60

def compile_tikz_for_outcome(outcome, image_seeds=None):
    """Compile the outcome's generated .tikz files to PNG.

    wrapper.sage writes a .tikz for every seed, because the LaTeX output
    \\input{}s the source and print has to work for all of them. PNGs are only
    consumed by the HTML/viewer surfaces, so `image_seeds` mirrors the
    --image-seeds cap and rasterizes just the first N seeds.

    A figure whose PNG is already at least as new as its .tikz is skipped, so
    re-running generation (or taking a short preview after a 1000-seed build)
    doesn't recompile work that is already current.
    """
    generated = outcome.build_path()  # assets/<slug>/generated/
    preamble = _load_preamble(outcome.bank.abspath())
    compiled = 0
    skipped = 0
    for entry in sorted(os.listdir(generated)):
        seed_dir = os.path.join(generated, entry)
        if not os.path.isdir(seed_dir):
            continue
        if image_seeds is not None and _seed_number(seed_dir) >= image_seeds:
            continue
        for fname in os.listdir(seed_dir):
            if not fname.endswith(".tikz"):
                continue
            name = fname[:-5]
            tikz_path = os.path.join(seed_dir, fname)
            png_path = os.path.join(seed_dir, f"{name}.png")
            if _png_is_current(tikz_path, png_path):
                skipped += 1
                continue
            _compile_one(
                tikz_path=tikz_path,
                png_path=png_path,
                name=name,
                preamble=preamble,
                bank_root=outcome.bank.abspath(),
            )
            compiled += 1
    if compiled or skipped:
        print(
            f"{outcome.slug}: compiled {compiled} TikZ figure(s), "
            f"skipped {skipped} already up to date"
        )

def _seed_number(seed_dir):
    """Seed directories are named for their seed (`f"{seed:04}"` in
    wrapper.sage), which is how the --image-seeds cap is applied here. If that
    naming ever changes, fail loudly rather than silently rasterizing the wrong
    subset (or nothing at all)."""
    entry = os.path.basename(seed_dir)
    try:
        return int(entry)
    except ValueError as e:
        raise RuntimeError(
            f"Expected a numerically-named seed directory, got {seed_dir!r}. "
            "compile_tikz_for_outcome() reads the seed number from the "
            "directory name to apply the --image-seeds cap."
        ) from e

def _png_is_current(tikz_path, png_path):
    """True when png_path exists and is no older than the .tikz it came from.

    A failed compile leaves no PNG behind (see _compile_one), so failures always
    retry rather than being cached as 'done'.
    """
    if not os.path.isfile(png_path):
        return False
    return os.path.getmtime(png_path) >= os.path.getmtime(tikz_path)

BANK_HELPERS_STY = "bank_helpers.sty"


def _load_preamble(bank_root):
    """The preamble each figure is compiled under.

    A tikz_preamble.tex in the bank root replaces this wholesale -- it carries
    its own \\documentclass, so it is a complete preamble rather than an
    addition, and a bank that writes one is taking full control.

    Otherwise the default gains \\usepackage{bank_helpers} when the bank has a
    bank_helpers.sty. That file holds the commands the bank's *content* needs,
    so a figure emitting one should be able to compile it, exactly as the
    printed document can.
    """
    custom = os.path.join(bank_root, "tikz_preamble.tex")
    if os.path.isfile(custom):
        with open(custom) as f:
            return f.read()
    if os.path.isfile(os.path.join(bank_root, BANK_HELPERS_STY)):
        return PREAMBLE + "\\usepackage{bank_helpers}\n"
    return PREAMBLE

def _support_files(bank_root):
    """Every .sty a figure's preamble may load, as (source, filename).

    `bank_helpers.sty`, plus whatever the bank declares under <latex-support>.
    A declared file is usually a theme installed by some other tool, and a
    figure drawn against that theme is the point: it makes the picture on the
    website and the picture in the printed handout the same picture, rather
    than two drawings kept looking alike by hand.

    Imported here rather than at module scope, because bank.py imports this
    module.
    """
    from ..bank import Bank

    found = []
    helpers = os.path.join(bank_root, BANK_HELPERS_STY)
    if os.path.isfile(helpers):
        found.append((helpers, BANK_HELPERS_STY))
    try:
        declared = Bank(bank_root).latex_support()
    except Exception:
        # A figure build must not fail because the manifest is unreadable;
        # `checkit generate` has already parsed it and reported anything wrong.
        return found
    for entry in declared:
        source = os.path.join(bank_root, entry["source"])
        if os.path.isfile(source):
            found.append((source, entry["filename"]))
    return found


def _log_errors(log_path, limit=8):
    """Error lines from a pdflatex log.

    LaTeX writes errors as a line beginning "! ", and carries on afterwards
    whenever it can. That recovery is why checking for a PDF is not enough:
    the file exists and the picture is wrong. Two silent cases reached
    published images before this was checked -- an undefined colour drew black,
    and an undefined \\dfrac dropped the fraction bar and printed "56".

    Warnings are left alone. Overfull boxes and font substitutions are normal
    in a figure and would make this too noisy to keep on.
    """
    if not os.path.isfile(log_path):
        return []
    with open(log_path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    errors = [line.strip() for line in lines if line.startswith("!")]
    if len(errors) > limit:
        errors = errors[:limit] + [f"... and {len(errors) - limit} more"]
    return errors


def _compile_one(tikz_path, png_path, name, preamble, bank_root=None):
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(tikz_path, os.path.join(tmp, f"{name}.tikz"))
        # pdflatex runs in the temp directory, so anything the preamble loads
        # has to be there too.
        if bank_root:
            for source, filename in _support_files(bank_root):
                shutil.copy(source, os.path.join(tmp, filename))
        wrapper_tex = os.path.join(tmp, "figure.tex")
        with open(wrapper_tex, "w") as f:
            f.write(preamble)
            f.write("\n\\begin{document}\n")
            f.write(f"\\input{{{name}.tikz}}\n")
            f.write("\\end{document}\n")
        # pdflatex can exit non-zero on RECOVERABLE errors while still
        # producing a valid PDF, so we don't use check=True here. A PDF being
        # written is necessary but NOT sufficient: the log is checked below,
        # because "recovered" means pdflatex carried on drawing something --
        # not that the something is right.
        # stdin=DEVNULL: some errors drop pdflatex to an interactive prompt even
        # under nonstopmode; feeding it empty input makes it exit instead of
        # hanging forever. Unfortunately this still doesn't work correctly.
        # timeout: hard backstop against any runaway process.
        try:
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmp, "figure.tex"],
                cwd=tmp,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=COMPILE_TIMEOUT,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"pdflatex timed out (>{COMPILE_TIMEOUT}s) compiling {name} "
                f"(from {tikz_path}). The figure may contain an error that put "
                f"pdflatex into an interactive prompt, or an expensive/looping "
                f"computation.\n--- partial output ---\n{e.stdout}\n{e.stderr}"
            ) from e
        pdf_path = os.path.join(tmp, "figure.pdf")
        if not os.path.isfile(pdf_path):
            raise RuntimeError(
                f"pdflatex failed to produce a PDF for {name} "
                f"(from {tikz_path}).\n"
                f"--- pdflatex output ---\n{result.stdout}\n{result.stderr}"
            )
        errors = _log_errors(os.path.join(tmp, "figure.log"))
        if errors:
            raise RuntimeError(
                f"pdflatex reported errors while compiling {name} "
                f"(from {tikz_path}). A PDF was still produced, but a figure "
                f"drawn through an error is not the figure that was asked for "
                f"-- an undefined colour silently draws black, an undefined "
                f"\\dfrac silently drops the fraction bar.\n"
                + "\n".join(f"  {line}" for line in errors)
                + f"\n\nThe figure's preamble comes from tikz_preamble.tex in "
                  f"the bank root, or CheckIt's default. Anything the figure "
                  f"uses has to be loaded there."
            )
        # PDF -> PNG. This step has no recoverable-error quirk, so a non-zero
        # exit is a genuine failure; surface the output if it happens.
        try:
            result = subprocess.run(
                ["pdftoppm", "-r", "150", "-png", "-singlefile", pdf_path, os.path.join(tmp, name)],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=COMPILE_TIMEOUT,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"pdftoppm timed out (>{COMPILE_TIMEOUT}s) converting {name}.\n"
                f"--- partial output ---\n{e.stdout}\n{e.stderr}"
            ) from e
        out_png = os.path.join(tmp, f"{name}.png")
        if not os.path.isfile(out_png):
            raise RuntimeError(
                f"pdftoppm failed to produce a PNG for {name}.\n"
                f"--- pdftoppm output ---\n{result.stdout}\n{result.stderr}"
            )
        # PDF is discarded with the temp directory; only the PNG is kept.
        shutil.move(out_png, png_path)
