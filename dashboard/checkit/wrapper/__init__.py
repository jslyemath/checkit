import importlib.resources
import subprocess, os, sys, tempfile, shutil
from ..utils import working_directory

# The generator's file extension selects the runtime. This is the whole runtime
# seam: no setting and no config file -- a generator declares what it needs by
# being named generator.py or generator.sage, and a bank may mix the two while
# migrating.
#
#   suffix -> (interpreter, wrapper script shipped in this package)
#
# sys.executable rather than the literal "python", so the subprocess uses the
# *same* interpreter running checkit. A machine with several Pythons would
# otherwise launch one that lacks sympy, and the failure would look like a
# broken generator rather than a wrong interpreter.
RUNTIMES = {
    ".py": (lambda: sys.executable, "wrapper.py"),
    ".sage": (lambda: "sage", "wrapper.sage"),
}


def run_generator(outcome, output_path, preview=True, images=False,
                  amount=1_000, random=False, image_seeds=None):
    """
    Runs an outcome's generator in the runtime its file extension selects,
    building to a seeds.json file at output_path.
    """
    if preview:
        amount_s = "20"
        random_s = "no"
    else:
        amount_s = str(amount)
        if random:
            random_s = "random"
        else:
            random_s = "no"
    generator_path = outcome.generator_path()
    if not os.path.isfile(generator_path):
        raise FileNotFoundError(generator_path)

    suffix = os.path.splitext(generator_path)[1].lower()
    try:
        interpreter, wrapper_name = RUNTIMES[suffix]
    except KeyError:
        raise RuntimeError(
            f"No runtime for generator {generator_path!r}. Expected one of: "
            + ", ".join(f"generator{s}" for s in RUNTIMES)
        ) from None

    with importlib.resources.path("checkit.wrapper", wrapper_name) as wrapper_path:
        with tempfile.TemporaryDirectory() as tmpdir:
            shutil.copyfile(wrapper_path, os.path.join(tmpdir, wrapper_name))
            with working_directory(outcome.bank.abspath()):
                cmds = [
                    interpreter(),
                    os.path.join(tmpdir, wrapper_name),
                    generator_path,
                    output_path,
                    amount_s,
                    random_s
                ]
                if images:
                    cmds += ["images"]
                    if image_seeds is not None:
                        cmds += [str(image_seeds)]
                try:
                    subprocess.run(cmds, check=True)
                except FileNotFoundError as e:
                    hint = (
                        "SageMath is not installed or not on PATH. It cannot be "
                        "pip-installed and does not run natively on Windows; "
                        "either install it, or port this generator to "
                        "generator.py (the plain-Python runtime)."
                        if suffix == ".sage" else
                        "The Python interpreter running checkit could not be "
                        "re-launched."
                    )
                    raise RuntimeError(
                        f"Could not launch {cmds[0]!r} to run {generator_path}. {hint}"
                    ) from e
