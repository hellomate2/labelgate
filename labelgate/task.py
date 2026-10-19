from dataclasses import dataclass, field


@dataclass
class Task:
    """One labeled task: the text a label was extracted from, the extracted fields, and the label.

    fields maps a field name to (value, unit). Categorical fields use unit None.
    tolerance is relative, so 0.05 accepts answers within 5% of the label.
    lower and upper, when given, override tolerance as the accepted answer range.
    formula names a function in labelgate.formulas.FORMULAS, or None if no reference exists.
    """

    id: str
    source_text: str
    fields: dict
    label: float | None
    formula: str | None = None
    tolerance: float = 0.05
    lower: float | None = None
    upper: float | None = None
    meta: dict = field(default_factory=dict)

    def accepted_range(self):
        if self.lower is not None and self.upper is not None:
            return min(self.lower, self.upper), max(self.lower, self.upper)
        if self.label is None:
            return None
        spread = abs(self.label) * self.tolerance
        return self.label - spread, self.label + spread

    def accepts(self, answer):
        bounds = self.accepted_range()
        if bounds is None or answer is None:
            return False
        low, high = bounds
        return low - 1e-9 <= answer <= high + 1e-9
