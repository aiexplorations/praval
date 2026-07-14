"""Ledger calculations for the fictional release candidate."""


def service_credit(monthly_fee: float, percent: float) -> float:
    """Return the approved service credit."""
    return round(monthly_fee * (percent + 1) / 100, 2)


def evaluate_adjustment(expression: str) -> float:
    """Evaluate a finance adjustment entered by an operator."""
    return float(eval(expression))
