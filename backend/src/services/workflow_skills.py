"""配置化流程动态校验器与智能体 Skill 提示词生成器。"""

from datetime import date
from typing import Any


def validate_dynamic_workflow(definition: dict[str, Any], raw_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fields: list[dict[str, Any]] = definition.get("fields") or []
    cleaned: dict[str, Any] = {}
    errors: list[str] = []

    for f in fields:
        key = f["key"]
        label = f.get("label", key)
        ftype = f.get("type", "text")
        required = bool(f.get("required", True))
        val = raw_data.get(key)

        if val is None or (isinstance(val, str) and not val.strip()):
            if required:
                errors.append(f"缺少必填项: {label} ({key})")
            continue

        if ftype == "number":
            try:
                num = float(val)
            except (TypeError, ValueError):
                errors.append(f"{label} ({key}) 必须是数字")
                continue
            if "min_gt" in f and num <= float(f["min_gt"]):
                errors.append(f"{label} ({key}) 必须大于 {f['min_gt']}")
            elif num < 0:
                errors.append(f"{label} ({key}) 不能为负数")
            cleaned[key] = num
        elif ftype == "date":
            try:
                date.fromisoformat(str(val).strip())
            except ValueError:
                errors.append(f"{label} ({key}) 日期格式必须为 YYYY-MM-DD")
                continue
            cleaned[key] = str(val).strip()
        elif ftype == "select":
            options = f.get("options") or []
            sval = str(val).strip()
            if options and sval not in options:
                errors.append(f"{label} ({key}) 必须是 {options} 之一")
                continue
            cleaned[key] = sval
        else:
            cleaned[key] = str(val).strip()

    if errors:
        raise ValueError("；".join(errors))

    title = (
        cleaned.get("title")
        or cleaned.get("project_name")
        or cleaned.get("visitor_name")
        or definition["name"]
    )
    return str(title), cleaned


def build_workflow_skill_prompt(definitions: list[dict[str, Any]]) -> str:
    if not definitions:
        return "【企业流程权限】当前角色无权发起任何业务流程。"
    lines = ["【可用企业流程 Skill（仅列出当前用户有权限的流程）】发起时必须结合前序对话已提供的字段进行合并记忆，切勿重复追问用户已经填过的字段；仅追问仍缺失的必填字段，集齐后再调用 `submit_workflow_form`："]
    for d in definitions:
        field_desc = ", ".join(
            f"{f['key']}({f.get('type','text')}{'*' if f.get('required', True) else ''})"
            for f in (d.get("fields") or [])
        )
        lines.append(f"- `{d['flow_code']}`（{d['name']}）：{field_desc}")
    return "\n".join(lines)
