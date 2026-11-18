<script setup lang="ts">
/** 可递归的 BOM 节点卡：拖动=移动，底部虚线槽=投放目标，成本与占比就地可见。 */
import { computed, ref } from 'vue'
import type { BomNode } from '../api/bomClient'
import { nodeKey, useBomDrag, type TreeIndex } from '../composables/useBomDrag'

defineOptions({ name: 'BomNodeCard' })
const props = withDefaults(defineProps<{
  node: BomNode
  index: TreeIndex
  parentTotal: number
  selectedKey?: string
  siblings?: BomNode[]
}>(), { selectedKey: '', siblings: () => [] })
const emit = defineEmits<{
  select: [key: string, node: BomNode]
  drop: [targetKey: string]
  remove: [node: BomNode]
  focus: [key: string]
}>()

const { payload, hoverKey, start, end, verdict } = useBomDrag()
const key = computed(() => nodeKey(props.node))
const depth = computed(() => props.index.byKey.get(key.value)?.depth ?? 1)
const expanded = ref(depth.value < 2)
const canDrop = computed(() => ['PRODUCT', 'SEMI_FINISHED'].includes(props.node.category))
const isDragging = computed(() => !!payload.value)
const v = computed(() => verdict(key.value, props.index))
const legal = computed(() => isDragging.value && v.value.ok)
const blocked = computed(() => isDragging.value && !v.value.ok)
const pct = computed(() => props.parentTotal > 0 ? Math.min(100, Math.round(props.node.subtotal / props.parentTotal * 100)) : 0)
const dupCount = computed(() => props.siblings.filter((s) => s.id === props.node.id).length)
const dupTip = computed(() => props.siblings.filter((s) => s.id === props.node.id)
  .map((s) => `${s.qty_mode === 'FORMULA_3D' ? '公式 ' + s.formula_expr : '固定 ' + s.qty} · ¥${s.subtotal}`).join('\n'))
const children = computed(() => props.node.children || [])

function onDragStart(e: DragEvent) {
  if (!props.node.edge_id) return
  const meta = props.index.byKey.get(key.value)
  start({ kind: 'move', node: props.node, parentId: meta?.parentId || '', key: key.value })
  e.dataTransfer?.setData('text/plain', key.value)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
  e.stopPropagation()
}

function onDragOver(e: DragEvent) {
  e.preventDefault(); e.stopPropagation()
  if (e.dataTransfer) e.dataTransfer.dropEffect = legal.value ? 'copy' : 'none'
  hoverKey.value = key.value
}

function onDrop(e: DragEvent) {
  e.preventDefault(); e.stopPropagation()
  hoverKey.value = ''
  if (legal.value) emit('drop', key.value)
}
</script>

<template>
  <div class="node" :class="{ blocked, picked: selectedKey === key, over: legal && hoverKey === key }"
       @click.stop="emit('select', key, node)" @dblclick.stop="emit('focus', key)">
    <div class="head" :draggable="!!node.edge_id" @dragstart="onDragStart" @dragend="end()">
      <span class="grip" title="拖动以更换父级">⋮⋮</span>
      <span class="name">{{ node.name }}</span>
      <span class="sku">{{ node.sku_code }}</span>
      <span v-if="dupCount > 1" class="dup" :title="dupTip">同物料 {{ dupCount }} 行</span>
      <span class="mode" :class="{ formula: node.qty_mode === 'FORMULA_3D' }">
        {{ node.qty_mode === 'FORMULA_3D' ? '公式' : '固定' }}
      </span>
      <span class="cost" :key="node.subtotal">¥{{ node.subtotal }}</span>
      <span class="pct">{{ pct }}%</span>
      <span v-if="pct >= 50 && node.edge_id" class="hot">大头</span>
      <button v-if="node.edge_id" class="rm" title="移除此行" @click.stop="emit('remove', node)">×</button>
    </div>
    <div class="bar"><i :style="{ width: pct + '%' }" /></div>

    <div v-if="children.length" class="fold" @click.stop="expanded = !expanded">
      {{ expanded ? '▾' : '▸' }} {{ children.length }} 个子件{{ expanded ? '' : '（点击展开）' }}
    </div>

    <div v-if="canDrop" class="slot" :class="{ on: legal, off: blocked, hover: hoverKey === key }"
         @dragenter.prevent.stop="hoverKey = key" @dragover="onDragOver" @dragleave.stop="hoverKey = ''" @drop="onDrop">
      <template v-if="!isDragging">＋ 拖入子件</template>
      <template v-else-if="legal">松手挂载到「{{ node.name }}」</template>
      <template v-else>不可投放 · {{ v.reason }}</template>
    </div>

    <div v-if="expanded && children.length" class="children">
      <BomNodeCard
        v-for="(child, i) in children" :key="`${nodeKey(child)}-${i}`"
        :node="child" :index="index" :parent-total="node.subtotal"
        :selected-key="selectedKey" :siblings="children"
        @select="(k, n) => emit('select', k, n)" @drop="(k) => emit('drop', k)"
        @remove="(n) => emit('remove', n)" @focus="(k) => emit('focus', k)"
      />
    </div>
  </div>
</template>

<style scoped>
.node { border: 1px solid var(--border); border-radius: 9px; background: #fff; padding: 8px 10px; margin-bottom: 6px; transition: opacity .15s, border-color .15s; }
.node.picked { border-color: #3b82f6; box-shadow: 0 0 0 2px #dbeafe; }
.node.blocked { opacity: .45; filter: grayscale(1); }
.node.over { border-color: #3b82f6; }
.head { display: flex; align-items: center; gap: 7px; cursor: pointer; font-size: 12px; }
.head[draggable="true"] { cursor: grab; }
.grip { color: #cbd5e1; font-size: 11px; letter-spacing: -2px; }
.name { font-weight: 500; }
.sku { font-size: 11px; color: var(--muted); }
.dup { font-size: 11px; background: #fef3c7; color: #92400e; padding: 1px 6px; border-radius: 999px; cursor: help; }
.mode { font-size: 11px; padding: 1px 6px; border-radius: 5px; background: #f1f5f9; color: #64748b; }
.mode.formula { background: #ede9fe; color: #6d28d9; }
.cost { margin-left: auto; font-weight: 500; animation: pop .25s ease; }
@keyframes pop { from { transform: scale(1.18); color: #1d4ed8; } to { transform: scale(1); } }
.pct { font-size: 11px; color: var(--muted); width: 34px; text-align: right; }
.hot { font-size: 10px; background: #fee2e2; color: #b91c1c; padding: 1px 5px; border-radius: 5px; }
.rm { border: none; background: none; color: #94a3b8; cursor: pointer; font-size: 16px; line-height: 1; padding: 0 2px; }
.rm:hover { color: #dc2626; }
.bar { height: 3px; background: #f1f5f9; border-radius: 2px; margin: 6px 0 5px; overflow: hidden; }
.bar i { display: block; height: 100%; background: #60a5fa; transition: width .25s ease; }
.fold { font-size: 11px; color: #1d4ed8; cursor: pointer; padding: 2px 0 5px; }
.slot { border: 1px dashed #cbd5e1; border-radius: 7px; padding: 6px; text-align: center; font-size: 11px; color: var(--muted); }
.slot.on { border-color: #3b82f6; background: #eff6ff; color: #1d4ed8; }
.slot.off { border-color: #e2e8f0; background: #f8fafc; color: #94a3b8; cursor: not-allowed; }
.slot.hover.on { background: #dbeafe; border-width: 2px; }
.children { padding-left: 14px; border-left: 2px solid #e2e8f0; margin-top: 6px; }
</style>
