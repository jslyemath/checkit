from setuptools import setup

# Metadata goes in setup.cfg. These are here for GitHub's dependency graph.
#
# THIS LIST IS DUPLICATED from setup.cfg's install_requires, and setuptools uses
# THIS one -- a setup() keyword overrides the .cfg. So a dependency added only to
# setup.cfg is silently absent from the built wheel: that is how sympy went
# missing, making every generated bank fail with ModuleNotFoundError on a clean
# install while working fine in the editable dev environment where sympy was
# already present. dashboard/tests/test_packaging.py asserts the two agree.
setup(
    name="checkit-dashboard",
    install_requires=[
        "ipywidgets",
        "lxml",
        "latex2mathml",
        "pystache",
        "trogon",
        "click",
        "sympy",
    ],
)
