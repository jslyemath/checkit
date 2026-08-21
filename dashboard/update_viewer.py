import os, subprocess, glob, shutil, sys, tempfile
from checkit import PUBLIC_SEEDS
from checkit.bank import Bank
from checkit.utils import working_directory

def _npm():
    """npm is npm.cmd on Windows, which bare subprocess.run() will not find."""
    found = shutil.which("npm")
    if found is None:
        raise RuntimeError("npm is not installed or not on PATH; cannot build the viewer.")
    return found

def main():
    with working_directory("../demo-bank"):
        print("building bank...")
        # -i is required or the demo bank is rebuilt with no images at all,
        # which build_docs.py then publishes over docs/demo -- deleting the
        # previously published PNGs. The cap keeps this to about a minute:
        # the viewer only ever shows PUBLIC_SEEDS seeds, and .tikz source is
        # written for every seed regardless, so LaTeX output is unaffected.
        #
        # sys.executable, not "python": on a machine with several Pythons the
        # bare name resolves to whatever is first on PATH, which is often not
        # the environment checkit is installed in.
        #
        # check=True on both calls: without it a failed generate was ignored and
        # the build carried on to publish a stale or empty demo site.
        #
        # --remote is required because the demo bank has figures: precomputed
        # HTML has to carry absolute <img src> values or they 404 wherever the
        # HTML ends up. It comes from the bank's own <url>, which for this bank
        # is the directory the site publishes to, so there is no second place
        # to keep in sync.
        remote = Bank().url
        subprocess.run(
            [sys.executable, "-m", "checkit", "generate", "-r", "-i",
             "--image-seeds", str(PUBLIC_SEEDS), "--remote", remote],
            check=True,
        )

    with working_directory("../viewer"):
        print("building viewer...")
        subprocess.run([_npm(), "run", "build"], check=True)

    print('zipping up viewer')
    with tempfile.TemporaryDirectory() as temporary_directory:
        shutil.copytree(
            os.path.join('..','viewer','dist'),
            temporary_directory,
            dirs_exist_ok=True,
        )
        os.remove(os.path.join(temporary_directory,"assets","bank.json"))
        shutil.make_archive(
            os.path.join('checkit','static','viewer'),
            'zip',
            temporary_directory,
        )

if __name__ == "__main__":
    main()