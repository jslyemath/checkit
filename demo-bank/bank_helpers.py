"""Helper functions shared by this bank's generators.

**This file is yours to edit.** It ships nearly empty on purpose: put anything
here that more than one of your generators needs, so you write it once instead
of copying it between outcomes.

Any generator in this bank can use it:

    import bank_helpers as bh

    class Generator(BaseGenerator):
        def data(self):
            return {"total": bh.money(19.5)}

Two notes on how this works:

* The bank root is added to the import path when a generator runs, which is why
  a plain `import bank_helpers` finds this file from any outcome, however deeply
  nested its folder is.
* That path is added *after* the standard library and installed packages, so
  avoid naming modules here after things that already exist (`math.py`,
  `random.py`, `statistics.py`). Such a file would simply be ignored rather than
  shadow the real one.

This is separate from the built-in `CheckIt` helper class, which ships with the
platform and is available to every bank without importing anything. Use
`CheckIt` for the general machinery it provides; use this file for whatever is
specific to your own courses and subject matter.

The functions below are what this demo bank happens to need. A real bank's
version would hold its own subject matter -- number-system conversions, random
people, whatever the courses call for.
"""

ONES = ["zero", "one", "two", "three", "four", "five",
        "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]


def spell(n):
    """Small whole numbers as words, so a word problem reads naturally."""
    return ONES[n] if 0 <= n < len(ONES) else f"{n:,}"


def money(amount, symbol=r"\$"):
    """A dollar amount with thousands separators and two decimal places.

    Returns LaTeX, so the dollar sign is escaped -- a bare $ would start math
    mode. Escaping at the point of formatting means a generator never has to
    remember to do it.
    """
    return f"{symbol}{amount:,.2f}"


def readable_list(items, conjunction="and"):
    """['a', 'b', 'c'] -> 'a, b, and c', the way a textbook would write it.

    Handy for word problems, where the number of items varies by seed and the
    punctuation has to follow along.
    """
    items = [str(i) for i in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"
