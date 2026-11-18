/** BOM 专属 API 模块：物料、结构、试算树、报价快照、库存齐套与公式校验。 */

import { request } from './client'

export interface BomItem {
  id: string
  sku_code: string
  name: string
  category: 'PRODUCT' | 'SEMI_FINISHED' | 'BASE_MATERIAL' | 'OUTSOURCED' | 'LABOR' | 'MACHINE'
  sub_type: 'FIXED' | 'NON_FIXED' | 'INTERNAL' | 'EXTERNAL' | 'SPECIAL_PROCESS' | 'STANDARD'
  unit: string
  base_price: number
  created_at: string
}

export interface BomEdge {
  id: string
  parent_item_id: string
  child_item_id: string
  child_sku: string
  child_name: string
  child_category: string
  child_sub_type: string
  child_unit: string
  child_price: number
  qty_mode: 'FIXED' | 'FORMULA_3D'
  base_qty: number
  formula_expr: string
  float_factor: number
  bom_group: '人工' | '材料' | '机械'
  cost_group: '半成品' | '基材' | '人工费'
}

export interface BomRollupResponse {
  root: {
    id: string
    sku_code: string
    name: string
    category: string
    qty: number
    subtotal: number
    children: Array<{
      id: string
      sku_code: string
      name: string
      category: string
      sub_type: string
      qty: number
      qty_mode?: string
      formula_expr?: string
      float_factor?: number
      bom_group?: string
      cost_group?: string
      subtotal: number
      children: unknown[]
    }>
  }
  cost_summary: Record<string, number>
  bom_summary: Record<string, number>
}

export interface QuoteSnapshotItem {
  id: string
  quote_no: string
  root_name: string
  direct_cost: number
  final_price: number
  note: string
  created_at: string
}

export interface StockCheckItem {
  sku_code: string
  name: string
  unit: string
  required_qty: number
  stock_qty: number
  warehouse: string
  status: '齐套' | '缺料' | '未建档'
}

export interface FormulaCheckResult {
  ok: boolean
  value: number | null
  error: string
}

export function listBomItems(token: string) {
  return request<BomItem[]>('/api/v1/bom/items', token)
}

export function upsertBomItem(token: string, payload: Omit<BomItem, 'id' | 'created_at'>) {
  return request<BomItem>('/api/v1/bom/items', token, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteBomItem(token: string, itemId: string) {
  return request<{ deleted: boolean }>(`/api/v1/bom/items/${itemId}`, token, { method: 'DELETE' })
}

export function listBomEdges(token: string, parentId: string) {
  return request<BomEdge[]>(`/api/v1/bom/edges/${parentId}`, token)
}

export function createBomEdge(
  token: string,
  parentId: string,
  payload: {
    child_item_id: string
    qty_mode: 'FIXED' | 'FORMULA_3D'
    base_qty: number
    formula_expr: string
    float_factor: number
    bom_group: '人工' | '材料' | '机械'
    cost_group: '半成品' | '基材' | '人工费'
  },
) {
  return request<BomEdge>(`/api/v1/bom/edges/${parentId}`, token, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteBomEdge(token: string, edgeId: string) {
  return request<{ deleted: boolean }>(`/api/v1/bom/edges/${edgeId}`, token, { method: 'DELETE' })
}

export function seedBomDemo(token: string) {
  return request<{ seeded_items: number; seeded_edges: number }>('/api/v1/bom/seed', token, {
    method: 'POST',
  })
}

export function fetchBomRollupTree(token: string, rootId: string, p?: { h: number; w: number; d: number; t: number }) {
  const qs = p ? `?h=${p.h}&w=${p.w}&d=${p.d}&t=${p.t}` : ''
  return request<BomRollupResponse>(`/api/v1/bom/tree/${rootId}${qs}`, token)
}

export function updateBomEdge(
  token: string,
  edgeId: string,
  payload: {
    qty_mode: 'FIXED' | 'FORMULA_3D'
    base_qty: number
    formula_expr: string
    float_factor: number
    bom_group: '人工' | '材料' | '机械'
    cost_group: '半成品' | '基材' | '人工费'
  },
) {
  return request<BomEdge>(`/api/v1/bom/edges/${edgeId}`, token, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function cloneBomStructure(token: string, source_parent_id: string, target_parent_id: string) {
  return request<{ cloned_count: number }>('/api/v1/bom/clone', token, {
    method: 'POST',
    body: JSON.stringify({ source_parent_id, target_parent_id }),
  })
}

export function saveBomQuote(token: string, payload: { root_id: string; h: number; w: number; d: number; t: number; margin_rate: number; tax_rate: number; note: string }) {
  return request<QuoteSnapshotItem>('/api/v1/bom/quotes', token, { method: 'POST', body: JSON.stringify(payload) })
}

export function listBomQuotes(token: string) {
  return request<QuoteSnapshotItem[]>('/api/v1/bom/quotes', token)
}

export function checkBomStock(token: string, payload: { root_id: string; h: number; w: number; d: number; t: number }) {
  return request<StockCheckItem[]>('/api/v1/bom/stock-check', token, { method: 'POST', body: JSON.stringify(payload) })
}

export function checkBomFormula(token: string, expr: string, env?: { H: number; W: number; D: number; T: number }) {
  return request<FormulaCheckResult>('/api/v1/bom/formula/check', token, {
    method: 'POST',
    body: JSON.stringify({ expr, env: env ?? { H: 2200, W: 800, D: 600, T: 2.0 } }),
  })
}
