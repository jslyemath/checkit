VERSION = '0.2.8'

# How many exercise versions the viewer exposes to students, and therefore the
# range everything else measures itself against: `checkit preview` generates
# this many, --image-seeds should not fall below it, and printed assessments
# deliberately draw from seeds at or above it so a student cannot look up the
# printed version.
#
# THIS VALUE IS DUPLICATED IN THE VIEWER as PUBLIC_SEEDS in
# viewer/src/utils/index.ts, because the browser cannot import from Python.
# The two must match; dashboard/tests/test_subset.py asserts that they do.
PUBLIC_SEEDS = 50
