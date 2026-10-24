"""安全表达式求值。

两用：
1. calculator 工具——只允许算术
2. memory 过滤器——算术 + 比较 + 布尔 + 变量名

用 ast 白名单，拒绝一切其他语法（import、属性访问、调用等）。
"""
from __future__ import annotations

import ast
import operator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}


class UnsafeExpression(Exception):
    pass


#: 指数/重复次数的上限：防止 9**9**9**9 这类表达式把 CPU 烧死（DoS）
_MAX_EXPONENT = 10_000


def safe_eval(expr: str, variables: dict | None = None) -> object:
    """在白名单内求值。变量从 variables 取（仅支持名字，不支持点号访问）。"""
    variables = variables or {}
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpression(f"bad syntax: {exc}") from exc
    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        raise UnsafeExpression(f"unknown name: {node.id}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if type(node.op) is ast.Pow and isinstance(right, int) and abs(right) > _MAX_EXPONENT:
            raise UnsafeExpression(f"exponent too large: {right} (limit {_MAX_EXPONENT})")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, variables))
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            if type(op) not in _CMP_OPS:
                raise UnsafeExpression(f"comparison not allowed: {type(op).__name__}")
            right = _eval_node(comparator, variables)
            if not _CMP_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, variables) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)
    raise UnsafeExpression(f"expression not allowed: {type(node).__name__}")
