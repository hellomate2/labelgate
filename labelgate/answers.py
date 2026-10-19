"""Parse a model's answer the way MedCalc-Bench's extract_answer() does, for numeric calculators.

Kept: take the last `answer": ...}` match, the "N out of" and comma-list rules for integer scores,
the mL/min/1.73 rule, and otherwise the last number. Two departures, both stated in the README:
an expression written as str(...) is not evaluated (the original calls eval on model text), and a
percent sign is not divided by 100, because FENa labels are themselves in percent.
"""
import re

INTEGER_CALCULATORS = {4, 15, 16, 17, 18, 20, 21, 25, 27, 28, 29, 32, 33, 36, 43, 45, 48, 51}
NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"


def answer_text(response):
    found = re.findall(r'[Aa]nswer":\s*(.*?)\}', response, flags=re.S)
    if not found:
        return None
    text = found[-1].strip().strip('"')
    if text in ("str(short_and_direct_answer_of_the_question)", "X.XX"):
        return None
    return text


def parse(response, calculator_id):
    """Return a float, or None when no answer can be read."""
    text = answer_text(response)
    if text is None:
        return None
    if calculator_id in INTEGER_CALCULATORS:
        m = re.search(r"(\d+) out of", text)
        if m:
            return float(m.group(1))
        m = re.search(r"-?\d+(, ?-?\d+)+", text)
        if m:
            return float(len(m.group(0).split(",")))
    if "str(" in text:
        return None
    m = re.search(rf"({NUMBER})\s*mL/min/1.73", text)
    if m:
        return float(m.group(1))
    numbers = re.findall(NUMBER, text.replace(",", ""))
    return float(numbers[-1]) if numbers else None
