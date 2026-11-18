"""AST-based code map generator: produces token-efficient docs/CODE_INDEX.md."""

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "docs" / "CODE_INDEX.md"


def scan_python_file(path: Path) -> tuple[str, list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc = (ast.get_docstring(tree) or "").splitlines()[0] if ast.get_docstring(tree) else ""
    exports: list[str] = []
    deps: set[str] = set()

    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src."):
            deps.add(node.module)
    return doc, exports, sorted(deps)


def scan_frontend_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".vue":
        return [path.stem]
    return re.findall(r"export\s+(?:async\s+)?(?:function|interface|class|const)\s+(\w+)", text)


def main() -> None:
    lines = [
        "# CODE_INDEX.md — Auto-Generated Structural Map (Agent-Readable)",
        "",
        "> Do NOT edit manually. Run `python3 scripts/gen_code_index.py` after file/symbol changes.",
        "",
        "## Backend (`backend/src/`)",
        "",
        "| File | Exports | Internal Deps | Summary |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for py_file in sorted((ROOT / "backend" / "src").rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        rel = py_file.relative_to(ROOT).as_posix()
        doc, exports, deps = scan_python_file(py_file)
        lines.append(
            f"| `{rel}` | {', '.join(exports) or '-'} | {', '.join(deps) or '-'} | {doc or '-'} |"
        )

    lines.extend([
        "",
        "## Frontend (`frontend/src/`)",
        "",
        "| File | Exports / Component |",
        "| :--- | :--- |",
    ])
    for fe_file in sorted((ROOT / "frontend" / "src").rglob("*")):
        if fe_file.suffix not in (".ts", ".vue"):
            continue
        rel = fe_file.relative_to(ROOT).as_posix()
        exports = scan_frontend_file(fe_file)
        lines.append(f"| `{rel}` | {', '.join(exports) or '-'} |")

    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {OUT_FILE}")


if __name__ == "__main__":
    main()
