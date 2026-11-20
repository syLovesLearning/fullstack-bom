"""BOM 报价单 Excel (.xlsx) 导出服务。"""

from datetime import datetime
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


def _flatten_nodes(node: dict[str, Any], depth: int = 0, out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = out if out is not None else []
    rows.append({**node, "_depth": depth})
    for child in node.get("children") or []:
        _flatten_nodes(child, depth + 1, rows)
    return rows


def build_bom_quote_xlsx(
    rollup: dict[str, Any],
    params_3d: dict[str, float],
    margin_rate: float = 0.15,
    tax_rate: float = 0.13,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM报价单"

    root = rollup["root"]
    direct_cost = float(root.get("subtotal", 0.0))
    pre_tax = round(direct_cost * (1.0 + margin_rate), 2)
    final_price = round(pre_tax * (1.0 + tax_rate), 2)

    title_font = Font(name="Microsoft YaHei", size=14, bold=True, color="0F172A")
    hdr_fill = PatternFill("solid", fgColor="1E3A8A")
    hdr_font = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")

    ws["A1"] = f"产品报价与 BOM 算料明细单 — {root.get('name', '')} ({root.get('sku_code', '')})"
    ws["A1"].font = title_font
    ws.merge_cells("A1:H1")

    ws["A2"] = f"3D 尺寸(mm): H={params_3d['H']} × W={params_3d['W']} × D={params_3d['D']} × T={params_3d['T']}"
    ws["D2"] = f"毛利率: {margin_rate * 100:.1f}% | 税率: {tax_rate * 100:.1f}%"
    ws["G2"] = f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    ws["A3"] = "直接成本 (¥)"
    ws["B3"] = direct_cost
    ws["C3"] = "未税报价 (¥)"
    ws["D3"] = pre_tax
    ws["E3"] = "含税总报价 (¥)"
    ws["F3"] = final_price
    for cell in ("B3", "D3", "F3"):
        ws[cell].number_format = "#,##0.00"
        ws[cell].font = Font(bold=True, color="047857")

    headers = ["层级", "物料编码", "物料名称", "分类", "数量", "单位", "小计 (¥)", "余料/工艺备注"]
    row_idx = 5
    for col_idx, h in enumerate(headers, 1):
        c = ws.cell(row=row_idx, column=col_idx, value=h)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal="center", vertical="center")

    flat = _flatten_nodes(root)
    for item in flat[1:]:
        row_idx += 1
        depth = item["_depth"]
        prefix = "  " * max(0, depth - 1) + ("├─ " if depth > 0 else "")
        ws.cell(row=row_idx, column=1, value=depth)
        ws.cell(row=row_idx, column=2, value=item.get("sku_code", ""))
        ws.cell(row=row_idx, column=3, value=f"{prefix}{item.get('name', '')}")
        ws.cell(row=row_idx, column=4, value=item.get("category", ""))
        ws.cell(row=row_idx, column=5, value=round(float(item.get("qty", 0.0)), 4))
        ws.cell(row=row_idx, column=6, value=item.get("unit", ""))
        sub_cell = ws.cell(row=row_idx, column=7, value=round(float(item.get("subtotal", 0.0)), 2))
        sub_cell.number_format = "#,##0.00"
        ws.cell(row=row_idx, column=8, value=item.get("remnant_note", ""))

    widths = [8, 18, 30, 16, 12, 8, 14, 28]
    for idx, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + idx)].width = w

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
