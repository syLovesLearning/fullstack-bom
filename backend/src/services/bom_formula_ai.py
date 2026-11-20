"""口述逻辑 → BOM 公式：LLM 编译为受限 DSL，回环自修复并输出样例求值。"""

import json
import re
from typing import Any

from src.config import settings
from src.schemas.models import ChatMessage
from src.services.bom_formula import eval_formula_with_error
from src.services.llm_service import LLMService

DSL_SPEC = (
    "可用变量（尺寸单位 mm）：H 高、W 宽、D 深、T 板厚、base_qty 基准用量、qty 父件数量、loss_rate 损耗率\n"
    "可用函数：iif(条件, 真值, 假值)、dist3d(x1,y1,z1,x2,y2,z2)、ceil(x)、floor(x)、min(a,b)、max(a,b)、abs(x)\n"
    "可用运算符：+ - * / % > >= < <= == != and or，以及括号\n"
    "禁止：赋值、字符串、列表、lambda、属性访问、import、中文标点、上述函数以外的任何调用"
)

_SYSTEM = f"""你是工业机柜 BOM 公式编译器。把用户的自然语言规则翻译成单行算术表达式。

{DSL_SPEC}

硬性要求：
1. 只输出一个 JSON 对象，不要 markdown 代码块，不要任何额外文字。
2. JSON 字段：expr（表达式，不含等号与反引号）、explain（一句话中文说明）、
   steps（数组，按计算顺序拆成 2~4 条中文步骤）、assumptions（数组，列出你补充的边界假设，可为空）。
3. 全用英文半角符号，比较用 >= <= ==，不要用单个 =。
4. 出现「否则」「其余情况」时用 iif 表达，必要时嵌套。
5. 不擅自换算单位；用户没说数量级就沿用原值。

口径约定（务必遵守，否则金额算错）：
- 用量公式（qty）：返回值是「单个父件」的用量，系统会再乘以父件累计数量；按数量放大时用 base_qty 或直接写系数。
- 附加成本公式（extra）：返回值是该子件行的金额总额，系统直接加到该行成本、不会再乘数量；
  只有用户明确说「每台/每个/按数量」时才乘 qty，并在 assumptions 里写明这一口径。
- 变量 qty 在 extra 中表示该行的计价用量，在 qty 公式中表示父件累计用量。"""

_SAMPLE_FRAMES = [
    {"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0, "qty": 1.0, "loss_rate": 0.0},
    {"H": 1800.0, "W": 1200.0, "D": 500.0, "T": 1.5, "qty": 12.0, "loss_rate": 0.05},
    {"H": 2600.0, "W": 600.0, "D": 800.0, "T": 2.5, "qty": 200.0, "loss_rate": 0.0},
]


def base_env(env: dict[str, float] | None, base_qty: float = 1.0, qty: float = 1.0) -> dict[str, float]:
    merged = {"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0, "base_qty": base_qty, "qty": qty, "loss_rate": 0.0}
    for key, val in (env or {}).items():
        if key in merged:
            try:
                merged[key] = float(val)
            except (TypeError, ValueError):
                continue
    return merged


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _clean_expr(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    expr = raw.replace("`", "").strip().lstrip("=").strip()
    if expr.lower().startswith("expr"):
        expr = expr.split(":", 1)[-1].split("=", 1)[-1].strip()
    return expr[:300]


def _compute_samples(expr: str, base: dict[str, float]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for frame in _SAMPLE_FRAMES:
        env = {**base, **frame}
        value, error = eval_formula_with_error(expr, env)
        out.append({"env": env, "value": None if value is None else round(value, 6), "error": error})
    return out


def _fail(message: str) -> dict[str, Any]:
    return {"ok": False, "expr": "", "explain": "", "steps": [], "assumptions": [], "samples": [], "error": message, "tokens": 0}


def _pack(data: dict[str, Any], base: dict[str, float], tokens: int) -> dict[str, Any]:
    expr = _clean_expr(data.get("expr"))
    if not expr:
        return {**_fail("模型未返回可用表达式，请把口述拆得更具体后重试"), "tokens": tokens}
    samples = _compute_samples(expr, base)
    bad = next((s["error"] for s in samples if s["error"]), "")
    if bad:
        return {"ok": False, "expr": expr, "explain": str(data.get("explain") or ""), "steps": [], "assumptions": [], "samples": samples, "error": bad, "tokens": tokens}
    steps = [str(s) for s in data.get("steps") or []][:4]
    assumptions = [str(s) for s in data.get("assumptions") or []][:4]
    return {
        "ok": True,
        "expr": expr,
        "explain": str(data.get("explain") or "").strip(),
        "steps": steps,
        "assumptions": assumptions,
        "samples": samples,
        "error": "",
        "tokens": tokens,
    }


async def draft_formula(
    llm: LLMService,
    intent: str,
    target: str = "qty",
    env: dict[str, float] | None = None,
    base_qty: float = 1.0,
    qty: float = 1.0,
) -> dict[str, Any]:
    """把口述规则编译为公式；首次求值失败时带错误信息让模型自修复一轮。"""
    if not settings.llm_api_key or settings.llm_api_key == "your_api_key":
        return _fail("未配置 LLM_API_KEY，AI 录入暂不可用；可直接手写公式。")
    base = base_env(env, base_qty, qty)
    scope = "3D 用量公式（结果按 base_qty 单位计）" if target == "qty" else "特殊附加成本公式（单位：元，可正可负）"
    prompt = (
        f"目标类型：{scope}\n"
        f"沙盒参数：H={base['H']} W={base['W']} D={base['D']} T={base['T']} "
        f"base_qty={base['base_qty']} qty={base['qty']} loss_rate={base['loss_rate']}\n"
        f"口述逻辑：{intent.strip()}"
    )
    messages = [ChatMessage(role="system", content=_SYSTEM), ChatMessage(role="user", content=prompt)]
    try:
        raw, _, tokens = await llm.chat_step(messages, tools=[])
    except Exception as exc:  # 网络/鉴权异常统一降级为可读提示
        return _fail(f"模型调用失败：{exc}")
    data = _extract_json(raw)
    if not data:
        return _fail("模型未返回可解析的 JSON，请换一种说法重述规则。")
    result = _pack(data, base, tokens)
    if result["ok"] or not result["expr"]:
        return result

    repair_prompt = (
        f"上一个表达式 `{result['expr']}` 求值报错：{result['error']}。"
        "请修正后重新只输出 JSON（字段同上），确保能算出数值。"
    )
    messages += [
        ChatMessage(role="assistant", content=raw),
        ChatMessage(role="user", content=repair_prompt),
    ]
    try:
        raw2, _, tokens2 = await llm.chat_step(messages, tools=[])
    except Exception:
        return result
    fixed = _extract_json(raw2)
    if not fixed:
        return result
    return _pack(fixed, base, tokens + tokens2)
