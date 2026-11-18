import type { BomNode, BomRollupResponse } from '../api/bomTypes'

export function printBomQuoteWith3D(rollup: BomRollupResponse | null, marginPct: number, taxPct: number, canvasImgUrl?: string): void {
  if (!rollup) return
  const rows: string[] = []
  const walk = (n: BomNode, depth: number) => {
    const indent = '&nbsp;&nbsp;'.repeat(depth * 2)
    rows.push(`<tr><td>${indent}${n.name}</td><td>${n.sku_code}</td><td>${n.qty} ${n.unit}</td><td>${n.scrap_qty || 0}</td><td>¥${n.subtotal}</td></tr>`)
    for (const c of n.children || []) walk(c, depth + 1)
  }
  walk(rollup.root, 0)
  const finalPrice = (rollup.root.subtotal * (1 + marginPct / 100) * (1 + taxPct / 100)).toFixed(2)
  const imgHtml = canvasImgUrl ? `<img src="${canvasImgUrl}" style="width:240px;border-radius:8px;border:1px solid #cbd5e1;" />` : ''
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>${rollup.root.sku_code} 工程报价单</title>
  <style>body{font-family:sans-serif;padding:24px;color:#0f172a}table{width:100%;border-collapse:collapse;margin-top:14px;font-size:12px}th,td{border:1px solid #cbd5e1;padding:6px 8px;text-align:left}th{background:#f1f5f9}.top{display:flex;justify-content:space-between;align-items:center}</style></head>
  <body><div class="top"><div><h2>工程 BOM 参数化报价单</h2><p>产品：${rollup.root.name} (${rollup.root.sku_code})</p><p>3D 尺寸：H=${rollup.params_3d.H} × W=${rollup.params_3d.W} × D=${rollup.params_3d.D} mm</p><p>直接成本：¥${rollup.root.subtotal} ｜ 毛利 ${marginPct}% + 税 ${taxPct}% ｜ <strong>含税总价：¥${finalPrice}</strong></p></div>${imgHtml}</div>
  <table><thead><tr><th>层级名称</th><th>SKU</th><th>计价用量</th><th>余料报废</th><th>小计</th></tr></thead><tbody>${rows.join('')}</tbody></table>
  <script>window.onload=()=>window.print()</script></body></html>`
  const w = window.open('', '_blank')
  if (w) { w.document.write(html); w.document.close() }
}
