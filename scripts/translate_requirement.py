"""Translate Chinese requirements into agent-readable English specs + hierarchical relational .xmind."""

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib import request
from uuid import uuid4
import zipfile


def _uid() -> str:
    return uuid4().hex[:16]


def _call_llm_translate(zh_text: str) -> dict[str, Any] | None:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
    model = os.getenv("LLM_MODEL", "glm-4-flash")
    if not api_key or api_key == "your_api_key":
        return None

    prompt = (
        "Translate the following Chinese software requirement into a concise, agent-readable English "
        "hierarchical JSON tree with cross-node relationships. Return ONLY valid JSON with keys: "
        '{"title": str, "nodes": [{"id": str, "title": str, "children": [...]}], '
        '"relationships": [{"from_id": str, "to_id": str, "label": str}]}.\n\n'
        f"Chinese Requirement:\n{zh_text}"
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }).encode("utf-8")
    req = request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            content = raw["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(content)
    except Exception:
        return None


def _fallback_tree(zh_text: str) -> dict[str, Any]:
    """Deterministic offline structuring when LLM_API_KEY is not configured."""
    return {
        "title": "Requirement Specification (Agent-Readable)",
        "nodes": [
            {
                "id": "n_goal",
                "title": "1. Objective & Scope",
                "children": [{"id": "n_raw", "title": f"Source Intent: {zh_text[:120]}"}],
            },
            {
                "id": "n_api",
                "title": "2. Contract & Interface (docs/API_SPEC.md)",
                "children": [{"id": "n_schema", "title": "Define Pydantic v2 + TS types first"}],
            },
            {
                "id": "n_impl",
                "title": "3. Layered Implementation",
                "children": [
                    {"id": "n_be", "title": "Backend: api -> services/core -> repositories"},
                    {"id": "n_fe", "title": "Frontend: src/api -> composables -> Vue components"},
                ],
            },
            {
                "id": "n_verify",
                "title": "4. Verification & Memory Sync",
                "children": [{"id": "n_idx", "title": "Run tests + gen_code_index.py"}],
            },
        ],
        "relationships": [
            {"from_id": "n_api", "to_id": "n_be", "label": "governs"},
            {"from_id": "n_api", "to_id": "n_fe", "label": "governs"},
            {"from_id": "n_impl", "to_id": "n_verify", "label": "validated_by"},
        ],
    }


def _to_xmind_topic(node: dict[str, Any], id_map: dict[str, str]) -> dict[str, Any]:
    x_id = _uid()
    if "id" in node:
        id_map[node["id"]] = x_id
    topic: dict[str, Any] = {"id": x_id, "title": node["title"]}
    children = node.get("children") or []
    if children:
        topic["children"] = {"attached": [_to_xmind_topic(c, id_map) for c in children]}
    return topic


def build_xmind_file(tree: dict[str, Any], xmind_path: Path) -> None:
    id_map: dict[str, str] = {}
    root_id = _uid()
    root_topic = {
        "id": root_id,
        "title": tree["title"],
        "structureClass": "org.xmind.ui.logic.right",
        "children": {"attached": [_to_xmind_topic(n, id_map) for n in tree.get("nodes", [])]},
    }
    relationships = []
    for rel in tree.get("relationships", []):
        src = id_map.get(rel["from_id"])
        dst = id_map.get(rel["to_id"])
        if src and dst:
            relationships.append({
                "id": _uid(),
                "end1Id": src,
                "end2Id": dst,
                "title": rel.get("label", "relates"),
            })

    sheet = {
        "id": _uid(),
        "class": "sheet",
        "title": tree["title"],
        "rootTopic": root_topic,
        "relationships": relationships,
    }
    manifest = {"file-entries": {"content.json": {}, "metadata.json": {}}}
    metadata = {"creator": {"name": "agent-framework-translator", "version": "1.0"}}

    with zipfile.ZipFile(xmind_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps([sheet], ensure_ascii=False, indent=2))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))


def translate_requirement_to_xmind(
    chinese_text: str, out_dir: Path, slug: str = "requirement"
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tree = _call_llm_translate(chinese_text) or _fallback_tree(chinese_text)

    xmind_path = out_dir / f"{slug}.xmind"
    build_xmind_file(tree, xmind_path)

    md_lines = [f"# {tree['title']}", ""]
    def walk(nodes: list[dict[str, Any]], depth: int = 0) -> None:
        for n in nodes:
            md_lines.append(f"{'  ' * depth}- {n['title']}")
            walk(n.get("children") or [], depth + 1)

    walk(tree.get("nodes", []))
    if tree.get("relationships"):
        md_lines.extend(["", "## Relationships"])
        for rel in tree["relationships"]:
            md_lines.append(f"- `{rel['from_id']}` --({rel.get('label', 'relates')})--> `{rel['to_id']}`")

    md_path = out_dir / f"{slug}.en.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return md_path, xmind_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate Chinese requirement to English spec + XMind")
    parser.add_argument("text", help="Chinese requirement text")
    parser.add_argument("--slug", default="requirement", help="Output filename slug")
    parser.add_argument("--out", default="docs/requirements", help="Output directory")
    args = parser.parse_args()
    md_p, xm_p = translate_requirement_to_xmind(args.text, Path(args.out), args.slug)
    print(f"Generated: {md_p} and {xm_p}")
