"""安全表达式求值测试。"""
from __future__ import annotations

import pytest

from aria.safeval import UnsafeExpression, safe_eval


def test_arithmetic():
    assert safe_eval("2 + 3 * 4") == 14
    assert safe_eval("(2 + 3) * 4") == 20
    assert safe_eval("10 / 4") == 2.5
    assert safe_eval("-5 % 3") == 1


def test_comparisons_and_bool():
    assert safe_eval("3 > 2") is True
    assert safe_eval("1 == 2") is False
    assert safe_eval("1 < 2 and 3 > 2") is True
    assert safe_eval("not (1 > 2)") is True


def test_variables():
    assert safe_eval("budget - cost", {"budget": 30, "cost": 12}) == 18


def test_rejects_dangerous():
    for expr in [
        "__import__('os').system('ls')",
        "open('x')",
        "().__class__",
        "lambda: 1",
        "x if y else z",
        "[1, 2]",
        "'a'.join(['b'])",
    ]:
        with pytest.raises((UnsafeExpression, Exception)):
            safe_eval(expr)


def test_huge_exponent_rejected():
    """9**9**9**9 之类的表达式必须在最内层就被拒绝，而不是烧死 CPU。"""
    with pytest.raises(UnsafeExpression):
        safe_eval("9**9**9**9")
    with pytest.raises(UnsafeExpression):
        safe_eval("2**99999999")
    # 正常范围内的幂运算不受影响
    assert safe_eval("2**10") == 1024
    assert safe_eval("2**10000") == 2 ** 10000
