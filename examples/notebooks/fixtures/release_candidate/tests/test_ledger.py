import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ledger import evaluate_adjustment, service_credit


def test_service_credit_uses_exact_percentage():
    assert service_credit(250.0, 10.0) == 25.0


def test_adjustment_supports_simple_arithmetic():
    assert evaluate_adjustment("10 + 5") == 15.0


if __name__ == "__main__":
    test_service_credit_uses_exact_percentage()
    test_adjustment_supports_simple_arithmetic()
