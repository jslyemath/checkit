"""Generate a page that checks html.xsl's `subset` parameter in a real browser.

test_subset.py compares the stylesheet against a *transcription* of the viewer's
filter, written in Python. That catches drift in html.xsl, but it cannot catch a
place where the transcription itself misreads utils/index.ts, and it does not
run a real XSLTProcessor. This does both: same stylesheet, real engine, real DOM
removal, real serialisation, compared against lxml's output.

    python dashboard/tests/browser_harness.py [output.html]

Then open the file over http:// (a file:// page may be restricted) and read the
last line. Browsers are removing XSLT -- Chrome 158 on 2026-11-17 -- so a build
that has already dropped it reports that instead of running, and after the
removal date this harness stops being usable at all. The unittest suite does not
depend on it and keeps working.

Chromium is not sufficient on its own. The document-vs-element bug that this
codebase already hit was invisible in Chromium and only reproduced in Firefox
(see the note atop outcomeToStxDocument), so run this in both if it matters.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkit.static import read_resource

import spatext_fixtures as fx
from test_subset import canon, transform

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>CheckIt subset harness</title>
<body style="font:13px ui-monospace,Consolas,monospace">
<pre id="out">running...</pre>
<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const lines = [];
const say = s => lines.push(s);
const canon = s => s.replace(/>\\s+</g, '><').replace(/\\s+/g, ' ').trim();
const parser = new DOMParser();

say('userAgent: ' + navigator.userAgent);
if (typeof XSLTProcessor === 'undefined') {
  say('');
  say('XSLTProcessor is GONE from this browser. Nothing to check here.');
  say('This is the deprecation the harness exists to get ahead of.');
  document.getElementById('out').textContent = lines.join('\\n');
} else {

const xslDoc = parser.parseFromString(P.xsl, 'application/xml');
const err = xslDoc.querySelector('parsererror');
if (err) { say('FATAL: stylesheet did not parse: ' + err.textContent.slice(0,300)); }

function render(spatext, subsetValue) {
  const proc = new XSLTProcessor();
  proc.importStylesheet(xslDoc);
  if (subsetValue !== null) proc.setParameter(null, 'subset', subsetValue);
  // A Document, never an Element: match="/" only fires on the document node,
  // and Firefox (correctly) will not paper over the difference.
  const src = parser.parseFromString(spatext, 'application/xml');
  return proc.transformToDocument(src).querySelector('div[class~="stx"]');
}

// utils/index.ts, transcribed once more -- but here it runs on a real DOM.
function viewerFilter(ele, classes) {
  const clone = ele.cloneNode(true);
  for (const c of classes) {
    clone.querySelectorAll('[class~="' + c + '"]')
         .forEach(n => n.parentElement.removeChild(n));
  }
  return clone;
}

let pass = 0, fail = 0;
for (const f of P.fixtures) {
  const base = render(f.spatext, null);
  for (const c of P.cases) {
    const viaParam  = render(f.spatext, c.subset);
    const viaViewer = viewerFilter(base, c.classes);
    const a  = viaParam  ? canon(viaParam.outerHTML)  : '(null)';
    const v  = viaViewer ? canon(viaViewer.outerHTML) : '(null)';
    const py = f.expected[c.subset];
    const okViewer = (a === v), okPython = (a === py);
    if (okViewer && okPython) { pass++; continue; }
    fail++;
    say('');
    say('MISMATCH ' + f.name + ' subset=' + c.subset
        + '  param==viewer:' + okViewer + '  param==python:' + okPython);
    say('  browser/param : ' + a.slice(0,240));
    if (!okViewer) say('  browser/viewer: ' + v.slice(0,240));
    if (!okPython) say('  python/lxml   : ' + py.slice(0,240));
  }
}

// The document-vs-element trap, measured rather than assumed. Chromium resolves
// an Element source to its owner document; Firefox does not, and that
// difference cost four wrong fixes once already.
const f0 = P.fixtures[0];
const doc = parser.parseFromString(f0.spatext, 'application/xml');
const mk = () => { const p = new XSLTProcessor(); p.importStylesheet(xslDoc); return p; };
let fromEle;
try { fromEle = mk().transformToDocument(doc.documentElement); } catch (e) { fromEle = null; }
const fromDoc = mk().transformToDocument(doc);
const head = d => (d && d.documentElement) ? d.documentElement.outerHTML.slice(0,80) : '(threw or empty)';
say('');
say('document source -> ' + head(fromDoc));
say('element  source -> ' + head(fromEle));

say('');
say('RESULT: ' + pass + ' passed, ' + fail + ' failed');
document.getElementById('out').textContent = lines.join('\\n');
}
</script>
</body>
"""


def build():
    xsl = read_resource("html.xsl")
    if isinstance(xsl, bytes):
        xsl = xsl.decode("utf-8")

    fixtures = []
    for name, spatext in fx.ALL.items():
        fixtures.append({
            "name": name,
            "spatext": spatext,
            "expected": {
                subset: canon(transform(spatext, subset))
                for subset, _classes in fx.CASES.values()
            },
        })

    payload = {
        "xsl": xsl,
        "fixtures": fixtures,
        "cases": [
            {"subset": subset, "classes": classes}
            for subset, classes in fx.CASES.values()
        ],
    }
    return PAGE.replace("__PAYLOAD__", json.dumps(payload))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "subset_harness.html"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(build())
    print(f"wrote {out} ({os.path.getsize(out)} bytes, {len(fx.ALL)} fixtures)")
    print("serve it over http:// and open it; read the RESULT line.")
