import os, subprocess, glob, shutil
from checkit.utils import working_directory
from checkit.bank import Bank
import dashboard.update_viewer

with working_directory("dashboard"):
    print("updating viewer & dashboard")
    dashboard.update_viewer.main()

with working_directory("demo-bank"):
    bank = Bank()
    print("generating bank data")
    # remote= is required because this bank has figures: precomputed HTML must
    # carry absolute <img src> values. The bank's own <url> is the directory the
    # site publishes to, so it is the right base.
    bank.write_json(remote=bank.url)
    print("building bank viewer")
    bank.build_viewer()

print("copying viewer")
if os.path.exists("docs/demo"):
    shutil.rmtree("docs/demo")
shutil.copytree("demo-bank/docs","docs/demo")
