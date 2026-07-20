from __future__ import annotations

import ast
import operator
from typing import Any

from app.ai.agents.registry import BaseTool, ToolContext, ToolResult, register_tool

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported expression")


@register_tool
class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Evaluate a safe arithmetic expression (e.g. 12.5 * 1.08)."
    tags = ["math", "utility"]
    input_schema = {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    }

    async def execute(self, ctx: ToolContext, **kwargs: Any) -> ToolResult:
        _ = ctx
        expr = str(kwargs.get("expression") or "").strip()
        if not expr:
            return ToolResult(False, error="expression is required")
        try:
            tree = ast.parse(expr, mode="eval")
            value = _safe_eval(tree)
            return ToolResult(True, data={"expression": expr, "result": value})
        except Exception as exc:
            return ToolResult(False, error=f"Invalid expression: {exc}")
