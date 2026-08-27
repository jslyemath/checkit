# Upstream 0.2.8, fork revision 1. Bump the last number whenever a wheel is cut
# for someone else to install.
#
# A distinct version matters because checkit-dashboard 0.2.8 also exists on
# PyPI, published by Steven Clontz on 2026-08-01, and it is different code.
# Without this, `pip show checkit-dashboard` could not tell you which you have.
#
# NOT a PEP 440 local version like '0.2.8+slye.1', which is what this means
# semantically and was tried first. GitHub Releases rewrites '+' to '.' in an
# uploaded asset's filename, turning the wheel into
# checkit_dashboard-0.2.8.slye.1-py3-none-any.whl -- which pip then refuses
# outright with "Invalid wheel filename (invalid version)". Anything that has
# to survive a release asset name must stick to digits and dots.
VERSION = '0.2.8.3'

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

# Which derived formats are precomputed at build time, and for which seeds.
#
# Browsers remove XSLT in Chrome 158 (2026-11-17), so the viewer can no longer
# transform SpaTeXt itself. It reads these instead. The ranges are deliberately
# unequal, and that inequality is the dangerous part: a consumer asking for a
# seed/format combination that was never emitted must fail loudly rather than
# render blank, which is the trap --image-seeds already set once (see
# CODEBASE_NOTES.md).
#
# Inline: carried in bank.json, which every visitor downloads. Cheap because it
# is only the public seeds, and because bank.json compresses about tenfold.
INLINE_FORMATS = ("html", "latex", "pretext")

# Bundled: one file per outcome, fetched only when an instructor asks. PreTeXt
# is absent on purpose -- the only consumer of PreTeXt is the instructor tab,
# and the version picker cannot reach past PUBLIC_SEEDS, so it would be dead
# weight for 950 seeds per outcome.
BUNDLE_FORMATS = ("html", "latex")
BUNDLE_FILENAME = "derived.json"

# Seeds are split by who consumes them:
#
#   0 .. PUBLIC_SEEDS-1     students; inlined in bank.json
#   PUBLIC_SEEDS .. BUNDLE_UNTIL-1   instructors; in the per-outcome bundles
#   BUNDLE_UNTIL .. end     print only; data exists in seeds.json, nothing is
#                           precomputed, nothing is published
#
# The last range is why this bound exists. Precomputing every seed for the
# browser meant ~83 MB of bundles for a 28-outcome bank, all of it committed to
# a repo that republishes regularly -- to serve seeds no browser ever asks for,
# because the print tool reads seeds.json directly and never touches the
# bundles. Bounding the browser's range keeps a large seed pool for print
# without paying to publish it.
BUNDLE_UNTIL = 400
