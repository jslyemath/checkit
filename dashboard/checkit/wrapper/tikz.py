import concurrent.futures
import hashlib
import json
import os, shutil, subprocess, tempfile

from ..utils import atomic_write

#: Beside each outcome's seed folders: {"0007/fig.tikz": hash} for every
#: figure whose PNG is known to match what made it. Not published -- see
#: Bank.build_viewer.
FIGURE_KEYS = "figure-keys.json"

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

    **What "already current" means.** A PNG is current when it was made from
    this exact .tikz, under this exact preamble and these exact support
    files -- recorded as a hash per figure in `FIGURE_KEYS`. It used to mean
    "newer than its .tikz", which missed every change that mattered and
    caught one that did not (RV-11, 2026-11-16): editing tikz_preamble.tex or
    printitfigures.sty refreshed no PNG while print, which \\input's the
    .tikz, changed at once -- and `-r` rewrites every .tikz byte for byte, so
    every PNG recompiled for nothing. A figure with no recorded key is
    compiled once, so the first `-i` after this change redoes every figure.
    """
    generated = outcome.build_path()  # assets/<slug>/generated/
    preamble = _load_preamble(outcome.bank.abspath())
    # Worked out once per outcome, from the Bank already in hand. It was
    # worked out once per *figure*, by building a fresh Bank -- bank.xml
    # parsed and every seeds.json loaded, about a second each on mat-106,
    # half an hour of pure Python in a full F2 rasterise (RV-8).
    support = _support_files(outcome.bank)
    setting = _setting_key(preamble, support)
    keys_path = os.path.join(generated, FIGURE_KEYS)
    keys = _load_keys(keys_path)

    pending = []
    skipped = 0
    for entry in sorted(os.listdir(generated)):
        seed_dir = os.path.join(generated, entry)
        if not os.path.isdir(seed_dir):
            continue
        if image_seeds is not None and _seed_number(seed_dir) >= image_seeds:
            continue
        for fname in sorted(os.listdir(seed_dir)):
            if not fname.endswith(".tikz"):
                continue
            name = fname[:-5]
            tikz_path = os.path.join(seed_dir, fname)
            png_path = os.path.join(seed_dir, f"{name}.png")
            rel = f"{entry}/{fname}"
            key = _figure_key(setting, tikz_path)
            if os.path.isfile(png_path) and keys.get(rel) == key:
                skipped += 1
                continue
            pending.append((tikz_path, png_path, name, rel, key))

    # Each figure is an independent pdflatex in its own temp directory, and
    # nearly all of the ~2s it takes is that process starting up and reading
    # the preamble. Nothing is shared, so they run at once; threads are enough
    # because the work happens in subprocesses.
    #
    # This matters at the scale a real bank reaches. mat-106's F2 alone is
    # about 2,000 figures, which is over an hour one at a time.
    compiled = 0
    if pending:
        workers = min(_worker_count(), len(pending))
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_compile_one, tikz_path=t, png_path=p, name=n,
                                preamble=preamble, support=support): (rel, key)
                    for t, p, n, rel, key in pending
                }
                try:
                    for future in concurrent.futures.as_completed(futures):
                        future.result()
                        rel, key = futures[future]
                        keys[rel] = key
                        compiled += 1
                except BaseException:
                    # Cancel what has not started, *explicitly*. Leaving the
                    # `with` block waits for every queued figure, so the
                    # comment that stood here -- "raising here cancels what
                    # has not started" -- was false, and after one bad
                    # figure the other two thousand still compiled before
                    # the error was seen (RV-14). Figures already written
                    # keep their keys below, so a failure costs only the
                    # work that was in flight.
                    pool.shutdown(wait=False, cancel_futures=True)
                    raise
        finally:
            atomic_write(keys_path, json.dumps(keys, indent=0, sort_keys=True))

    if compiled or skipped:
        print(
            f"{outcome.slug}: compiled {compiled} TikZ figure(s), "
            f"skipped {skipped} already up to date"
        )


def _worker_count():
    """How many figures to compile at once.

    One per core, capped: past a point the machine is waiting on disk rather
    than doing more work, and a build should leave the laptop usable.
    CHECKIT_TIKZ_WORKERS overrides it, and 1 restores the old serial order for
    debugging a figure that only fails under load.
    """
    override = os.environ.get("CHECKIT_TIKZ_WORKERS")
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            raise RuntimeError(
                f"CHECKIT_TIKZ_WORKERS must be a whole number, got {override!r}"
            )
    return max(1, min(8, (os.cpu_count() or 2) - 1))

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

def _setting_key(preamble, support):
    """A hash of everything a figure is drawn under but its own source:
    the preamble and the contents of every support file it may load."""
    h = hashlib.sha256(preamble.encode("utf-8"))
    for source, filename in sorted(support, key=lambda s: s[1]):
        h.update(b"\0" + filename.encode("utf-8") + b"\0")
        with open(source, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def _figure_key(setting, tikz_path):
    """The hash a PNG must have been made under to count as current."""
    with open(tikz_path, "rb") as f:
        return hashlib.sha256(setting.encode("ascii") + f.read()).hexdigest()


def _load_keys(path):
    """The recorded keys, or none. A damaged file means recompiling, which
    is slow and correct; trusting it would be fast and maybe wrong."""
    try:
        with open(path, encoding="utf-8") as f:
            keys = json.load(f)
        return keys if isinstance(keys, dict) else {}
    except (OSError, ValueError):
        return {}

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
        with open(custom, encoding="utf-8") as f:     # RV-6
            return f.read()
    if os.path.isfile(os.path.join(bank_root, BANK_HELPERS_STY)):
        return PREAMBLE + "\\usepackage{bank_helpers}\n"
    return PREAMBLE

def _support_files(bank):
    """Every .sty a figure's preamble may load, as (source, filename).

    `bank_helpers.sty`, plus whatever the bank declares under <latex-support>.
    A declared file is usually a theme installed by some other tool, and a
    figure drawn against that theme is the point: it makes the picture on the
    website and the picture in the printed handout the same picture, rather
    than two drawings kept looking alike by hand.

    Takes the Bank, not its path. It took the path and built a new Bank from
    it on every call -- once per figure (RV-8) -- inside an `except
    Exception` that turned an unreadable manifest into figures quietly
    drawn without their theme.
    """
    root = bank.abspath()
    found, seen = [], set()
    helpers = os.path.join(root, BANK_HELPERS_STY)
    if os.path.isfile(helpers):
        found.append((helpers, BANK_HELPERS_STY))
        seen.add(BANK_HELPERS_STY)
    for entry in bank.latex_support():
        source = os.path.join(root, entry["source"])
        if entry["filename"] not in seen and os.path.isfile(source):
            found.append((source, entry["filename"]))
            seen.add(entry["filename"])
    return found


def _log_errors(log_path, limit=8):
    """Error lines from a pdflatex log.

    LaTeX writes errors as a line beginning "! ", and carries on afterwards
    whenever it can. That recovery is why checking for a PDF is not enough:
    the file exists and the picture is wrong. Two silent cases reached
    published images before this was checked -- an undefined color drew black,
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


def _compile_one(tikz_path, png_path, name, preamble, support=()):
    """One figure. `support` is `_support_files(bank)`, worked out once by
    the caller rather than once per figure."""
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(tikz_path, os.path.join(tmp, f"{name}.tikz"))
        # pdflatex runs in the temp directory, so anything the preamble loads
        # has to be there too.
        for source, filename in support:
            shutil.copy(source, os.path.join(tmp, filename))
        wrapper_tex = os.path.join(tmp, "figure.tex")
        with open(wrapper_tex, "w", encoding="utf-8") as f:       # RV-6
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
                f"-- an undefined color silently draws black, an undefined "
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
