import os, shutil, subprocess, tempfile

PREAMBLE = r"""\documentclass[tikz,border=4pt]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
"""
# To use a custom preamble, place a tikz_preamble.tex file in the bank root directory.

def compile_tikz_for_outcome(outcome):
    """Compile any .tikz files in the outcome's generated/ directory to PNG."""
    generated = outcome.build_path()  # assets/<slug>/generated/
    preamble = _load_preamble(outcome.bank.abspath())
    for entry in os.listdir(generated):
        seed_dir = os.path.join(generated, entry)
        if not os.path.isdir(seed_dir):
            continue
        for fname in os.listdir(seed_dir):
            if not fname.endswith(".tikz"):
                continue
            name = fname[:-5]
            _compile_one(
                tikz_path=os.path.join(seed_dir, fname),
                png_path=os.path.join(seed_dir, f"{name}.png"),
                name=name,
                preamble=preamble,
            )

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
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmp, "figure.tex"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        pdf_path = os.path.join(tmp, "figure.pdf")
        if not os.path.isfile(pdf_path):
            raise RuntimeError(
                f"pdflatex failed to produce a PDF for {name} "
                f"(from {tikz_path}).\n"
                f"--- pdflatex output ---\n{result.stdout}\n{result.stderr}"
            )
        # PDF -> PNG. This step has no recoverable-error quirk, so a non-zero
        # exit is a genuine failure; surface the output if it happens.
        result = subprocess.run(
            ["pdftoppm", "-r", "150", "-png", "-singlefile", pdf_path, os.path.join(tmp, name)],
            capture_output=True,
            text=True,
        )
        out_png = os.path.join(tmp, f"{name}.png")
        if not os.path.isfile(out_png):
            raise RuntimeError(
                f"pdftoppm failed to produce a PNG for {name}.\n"
                f"--- pdftoppm output ---\n{result.stdout}\n{result.stderr}"
            )
        # PDF is discarded with the temp directory; only the PNG is kept.
        shutil.move(out_png, png_path)
