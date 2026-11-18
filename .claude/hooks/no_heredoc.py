"""PreToolUse hook on Bash and PowerShell: refuse a command that writes code
through a heredoc, edits a file with `sed -i`, or goes around the git hooks.

Heredocs and `sed -i` have shipped broken code here while reporting
success. A heredoc mangles backslashes, so `\\n` in a Python string becomes
a real newline and a find-and-replace matches nothing; `sed` reads `\\u` as
an escape and breaks every `\\usepackage`. The rule was written down in
three places and broken anyway, every time noticed only after the damage --
so it is enforced here, before the command runs. See WORKING_RULES.md.

The git hooks (checkit-printit/githooks, DESIGN.md section 20) refuse a
commit or push that adds a real student. `--no-verify`, `commit -n` and a
change to `core.hooksPath` are the ways past them, so they are refused here.

Reads the hook payload on stdin. Exit 2 blocks the call and hands stderr
back to the model; exit 0 lets it through. Anything unparseable lets it
through: a broken hook must not stop every command.
"""

import json
import re
import sys

# `<<WORD`, `<< 'WORD'`, `<<-"WORD"`: a heredoc. Not `<<<` (a here-string,
# one line) and not `1<<3` (a shift).
HEREDOC = re.compile(r"(?<![<\d\w])<<-?\s*['\"]?[A-Za-z_][A-Za-z0-9_]*['\"]?")
SED_IN_PLACE = re.compile(r"(?:^|[\s;|&(])sed\s+(?:-[a-zA-Z]*i|--in-place)")

# Around the git hooks: --no-verify on any git command, -n on a commit
# (its short form), and core.hooksPath set, unset or overridden with -c.
NO_VERIFY = re.compile(r"\bgit\b[^\n;|&]*\s--no-verify\b")
COMMIT_N = re.compile(r"\bgit\b(?:\s+-c\s+\S+)*\s+commit\b[^\n;|&]*\s-[a-zA-Z]*n[a-zA-Z]*(?=\s|$)")
HOOKS_PATH = re.compile(r"core\.hookspath", re.IGNORECASE)

ADVICE = (
    "Blocked by this project's hook (.claude/hooks/no_heredoc.py): {what}. "
    "Write the script or the file with the Write tool instead -- for a "
    "find-and-replace, a Python script with `assert text.count(old) == 1` "
    "-- then run it with Bash. A heredoc mangles backslashes and `sed` "
    "eats `\\u`; both have shipped broken code here. See WORKING_RULES.md, "
    "'Checks that have failed silently here'."
)
GUARD = (
    "Blocked by this project's hook (.claude/hooks/no_heredoc.py): {what}. "
    "The git hooks refuse a commit or push that adds a real student "
    "(checkit-printit/DESIGN.md section 20), and this would go around them. "
    "If the guard refused something, replace the value with an invented one; "
    "if it is a false positive, ask the instructor to add the word to "
    "fine_words in ~/CheckItPrintIt/name-guard.toml."
)


def main():
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
    except Exception:                                     # noqa: BLE001
        return 0
    if not isinstance(command, str):
        return 0
    if HEREDOC.search(command.replace("<<<", "")):
        print(ADVICE.format(what="the command contains a heredoc"), file=sys.stderr)
        return 2
    if SED_IN_PLACE.search(command):
        print(ADVICE.format(what="the command edits a file with `sed -i`"),
              file=sys.stderr)
        return 2
    if NO_VERIFY.search(command) or COMMIT_N.search(command):
        print(GUARD.format(what="the command skips the git hooks"), file=sys.stderr)
        return 2
    if HOOKS_PATH.search(command):
        print(GUARD.format(what="the command changes core.hooksPath"), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
