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
    re-running generation (or taking a 20-seed preview after a 1000-seed build)
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

def _load_preamble(bank_root):
    custom = os.path.join(bank_root, "tikz_preamble.tex")
    if os.path.isfile(custom):
        with open(custom) as f:
            return f.read()
    return PREAMBLE

def _compile_one(tikz_path, png_path, name, preamble):
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(tikz_path, os.path.join(tmp, f"{name}.tikz"))
        wrapper_tex = os.path.join(tmp, "figure.tex")
        with open(wrapper_tex, "w") as f:
            f.write(preamble)
            f.write("\n\\begin{document}\n")
            f.write(f"\\input{{{name}.tikz}}\n")
            f.write("\\end{document}\n")
        # pdflatex can exit non-zero on RECOVERABLE errors while still
        # producing a valid PDF, so we don't use check=True here. Instead we
        # judge success by whether figure.pdf was actually written.
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
