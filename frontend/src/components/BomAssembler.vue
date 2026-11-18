<script setup lang="ts">
/** 拖拽拼装三栏容器：物料库 / 嵌套卡片画布 / 属性检查器。 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  createBomEdge, deleteBomEdge, listBomEdges, moveBomEdge, updateBomEdge,
  type BomEdge, type BomEdgeRule, type BomNode,
} from '../api/bomClient'
import { useBom } from '../composables/useBom'
import { buildTreeIndex, nodeKey, useBomDrag } from '../composables/useBomDrag'
import BomInspector from './BomInspector.vue'
import BomNodeCard from './BomNodeCard.vue'
import BomPalette from './BomPalette.vue'

const props = defineProps<{ token: string; rootId: string }>()
const { items, rollup, sandbox3d, refreshItems, refreshTreeOnly, dropItems, moveEdge, removeEdge, saveEdge, loadEdgeDetail } = useBom()
const { payload, undoStack, end, pushUndo, undo } = useBomDrag()

const selectedKey = ref('')
const focusKey = ref('')
const edgeDetail = ref<BomEdge | null>(null)
const msg = ref('')
const errMsg = ref('')
const busy = ref(false)

const tree = computed<BomNode | null>(() => rollup.value?.root ?? null)
const index = computed(() => buildTreeIndex(tree.value))
const displayRoot = computed<BomNode | null>(() => focusKey.value ? index.value.byKey.get(focusKey.value)?.node ?? tree.value : tree.value)
const crumbs = computed(() => focusKey.value ? index.value.chainOf(focusKey.value).map((n) => n.name).join(' / ') : '')
const selectedNode = computed<BomNode | null>(() => selectedKey.value ? index.value.byKey.get(selectedKey.value)?.node ?? null : null)
const selectedMeta = computed(() => selectedKey.value ? index.value.byKey.get(selectedKey.value) : undefined)

function ruleFromEdge(e: BomEdge): BomEdgeRule & { child_item_id: string } {
  return {
    child_item_id: e.child_item_id, qty_mode: e.qty_mode, base_qty: e.base_qty,
    formula_expr: e.formula_expr, extra_cost_expr: e.extra_cost_expr || '',
    remnant_policy: e.remnant_policy || 'CONTINUOUS', unit_pack_size: e.unit_pack_size ?? 1,
    min_remnant: e.min_remnant ?? 0, loss_rate: e.loss_rate ?? 0,
    float_factor: e.float_factor, bom_group: e.bom_group, cost_group: e.cost_group,
  }
}

function flash(ok: string) { msg.value = ok; errMsg.value = '' }
function fail(err: unknown) { errMsg.value = err instanceof Error ? err.message : String(err); msg.value = '' }

async function handleSelect(key: string, node: BomNode) {
  selectedKey.value = key
  edgeDetail.value = null
  const meta = index.value.byKey.get(key)
  if (node.edge_id && meta?.parentId) edgeDetail.value = await loadEdgeDetail(props.token, meta.parentId, node.edge_id)
}

async function handleDrop(targetKey: string) {
  const p = payload.value
  const meta = index.value.byKey.get(targetKey)
  end()
  if (!p || !meta) return
  const parentId = meta.node.id
  busy.value = true
  try {
    if (p.kind === 'new') {
      const before = await listBomEdges(props.token, parentId)
      const n = await dropItems(props.token, parentId, p.items, props.rootId)
      const after = await listBomEdges(props.token, parentId)
      const newIds = after.filter((a) => !before.some((b) => b.id === a.id)).map((a) => a.id)
      pushUndo({ label: `撤销新增 ${n} 行`, run: async () => {
        for (const id of newIds) await deleteBomEdge(props.token, id)
        await refreshTreeOnly(props.token, props.rootId)
      } })
      flash(`已挂载 ${n} 个子件到「${meta.node.name}」，成本已重算`)
    } else if (p.node.edge_id) {
      const edgeId = p.node.edge_id
      const oldParent = p.parentId
      await moveEdge(props.token, edgeId, parentId, props.rootId)
      pushUndo({ label: `撤销移动 ${p.node.name}`, run: async () => {
        await moveBomEdge(props.token, edgeId, oldParent)
        await refreshTreeOnly(props.token, props.rootId)
      } })
      flash(`「${p.node.name}」已移动到「${meta.node.name}」`)
    }
  } catch (err) { fail(err) }
  finally { busy.value = false }
}

async function handleRemove(node: BomNode) {
  const meta = index.value.byKey.get(nodeKey(node))
  if (!node.edge_id || !meta?.parentId) return
  const parentId = meta.parentId
  const detail = await loadEdgeDetail(props.token, parentId, node.edge_id)
  const saved = detail ? ruleFromEdge(detail) : null
  busy.value = true
  try {
    await removeEdge(props.token, parentId, node.edge_id, props.rootId)
    if (saved) pushUndo({ label: `撤销移除 ${node.name}`, run: async () => {
      await createBomEdge(props.token, parentId, saved)
      await refreshTreeOnly(props.token, props.rootId)
    } })
    edgeDetail.value = null; selectedKey.value = ''
    flash(`已移除「${node.name}」`)
  } catch (err) { fail(err) }
  finally { busy.value = false }
}

async function handleSave(rule: BomEdgeRule) {
  const node = selectedNode.value
  const meta = selectedMeta.value
  if (!node?.edge_id || !meta?.parentId) return
  const before = edgeDetail.value ? ruleFromEdge(edgeDetail.value) : null
  busy.value = true
  try {
    await saveEdge(props.token, node.edge_id, meta.parentId, rule, props.rootId)
    if (before) pushUndo({ label: `撤销修改 ${node.name}`, run: async () => {
      await updateBomEdge(props.token, node.edge_id!, before as never)
      await refreshTreeOnly(props.token, props.rootId)
    } })
    edgeDetail.value = await loadEdgeDetail(props.token, meta.parentId, node.edge_id)
    flash(`「${node.name}」规则已保存，祖先卡金额同步更新`)
  } catch (err) { fail(err) }
  finally { busy.value = false }
}

async function doUndo() {
  busy.value = true
  try { const label = await undo(); flash(label ? `已${label}` : '没有可撤销的操作') }
  catch (err) { fail(err) }
  finally { busy.value = false }
}

function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !e.shiftKey && undoStack.value.length) {
    e.preventDefault(); void doUndo()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await refreshItems(props.token)
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="assembler">
    <div class="toolbar">
      <span class="view-tag">拼装模式</span>
      <button class="btn" :disabled="!undoStack.length || busy" @click="doUndo">↶ 撤销 ({{ undoStack.length }})</button>
      <span v-if="busy" class="hint">保存中…</span>
      <template v-if="focusKey">
        <span class="crumbs">{{ crumbs }}</span>
        <button class="btn" @click="focusKey = ''">退出聚焦</button>
      </template>
      <span v-else class="hint">拖物料入库 → 拖卡片换父级 → 双击卡片聚焦深层</span>
      <span v-if="tree" class="total">总成本 <b>¥{{ tree.subtotal }}</b></span>
    </div>
    <p v-if="msg" class="ok-line">{{ msg }}</p>
    <p v-if="errMsg" class="err-line">{{ errMsg }}</p>

    <div class="cols">
      <BomPalette :items="items" />
      <section class="canvas">
        <p class="c-title">拼装画布 <span>最多 4 级 · 灰卡为不可投放</span></p>
        <div v-if="displayRoot">
          <BomNodeCard
            :node="displayRoot" :index="index" :parent-total="displayRoot.subtotal"
            :selected-key="selectedKey"
            @select="handleSelect" @drop="handleDrop" @remove="handleRemove"
            @focus="(k) => { focusKey = k; handleSelect(k, displayRoot!) }"
          />
        </div>
        <div v-else class="c-empty">尚无 BOM 结构，请先从左侧物料库拖入子件，或切到表格视图「一键写入示例机柜 BOM」。</div>
      </section>
      <BomInspector
        :token="token" :node="selectedNode" :edge="edgeDetail" :params="sandbox3d"
        @save="handleSave" @remove="selectedNode && handleRemove(selectedNode)"
      />
    </div>
  </div>
</template>

<style scoped>
.assembler { display: flex; flex-direction: column; gap: 10px; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; background: #eff6ff; border: 1px solid #bfdbfe; padding: 9px 12px; border-radius: 10px; font-size: 12px; }
.view-tag { background: #1d4ed8; color: #fff; padding: 3px 9px; border-radius: 999px; font-size: 11px; }
.btn { font-size: 11px; padding: 5px 10px; border: 1px solid var(--border); background: #fff; border-radius: 7px; cursor: pointer; }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.hint { color: var(--muted); font-size: 11px; }
.crumbs { font-size: 11px; color: #1d4ed8; }
.total { margin-left: auto; font-size: 12px; } .total b { font-size: 14px; color: #b45309; }
.cols { display: grid; grid-template-columns: 210px minmax(0, 1fr) 260px; gap: 12px; align-items: start; }
.canvas { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; min-height: 420px; }
.c-title { margin: 0 0 10px; font-size: 13px; font-weight: 500; }
.c-title span { font-size: 11px; font-weight: 400; color: var(--muted); margin-left: 8px; }
.c-empty { font-size: 12px; color: var(--muted); padding: 40px 12px; text-align: center; line-height: 1.8; }
.ok-line { color: #047857; background: #ecfdf5; padding: 8px 12px; border-radius: 8px; font-size: 12px; margin: 0; }
.err-line { color: var(--err); background: var(--err-soft); padding: 8px 12px; border-radius: 8px; font-size: 12px; margin: 0; }
@media (max-width: 1100px) { .cols { grid-template-columns: 180px minmax(0, 1fr); } .canvas { min-height: 360px; } }
</style>
