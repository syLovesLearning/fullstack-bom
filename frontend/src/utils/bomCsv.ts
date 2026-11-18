/** BOM 试算树导出 CSV（纯前端，不依赖后端）。 */

import type { BomNode } from '../api/bomTypes'

/** RFC 4180 转义：含逗号/引号/换行的字段用双引号包裹并转义内部引号，否则物料名含逗号会错列。 */
function csvCell(v: string | number): string {
  const s = String(v ?? '')
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function exportBomCsv(root: BomNode | null): void {
  if (!root) return
  const rows: Array<Array<string | number>> = [['层级名称', 'SKU', '计价用量', '余料报废', '附加费', '小计(元)', '余料备注']]
  const walk = (n: BomNode) => {
    rows.push([n.name, n.sku_code, n.qty, n.scrap_qty || 0, n.extra_cost || 0, n.subtotal, n.remnant_note || ''])
    for (const child of n.children || []) walk(child)
  }
  walk(root)
  const blob = new Blob(['\ufeff' + rows.map((r) => r.map(csvCell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${root.sku_code}_BOM报价.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
