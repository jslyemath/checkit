"""PreToolUse hook: refuse a Bash command that writes code through a heredoc
or edits a file with `sed -i`.

Both have shipped broken code here while reporting success. A heredoc
mangles backslashes, so `\\n` in a Python string becomes a real newline
and a find-and-replace matches nothing; `sed` reads `\\u` as an escape and
breaks every `\\usepackage`. The rule was written down in three places
and broken anyway, every time noticed only after the damage -- so it is
enforced here, before the command runs. See WORKING_RULES.md.

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

ADVICE = (
    "Blocked by this project's hook (.claude/hooks/no_heredoc.py): {what}. "
    "Write the script or the file with the Write tool instead -- for a "
    "find-and-replace, a Python script with `assert text.count(old) == 1` "
    "-- then run it with Bash. A heredoc mangles backslashes and `sed` "
    "eats `\\u`; both have shipped broken code here. See WORKING_RULES.md, "
    "'Checks that have failed silently here'."
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
