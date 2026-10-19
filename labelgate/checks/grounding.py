"""G2: every numeric input should appear in the source text as a number.

A value counts as found if it equals a number in the text times a power of ten from 10**-3 to 10**3,
which allows plain unit rescaling. An input that is not found is also tested against hyphenated
ranges in the text: if its digits sit inside the digits of "150-160" joined together, it is reported
as range_merged instead of not_found.

check(task) is the reader the precision on the report was measured with. check(task, formats=True)
also reads four number formats seen in case reports: a decimal comma ("3,79", "1, 65"), a space as
thousands separator ("9 500"), a space after the decimal point ("64. 4") and a power of ten whose
superscript was lost ("1.79×105" for 1.79 × 10^5). It only adds candidate numbers, so it can remove a
flag but never add one.
"""
import re

NUMBER = re.compile(r"\d+(?:\.\d+)?")
RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)")
THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
SCALES = [10.0 ** k for k in range(-3, 4)]
DECIMAL_COMMA = re.compile(r"(?<![\d,])(\d+), ?(\d{1,2})(?![\d,])")
SPACE_THOUSANDS = re.compile(r"(?<![\d.])(\d{1,3})[ \u00a0\u2009\u202f](\d{3})(?!\d)")
SPACE_DECIMAL = re.compile(r"(\d+)\. (\d+)")
LOST_SUPERSCRIPT = re.compile(r"(\d+(?:\.\d+)?) ?[×x] ?10(\d{1,2})(?!\d)")


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def numeric_inputs(task, skip=("age",)):
    """Yield (field, number) for every number in the task's fields."""
    for name, (value, _unit) in task.fields.items():
        if name in skip:
            continue
        parts = value if isinstance(value, tuple) else (value,)
        for part in parts:
            if _is_number(part):
                yield name, float(part)


def note_numbers(text, formats=False):
    numbers = [float(m) for m in NUMBER.findall(THOUSANDS.sub("", text))]
    if formats:
        numbers += [float(f"{a}.{b}") for a, b in DECIMAL_COMMA.findall(text)]
        numbers += [float(a + b) for a, b in SPACE_THOUSANDS.findall(text)]
        numbers += [float(f"{a}.{b}") for a, b in SPACE_DECIMAL.findall(text)]
        numbers += [float(a) * 10 ** int(e) for a, e in LOST_SUPERSCRIPT.findall(text)]
    return numbers


def is_found(value, numbers):
    tol = 1e-3 * max(1.0, abs(value))
    return any(abs(value - n * s) < tol for n in numbers for s in SCALES)


def _digits(value):
    text = str(int(value)) if value == int(value) else repr(value)
    return text.replace(".", "").replace("-", "").lstrip("0")


def merged_range(value, text):
    """Return the range span whose joined digits contain the value's digits, or None."""
    want = _digits(value)
    for m in RANGE.finditer(THOUSANDS.sub("", text)):
        a, b = (x.replace(".", "") for x in m.groups())
        if len(want) > max(len(a), len(b)) and want in a + b:
            return m.group(0)
    return None


def check(task, skip=("age",), formats=False):
    numbers = note_numbers(task.source_text, formats)
    flags = []
    for name, value in numeric_inputs(task, skip):
        if is_found(value, numbers):
            continue
        span = merged_range(value, task.source_text)
        kind = "range_merged" if span else "not_found"
        flags.append({"field": name, "value": value, "kind": kind, "span": span or ""})
    return flags
