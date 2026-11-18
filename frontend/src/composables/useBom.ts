import { ref } from 'vue'
import {
  checkBomStock, cloneBomStructure, createBomEdge, deleteBomEdge, deleteBomItem,
  fetchBomRollupTree, listBomEdges, listBomItems, listBomQuotes, saveBomQuote,
  seedBomDemo, updateBomEdge, upsertBomItem,
  type BomEdge, type BomItem, type BomRollupResponse, type QuoteSnapshotItem, type StockCheckItem,
} from '../api/bomClient'

const items = ref<BomItem[]>([])
const edges = ref<BomEdge[]>([])
const rollup = ref<BomRollupResponse | null>(null)
const quotes = ref<QuoteSnapshotItem[]>([])
const stockItems = ref<StockCheckItem[]>([])
const sandbox3d = ref({ h: 2200, w: 800, d: 600, t: 2.0 })
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
  async function addEdge(token: string, parentId: string, payload: Record<string, unknown>, treeRootId?: string) {
    await createBomEdge(token, parentId, payload as never); await refreshEdges(token, parentId, treeRootId)
  }
  async function saveEdge(token: string, edgeId: string, parentId: string, payload: Record<string, unknown>, treeRootId?: string) {
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
  async function seedDemo(token: string) {
    loading.value = true
    try { await seedBomDemo(token); await refreshItems(token) } finally { loading.value = false }
  }
  return {
    items, edges, rollup, quotes, stockItems, sandbox3d, loading,
    refreshItems, saveItem, removeItem, refreshEdges, refreshTreeOnly,
    addEdge, saveEdge, removeEdge, cloneBom, runStockCheck, createQuote, loadQuotes, seedDemo,
  }
}
