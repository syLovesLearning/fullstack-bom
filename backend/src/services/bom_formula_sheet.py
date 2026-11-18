"""测试数据模板生成与上传解析：openpyxl 显式读写 xlsx，另兼容 csv。"""

import csv
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADERS = ["序号", "H(mm)", "W(mm)", "D(mm)", "T(mm)", "base_qty", "qty", "预期结果", "备注"]
_WIDTHS = [6, 10, 10, 10, 10, 11, 8, 12, 26]
_PRESET = [(2200, 800, 600, 2.0), (1800, 1200, 500, 1.5), (2600, 600, 800, 2.5)]
MAX_ROWS = 500
MAX_BYTES = 2 * 1024 * 1024

_ALIAS = {
    "h": "H", "h(mm)": "H", "高": "H", "高度": "H", "高(mm)": "H",
    "w": "W", "w(mm)": "W", "宽": "W", "宽度": "W", "宽(mm)": "W",
    "d": "D", "d(mm)": "D", "深": "D", "深度": "D", "深(mm)": "D",
    "t": "T", "t(mm)": "T", "厚": "T", "板厚": "T", "厚度": "T",
    "base_qty": "base_qty", "基准用量": "base_qty", "用量": "base_qty",
    "qty": "qty", "数量": "qty", "父件数量": "qty",
    "预期结果": "expected", "期望值": "expected", "预期值": "expected", "expected": "expected",
    "备注": "note", "说明": "note", "note": "note",
    "序号": "index", "index": "index", "no": "index",
}


def _norm(cell: Any) -> str:
    text = str(cell or "").strip().lower().replace(" ", "").replace("（", "(").replace("）", ")")
    return _ALIAS.get(text, text)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_template(expr: str = "", target: str = "qty") -> bytes:
    """生成 xlsx 模板：主表为待填数据，次表写清变量/函数/判定规则。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "测试数据"
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1D4ED8")
    for col, name in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font, cell.fill = head_font, head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = _WIDTHS[col - 1]
    for idx, (h, w, d, t) in enumerate(_PRESET, start=1):
        row = 1 + idx
        ws.cell(row=row, column=1, value=idx)
        for col, val in enumerate([h, w, d, t, 1, 1], start=2):
            ws.cell(row=row, column=col, value=val)
        ws.cell(row=row, column=8, value=None)
    ws.freeze_panes = "A2"

    doc = wb.create_sheet("填写说明")
    doc.column_dimensions["A"].width = 18
    doc.column_dimensions["B"].width = 96
    scope = "3D 用量公式（FORMULA_3D）" if target == "qty" else "特殊附加成本公式（元）"
    lines = [
        ("目标类型", scope),
        ("当前表达式", expr or "（尚未填写）"),
        ("必填列", "H / W / D / T 至少填齐尺寸；base_qty 缺省按 1 处理；qty 缺省按 1 处理"),
        ("预期结果", "至少填 1 行才可判定通过；其余留空表示只回显计算结果、不计入失败"),
        ("变量", "H 高、W 宽、D 深、T 板厚、base_qty 基准用量、qty 父件数量、loss_rate 损耗率"),
        ("函数", "iif(条件, 真值, 假值)、dist3d(x1,y1,z1,x2,y2,z2)、ceil(x)、floor(x)、min(a,b)、max(a,b)、abs(x)"),
        ("运算符", "+ - * / % > >= < <= == != and or 与括号，全部英文半角"),
        ("限制", f"最多 {MAX_ROWS} 行；不要改动表头文字；仅读取第 1 个工作表"),
        ("示例", "iif(W >= 1000, 120, -10) 表示宽度≥1000 加 120 元，否则减 10 元"),
    ]
    doc.cell(row=1, column=1, value="项").font = Font(bold=True)
    doc.cell(row=1, column=2, value="说明").font = Font(bold=True)
    for idx, (key, val) in enumerate(lines, start=2):
        doc.cell(row=idx, column=1, value=key)
        cell = doc.cell(row=idx, column=2, value=val)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _rows_from_csv(content: bytes) -> list[list[Any]]:
    for encoding in ("utf-8-sig", "gbk", "utf-8"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSV 编码无法识别，请另存为 UTF-8")
    return [row for row in csv.reader(StringIO(text))]


def _rows_from_xlsx(content: bytes) -> list[list[Any]]:
    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def parse_sheet(filename: str, content: bytes) -> dict[str, Any]:
    """解析上传文件为 {rows, warnings, skipped}；表头按别名映射，容错跳过空行。"""
    if len(content) > MAX_BYTES:
        raise ValueError("文件超过 2MB，请精简后重试")
    name = (filename or "").lower()
    if name.endswith(".csv"):
        raw_rows = _rows_from_csv(content)
    elif name.endswith((".xlsx", ".xlsm")):
        raw_rows = _rows_from_xlsx(content)
    else:
        raise ValueError("仅支持 .xlsx / .xlsm / .csv")

    raw_rows = [r for r in raw_rows if any(str(c).strip() for c in r if c is not None)]
    if len(raw_rows) < 2:
        raise ValueError("文件里没有数据行，请按模板填写后重试")

    header = [_norm(c) for c in raw_rows[0]]
    if "H" not in header and "W" not in header:
        raise ValueError("表头未识别到 H/W 等尺寸列，请使用下载的模板")
    col_of = {key: idx for idx, key in enumerate(header) if key}

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped = 0
    for offset, raw in enumerate(raw_rows[1:], start=2):
        if len(rows) >= MAX_ROWS:
            warnings.append(f"超过 {MAX_ROWS} 行上限，其余已忽略")
            break
        env: dict[str, float] = {}
        for key in ("H", "W", "D", "T", "base_qty", "qty"):
            idx = col_of.get(key)
            val = _num(raw[idx]) if idx is not None and idx < len(raw) else None
            if val is not None:
                env[key] = val
        if not env:
            skipped += 1
            continue
        miss = [k for k in ("H", "W", "D", "T") if k not in env]
        if miss:
            warnings.append(f"第 {offset} 行缺少 {'/'.join(miss)}，已按 0 处理")
        exp_idx = col_of.get("expected")
        note_idx = col_of.get("note")
        rows.append({
            "index": len(rows) + 1,
            "env": {k: env.get(k, 0.0) for k in ("H", "W", "D", "T")} | {"base_qty": env.get("base_qty", 1.0), "qty": env.get("qty", 1.0)},
            "expected": _num(raw[exp_idx]) if exp_idx is not None and exp_idx < len(raw) else None,
            "note": str(raw[note_idx]).strip() if note_idx is not None and note_idx < len(raw) and raw[note_idx] else "",
        })
    if not rows:
        raise ValueError("没有解析到有效数据行，请检查 H/W/D/T 是否填写")
    return {"rows": rows, "warnings": warnings[:10], "skipped": skipped}
