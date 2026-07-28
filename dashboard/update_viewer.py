import os, subprocess, glob, shutil, tempfile
from checkit.utils import working_directory

def main():
    with working_directory("../demo-bank"):
        print("building bank...")
        # -i is required or the demo bank is rebuilt with no images at all,
        # which build_docs.py then publishes over docs/demo -- deleting the
        # previously published PNGs. The cap keeps this to about a minute:
        # the viewer only ever shows ~20 seeds, and .tikz source is written for
        # every seed regardless, so LaTeX output is unaffected by it.
        subprocess.run("python -m checkit generate -r -i --image-seeds 20".split(" "))

    with working_directory("../viewer"):
        print("building viewer...")
        subprocess.run("npm run build".split(" "))

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