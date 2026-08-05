"""Helpers shared by every outcome in this bank.

Demonstrates that a generator can `import` a module living at the bank root.
That only works because wrapper.py puts the bank root on sys.path before
exec'ing a generator -- running a script otherwise puts only the *script's*
directory there, and cwd is not on sys.path in Python 3.

A real bank puts its domain helpers here (number-system conversions, formatting,
random people, and so on) instead of copying them into every outcome or reaching
for runpy tricks.
"""

ONES = ["zero", "one", "two", "three", "four", "five",
        "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]


def spell(n):
    """Small whole numbers as words, so a word problem can read naturally."""
    return ONES[n] if 0 <= n < len(ONES) else f"{n:,}"


def readable_list(items, conjunction="and"):
    """['a','b','c'] -> 'a, b, and c' (Oxford comma, as a textbook would)."""
    items = [str(i) for i in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"


def money(amount):
    """A dollar amount with thousands separators and two decimal places."""
    return f"\\${amount:,.2f}"
