"""公式 AI 录入链路测试：模板往返、上传解析、批量校验、口述编译（Fake LLM 离线）。"""

import asyncio
import json

import pytest

from src.config import settings
from src.services.bom_formula import verify_rows
from src.services.bom_formula_ai import draft_formula
from src.services.bom_formula_sheet import build_template, parse_sheet


class FakeLLM:
    """按序列返回预设 content，模拟模型正常/失败/自修复三种行为。"""

    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[list] = []

    async def chat_step(self, messages, tools):  # noqa: ANN001, ANN201
        self.calls.append(list(messages))
        content = self._replies[min(len(self.calls) - 1, len(self._replies) - 1)]
        return content, [], 100


def _draft(replies: list[str], intent: str = "宽度>=1000加120元，否则减10元", target: str = "extra"):
    llm = FakeLLM(replies)
    return asyncio.run(draft_formula(llm, intent, target=target)), llm


def test_template_roundtrip_xlsx() -> None:
    blob = build_template(expr="iif(W >= 1000, 120, -10)", target="extra")
    assert blob[:2] == b"PK"  # xlsx 即 zip 容器
    parsed = parse_sheet("模板.xlsx", blob)
    assert len(parsed["rows"]) == 3
    first = parsed["rows"][0]
    assert first["env"]["H"] == 2200 and first["env"]["W"] == 800
    assert first["expected"] is None  # 模板默认不填预期，避免自证
    assert parsed["skipped"] == 0


def test_parse_csv_with_aliases_and_expected() -> None:
    csv_text = "高(mm),宽度,深度,板厚,基准用量,数量,期望值,备注\n2200,1200,600,2,1,3,360,超宽\n"
    parsed = parse_sheet("data.csv", csv_text.encode("utf-8-sig"))
    row = parsed["rows"][0]
    assert row["env"] == {"H": 2200.0, "W": 1200.0, "D": 600.0, "T": 2.0, "base_qty": 1.0, "qty": 3.0}
    assert row["expected"] == 360.0
    assert row["note"] == "超宽"


def test_parse_rejects_unknown_header() -> None:
    with pytest.raises(ValueError, match="表头"):
        parse_sheet("bad.csv", "甲,乙,丙\n1,2,3\n".encode())


def test_verify_rows_mixed_status() -> None:
    rows = [
        {"index": 1, "env": {"H": 2200, "W": 800, "D": 600, "T": 2, "qty": 1}, "expected": -10},
        {"index": 2, "env": {"H": 2200, "W": 1200, "D": 600, "T": 2, "qty": 1}, "expected": 120},
        {"index": 3, "env": {"H": 2200, "W": 1200, "D": 600, "T": 2, "qty": 1}, "expected": 999},
        {"index": 4, "env": {"H": 2200, "W": 800, "D": 600, "T": 2, "qty": 1}, "expected": None},
    ]
    out = verify_rows("iif(W >= 1000, 120, -10)", rows)
    statuses = [r["status"] for r in out["rows"]]
    assert statuses == ["pass", "pass", "fail", "no_expect"]
    assert (out["passed"], out["failed"], out["no_expect"]) == (2, 1, 1)
    assert out["all_ok"] is False
    assert out["rows"][2]["diff"] == -879.0


def test_verify_rows_requires_at_least_one_expectation() -> None:
    rows = [{"index": 1, "env": {"H": 2200, "W": 800, "D": 600, "T": 2}, "expected": None}]
    out = verify_rows("H * 0.001", rows)
    # 全行留空 = 没人声明期望值，不能算"验证通过"，否则校验环节形同虚设
    assert out["no_expect"] == 1 and out["all_ok"] is False
    assert out["summary"]["avg"] == 2.2


def test_verify_rows_all_ok_when_every_expectation_matches() -> None:
    rows = [
        {"index": 1, "env": {"W": 800}, "expected": -10},
        {"index": 2, "env": {"W": 1200}, "expected": 120},
        {"index": 3, "env": {"W": 1500}, "expected": None},
    ]
    out = verify_rows("iif(W >= 1000, 120, -10)", rows)
    assert out["passed"] == 2 and out["failed"] == 0 and out["no_expect"] == 1
    assert out["all_ok"] is True


def test_verify_rows_syntax_error_flags_error() -> None:
    out = verify_rows("iif(W >=, 1, 2)", [{"index": 1, "env": {"W": 900}, "expected": 1}])
    assert out["rows"][0]["status"] == "error"
    assert out["all_ok"] is False


def test_draft_ok_with_valid_json() -> None:
    reply = json.dumps({"expr": "iif(W >= 1000, 120, -10)", "explain": "宽度阈值加收", "steps": ["判断W", "取值"], "assumptions": ["单位为元"]}, ensure_ascii=False)
    result, llm = _draft([reply])
    assert result["ok"] is True
    assert result["expr"] == "iif(W >= 1000, 120, -10)"
    assert len(result["samples"]) == 3
    assert result["samples"][0]["value"] == -10.0
    assert len(llm.calls) == 1


def test_draft_strips_code_fence_and_equals() -> None:
    reply = '```json\n{"expr": "= iif(W>=1000,120,-10)", "explain": "x", "steps": [], "assumptions": []}\n```'
    result, _ = _draft([reply])
    assert result["ok"] is True
    assert result["expr"] == "iif(W>=1000,120,-10)"


def test_draft_repairs_invalid_expr() -> None:
    bad = json.dumps({"expr": "iif(W >=, 1, 2)", "explain": "", "steps": [], "assumptions": []})
    good = json.dumps({"expr": "iif(W >= 1000, 120, -10)", "explain": "修正版", "steps": [], "assumptions": []})
    result, llm = _draft([bad, good])
    assert len(llm.calls) == 2  # 第二轮带错误信息重试
    assert "求值报错" in llm.calls[1][-1].content
    assert result["ok"] is True and result["expr"] == "iif(W >= 1000, 120, -10)"


def test_draft_returns_error_on_garbage() -> None:
    result, _ = _draft(["抱歉，我无法理解这句话。"])
    assert result["ok"] is False
    assert "JSON" in result["error"]


def test_draft_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", "your_api_key")
    result, llm = _draft(["{}"])
    assert result["ok"] is False
    assert "LLM_API_KEY" in result["error"]
    assert llm.calls == []
