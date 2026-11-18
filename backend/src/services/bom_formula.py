"""安全 AST 表达式求值器与余料阈值核算：支持 iif() 条件、dist3d() 与整料余料报废计算。"""

import ast
import math
import operator
from typing import Any

_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_CMP_OPS = {ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Eq: operator.eq, ast.NotEq: operator.ne}


def dist3d(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)


def iif(cond: Any, true_val: float, false_val: float) -> float:
    return float(true_val) if bool(cond) else float(false_val)


_SAFE_FUNCS = {"dist3d": dist3d, "iif": iif, "ceil": math.ceil, "floor": math.floor, "min": min, "max": max, "abs": abs}


def safe_eval_formula(expr: str, env: dict[str, float], fallback: float = 0.0) -> float:
    if not expr or not expr.strip():
        return fallback
    try:
        tree = ast.parse(expr.strip(), mode="eval")
        return float(_eval_node(tree, env))
    except Exception:
        return fallback


def _eval_node(node: ast.AST, env: dict[str, float]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)):
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return float(env[node.id])
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left, env), _eval_node(node.right, env))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, env))
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP_OPS:
        return _CMP_OPS[type(node.ops[0])](_eval_node(node.left, env), _eval_node(node.comparators[0], env))
    if isinstance(node, ast.BoolOp):
        vals = [_eval_node(v, env) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS:
        return _SAFE_FUNCS[node.func.id](*[_eval_node(a, env) for a in node.args])
    raise ValueError("Unsupported formula syntax")


def calc_remnant_qty(raw_qty: float, pack_size: float, policy: str, min_remnant: float) -> tuple[float, float, str]:
    """返回 (计价用量, 不可用余料报废量, 备注)。"""
    if raw_qty <= 0 or policy == "CONTINUOUS" or pack_size <= 0:
        return round(raw_qty, 4), 0.0, ""
    packs = math.ceil(raw_qty / pack_size)
    rem = round(packs * pack_size - raw_qty, 4)
    if policy == "WHOLE_PACK":
        return round(packs * pack_size, 4), rem, f"整料计价(含废料+{rem})" if rem > 0 else ""
    if policy == "THRESHOLD_SCRAP" and 0 < rem < min_remnant:
        return round(packs * pack_size, 4), rem, f"余料{rem}<阈值{min_remnant}，整块报废+{rem}"
    return round(raw_qty, 4), 0.0, f"余料{rem}可留库" if rem > 0 else ""
