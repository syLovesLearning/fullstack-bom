import { ref } from 'vue'
import {
  batchAddBomEdges, checkBomStock, cloneBomStructure, createBomEdge, deleteBomEdge, deleteBomItem,
  fetchBomRollupTree, listBomEdges, listBomItems, listBomQuotes, makeDefaultRule,
  moveBomEdge, saveBomQuote, seedBomDemo, updateBomEdge, upsertBomItem,
  type BomEdge, type BomEdgeRule, type BomItem, type BomRollupResponse, type QuoteSnapshotItem, type StockCheckItem,
} from '../api/bomClient'

const items = ref<BomItem[]>([])
const edges = ref<BomEdge[]>([])
const rollup = ref<BomRollupResponse | null>(null)
const quotes = ref<QuoteSnapshotItem[]>([])
const stockItems = ref<StockCheckItem[]>([])
const sandbox3d = ref({ h: 750, w: 1600, d: 800, t: 25 })
const loading = ref(false)

export function useBom() {
  async function refreshItems(token: string) {
    if (!token) return
    loading.value = true
    try { items.value = await listBomItems(token) } finally { loading.value = false }
  }
  async function saveItem(token: string, payload: Omit<BomItem, 'id' | 'created_at'>) {
    await upsertBomItem(token, payload); await refreshItems(token)
  }
  async function removeItem(token: string, id: string) {
    await deleteBomItem(token, id); items.value = items.value.filter((i) => i.id !== id)
  }
  async function refreshEdges(token: string, parentId: string, treeRootId?: string) {
    if (!token || !parentId) return
    edges.value = await listBomEdges(token, parentId)
    rollup.value = await fetchBomRollupTree(token, treeRootId || parentId, sandbox3d.value)
  }
  async function refreshTreeOnly(token: string, rootId: string) {
    if (token && rootId) rollup.value = await fetchBomRollupTree(token, rootId, sandbox3d.value)
  }
  async function addEdge(token: string, parentId: string, payload: object, treeRootId?: string) {
    await createBomEdge(token, parentId, payload as never); await refreshEdges(token, parentId, treeRootId)
  }
  async function addEdgesMany(token: string, parentId: string, rows: Array<BomEdgeRule & { child_item_id: string }>, treeRootId?: string) {
    await batchAddBomEdges(token, parentId, rows)
    await refreshTreeOnly(token, treeRootId || parentId)
  }
  async function moveEdge(token: string, edgeId: string, newParentId: string, treeRootId?: string) {
    await moveBomEdge(token, edgeId, newParentId)
    await refreshTreeOnly(token, treeRootId || newParentId)
  }
  async function dropItems(token: string, parentId: string, items: BomItem[], treeRootId?: string) {
    const rows = items.map((i) => makeDefaultRule(i.id, i.category))
    await addEdgesMany(token, parentId, rows, treeRootId)
    return rows.length
  }
  async function loadEdgeDetail(token: string, parentId: string, edgeId: string): Promise<BomEdge | null> {
    const rows = await listBomEdges(token, parentId)
    return rows.find((r) => r.id === edgeId) ?? null
  }
  async function saveEdge(token: string, edgeId: string, parentId: string, payload: object, treeRootId?: string) {
    await updateBomEdge(token, edgeId, payload as never); await refreshEdges(token, parentId, treeRootId)
  }
  async function removeEdge(token: string, parentId: string, edgeId: string, treeRootId?: string) {
    await deleteBomEdge(token, edgeId); await refreshEdges(token, parentId, treeRootId)
  }
  async function cloneBom(token: string, sourceId: string, targetId: string) {
    const res = await cloneBomStructure(token, sourceId, targetId)
    await refreshEdges(token, targetId, targetId)
    return res.cloned_count
  }
  async function runStockCheck(token: string, rootId: string) {
    stockItems.value = await checkBomStock(token, { root_id: rootId, ...sandbox3d.value })
  }
  async function createQuote(token: string, rootId: string, note = '', marginRate = 0.15, taxRate = 0.13) {
    const q = await saveBomQuote(token, { root_id: rootId, ...sandbox3d.value, margin_rate: marginRate, tax_rate: taxRate, note })
    quotes.value = await listBomQuotes(token)
    return q
  }
  async function loadQuotes(token: string) {
    if (token) quotes.value = await listBomQuotes(token)
  }
  async function fetchWhereUsed(token: string, itemId: string) {
    return whereUsedBomItem(token, itemId)
  }
  async function replaceItem(token: string, oldId: string, newId: string) {
    const res = await replaceBomItem(token, oldId, newId)
    await refreshItems(token)
    return res.replaced_count
  }
  async function batchAdjustPrice(token: string, category: string, pctDelta: number) {
    const res = await batchPriceBomItems(token, category, pctDelta)
    await refreshItems(token)
    return res.updated_count
  }
  async function seedDemo(token: string) {
    loading.value = true
    try { await seedBomDemo(token); await refreshItems(token) } finally { loading.value = false }
  }
  return {
    items, edges, rollup, quotes, stockItems, sandbox3d, loading,
    refreshItems, saveItem, removeItem, refreshEdges, refreshTreeOnly,
    addEdge, addEdgesMany, dropItems, moveEdge, loadEdgeDetail,
    saveEdge, removeEdge, cloneBom, runStockCheck, createQuote, loadQuotes, seedDemo,
  }
}
