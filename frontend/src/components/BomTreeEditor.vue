<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useBom } from '../composables/useBom'
import type { QuoteSnapshotItem } from '../api/bomClient'
import BomEdgeModal from './BomEdgeModal.vue'

const props = defineProps<{ token: string }>()
const { items, edges, rollup, quotes, stockItems, sandbox3d, refreshEdges, refreshTreeOnly, addEdge, saveEdge, removeEdge, cloneBom, runStockCheck, createQuote, loadQuotes } = useBom()

const rootId = ref('')
const activeParentId = ref('')
const cloneFromId = ref('')
const modalOpen = ref(false)
const editingEdge = ref<Record<string, any> | null>(null)
const msg = ref(''); const errMsg = ref('')
const marginPct = ref(15)
const taxPct = ref(13)
const compareBase = ref<QuoteSnapshotItem | null>(null)
const compareMsg = ref('')

const parentOptions = computed(() => items.value.filter((i) => i.category === 'PRODUCT' || i.category === 'SEMI_FINISHED'))

async function selectNode(nodeId: string, isRoot = false) {
  if (isRoot) rootId.value = nodeId
  activeParentId.value = nodeId
  await refreshEdges(props.token, nodeId, rootId.value || nodeId)
}

async function handleModalSubmit(payload: Record<string, any>) {
  errMsg.value = ''; msg.value = ''
  try {
    if (editingEdge.value) await saveEdge(props.token, editingEdge.value.id, activeParentId.value, payload, rootId.value)
    else await addEdge(props.token, activeParentId.value, payload, rootId.value)
    modalOpen.value = false; msg.value = '规则配置已保存并完成重算'
  } catch (err) { errMsg.value = err instanceof Error ? err.message : String(err) }
}

async function handleClone() {
  if (!cloneFromId.value || !activeParentId.value) return
  try { msg.value = `成功克隆 ${await cloneBom(props.token, cloneFromId.value, activeParentId.value)} 条结构` }
  catch (err) { errMsg.value = err instanceof Error ? err.message : String(err) }
}

async function handleSaveQuote() {
  if (!rootId.value) return
  errMsg.value = ''
  try {
    const q = await createQuote(props.token, rootId.value, '3D沙盒试算快照', marginPct.value / 100, taxPct.value / 100)
    msg.value = `已冻结报价快照 ${q.quote_no}（毛利 ${marginPct.value}% + 税 ${taxPct.value}% → 含税 ¥${q.final_price}）`
  } catch (err) { errMsg.value = err instanceof Error ? err.message : String(err) }
}

function handleCompare(q: QuoteSnapshotItem) {
  if (!compareBase.value || compareBase.value.id === q.id) {
    compareBase.value = q
    compareMsg.value = `已设对比基准：${q.quote_no}（直接成本 ¥${q.direct_cost} · 含税 ¥${q.final_price}），点击其他快照计算差额`
    return
  }
  const dCost = +(q.direct_cost - compareBase.value.direct_cost).toFixed(2)
  const dPrice = +(q.final_price - compareBase.value.final_price).toFixed(2)
  const fmt = (v: number) => `${v >= 0 ? '+' : ''}${v}`
  compareMsg.value = `${compareBase.value.quote_no} → ${q.quote_no}：直接成本 ${fmt(dCost)} 元，含税总价 ${fmt(dPrice)} 元`
  compareBase.value = null
}

function exportCsv() {
  if (!rollup.value) return
  const rows = [['层级名称', 'SKU', '计价用量', '余料报废', '附加费', '小计(元)', '余料备注']]
  const walk = (n: any) => { rows.push([n.name, n.sku_code, n.qty, n.scrap_qty || 0, n.extra_cost || 0, n.subtotal, n.remnant_note || '']); (n.children || []).forEach(walk) }
  walk(rollup.value.root)
  const blob = new Blob(['﻿' + rows.map((r) => r.join(',')).join("\\n")], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${rollup.value.root.sku_code}_BOM报价.csv`; a.click()
}

onMounted(async () => {
  await loadQuotes(props.token)
  if (parentOptions.value.length) await selectNode(parentOptions.value[0].id, true)
})
</script>

<template>
  <div class="tree-editor">
    <div class="sandbox-bar">
      <strong>3D 沙盒(mm)：</strong>
      <label>H <input v-model.number="sandbox3d.h" type="number" class="num-inp" @change="refreshTreeOnly(token, rootId)" /></label>
      <label>W <input v-model.number="sandbox3d.w" type="number" class="num-inp" @change="refreshTreeOnly(token, rootId)" /></label>
      <label>D <input v-model.number="sandbox3d.d" type="number" class="num-inp" @change="refreshTreeOnly(token, rootId)" /></label>
      <label>T <input v-model.number="sandbox3d.t" type="number" step="0.5" class="num-inp" @change="refreshTreeOnly(token, rootId)" /></label>
      <button class="btn" @click="runStockCheck(token, rootId)">跨库查库存</button>
      <label>毛利% <input v-model.number="marginPct" type="number" min="0" max="80" class="num-inp" style="width: 52px" /></label>
      <label>税% <input v-model.number="taxPct" type="number" min="0" max="30" class="num-inp" style="width: 52px" /></label>
      <button class="btn btn-primary" @click="handleSaveQuote">冻结报价快照</button>
      <button class="btn" @click="exportCsv">导出 CSV</button>
      <div v-if="rollup" class="cost-pills">
        <span class="badge badge-ok">成本 ¥{{ rollup.root.subtotal }}</span>
        <span v-for="(v, k) in rollup.cost_summary" :key="k" class="badge badge-blue">{{ k }} ¥{{ v }}</span>
      </div>
    </div>

    <div class="split-pane">
      <aside class="tree-left">
        <select v-model="rootId" class="sel" style="width: 100%; margin-bottom: 8px" @change="selectNode(rootId, true)">
          <option v-for="p in parentOptions" :key="p.id" :value="p.id">{{ p.sku_code }} · {{ p.name }}</option>
        </select>
        <div v-if="rollup">
          <div class="tree-item" :class="{ active: activeParentId === rollup.root.id }" @click="selectNode(rollup.root.id)"><span>◈ {{ rollup.root.name }}</span><strong>¥{{ rollup.root.subtotal }}</strong></div>
          <div v-for="c1 in rollup.root.children" :key="c1.id">
            <div class="tree-item" :class="{ active: activeParentId === c1.id }" @click="(c1.category === 'PRODUCT' || c1.category === 'SEMI_FINISHED') && selectNode(c1.id)">
              <span>├─ {{ c1.name }} ({{ c1.qty }})</span><span>¥{{ c1.subtotal }}</span>
            </div>
            <div v-for="c2 in (c1.children as any[])" :key="c2.id" class="tree-leaf">
              <span>│ └─ {{ c2.name }} ({{ c2.qty }}) <em v-if="c2.remnant_note" style="color:#d97706">[{{ c2.remnant_note }}]</em></span><span>¥{{ c2.subtotal }}</span>
            </div>
          </div>
        </div>
      </aside>

      <div class="table-right">
        <div class="add-card">
          <button class="btn btn-primary" @click="editingEdge = null; modalOpen = true">+ 新增子件与高级规则</button>
          <select v-model="cloneFromId" class="sel" style="margin-left: auto"><option disabled value="">从其他BOM克隆...</option><option v-for="p in parentOptions" :key="p.id" :value="p.id">{{ p.name }}</option></select>
          <button class="btn" @click="handleClone">一键克隆</button>
        </div>
        <p v-if="msg" class="ok-line">{{ msg }}</p>
        <p v-if="errMsg" class="err-line">{{ errMsg }}</p>

        <div class="table-wrap">
          <table>
            <thead><tr><th>子件</th><th>计价/余料策略</th><th>公式 & 附加费</th><th>浮动</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="e in edges" :key="e.id">
                <td><strong>{{ e.child_sku }}</strong><div class="sub">{{ e.child_name }}</div></td>
                <td>{{ e.qty_mode }} · {{ (e as any).remnant_policy }}<div class="sub">整料:{{ (e as any).unit_pack_size }} 留库阈值:{{ (e as any).min_remnant }}</div></td>
                <td><div>{{ e.formula_expr || `固定 ${e.base_qty}` }}</div><div v-if="(e as any).extra_cost_expr" class="sub">附加: {{ (e as any).extra_cost_expr }}</div></td>
                <td>× {{ e.float_factor }}</td>
                <td><button class="btn" @click="editingEdge = e; modalOpen = true">高级配置</button> <button class="btn" @click="removeEdge(token, activeParentId, e.id, rootId)">移除</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="stockItems.length" class="table-wrap">
          <table>
            <thead><tr><th>跨库库存齐套检查 (rag_db.inventory_items)</th><th>需用量</th><th>现有库存</th><th>仓库</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="s in stockItems" :key="s.sku_code">
                <td>{{ s.name }}</td><td>{{ s.required_qty }} {{ s.unit }}</td><td>{{ s.stock_qty }}</td><td>{{ s.warehouse }}</td>
                <td><span class="badge" :class="s.status === '齐套' ? 'badge-ok' : 'badge-blue'">{{ s.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="quotes.length" class="table-wrap">
          <p v-if="compareMsg" class="ok-line">{{ compareMsg }}</p>
          <table>
            <thead><tr><th>历史报价快照</th><th>产品</th><th>直接成本</th><th>含税总价</th><th>时间</th><th>对比</th></tr></thead>
            <tbody>
              <tr v-for="q in quotes.slice(0, 5)" :key="q.id">
                <td>{{ compareBase?.id === q.id ? '⬤ ' : '' }}{{ q.quote_no }}</td>
                <td>{{ q.root_name }}</td><td>¥{{ q.direct_cost }}</td><td><strong>¥{{ q.final_price }}</strong></td>
                <td>{{ new Date(q.created_at).toLocaleString() }}</td>
                <td><button class="btn" @click="handleCompare(q)">{{ compareBase?.id === q.id ? '基准' : '⚖ 对比' }}</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    <BomEdgeModal :visible="modalOpen" :token="token" :items="items" :editing-edge="editingEdge" @close="modalOpen = false" @submit="handleModalSubmit" />
  </div>
</template>

<style scoped>
.tree-editor { display: flex; flex-direction: column; gap: 12px; }
.sandbox-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; background: #eff6ff; border: 1px solid #bfdbfe; padding: 10px 14px; border-radius: 10px; font-size: 13px; }
.cost-pills { display: flex; gap: 6px; margin-left: auto; flex-wrap: wrap; }
.split-pane { display: grid; grid-template-columns: 320px 1fr; gap: 14px; align-items: start; }
.tree-left { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
.tree-item { display: flex; justify-content: space-between; padding: 7px 8px; border-radius: 6px; font-size: 12px; cursor: pointer; }
.tree-item.active { background: #dbeafe; color: #1d4ed8; font-weight: 600; }
.tree-leaf { display: flex; justify-content: space-between; padding: 4px 8px 4px 16px; font-size: 11px; color: var(--muted); }
.table-right { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.add-card { display: flex; gap: 8px; align-items: center; background: var(--card); border: 1px solid var(--border); padding: 10px; border-radius: 10px; }
.sel, .num-inp { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; background: #fff; }
.num-inp { width: 64px; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { background: #f9fafb; color: var(--muted); }
.sub { font-size: 11px; color: var(--muted); }
.ok-line { color: #047857; background: #ecfdf5; padding: 8px 12px; border-radius: 8px; font-size: 12px; margin: 0; }
.err-line { color: var(--err); background: var(--err-soft); padding: 8px 12px; border-radius: 8px; font-size: 12px; margin: 0; }
</style>
