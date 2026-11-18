/** BOM 专属 API 模块：物料、结构、试算树、报价快照、库存齐套与公式校验。
 * 领域类型统一从 bomTypes.ts 导出，本文件只放 HTTP 调用。
 */

import { request } from './client'
import type {
  BomEdge, BomEdgeRule, BomItem, BomRollupResponse, FormulaCheckResult,
  QuoteSnapshotItem, StockCheckItem,
} from './bomTypes'
export * from './bomTypes'

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

export function createBomEdge(token: string, parentId: string, payload: BomEdgeRule & { child_item_id: string }) {
  return request<BomEdge>(`/api/v1/bom/edges/${parentId}`, token, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** 拖拽落地：多选物料一次 POST，后端单事务 executemany 写入。 */
export function batchAddBomEdges(token: string, parentId: string, rows: Array<BomEdgeRule & { child_item_id: string }>) {
  return request<{ created_count: number }>(`/api/v1/bom/edges/${parentId}/batch`, token, {
    method: 'POST', body: JSON.stringify({ rows }),
  })
}

/** 拖拽换父级：边连同公式/余料策略整体迁移，只改挂载点。 */
export function moveBomEdge(token: string, edgeId: string, parentId: string) {
  return request<{ edge_id: string; parent_id: string; child_id: string }>(`/api/v1/bom/edges/${edgeId}/move`, token, {
    method: 'PATCH', body: JSON.stringify({ parent_id: parentId }),
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

export function updateBomEdge(token: string, edgeId: string, payload: BomEdgeRule) {
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
