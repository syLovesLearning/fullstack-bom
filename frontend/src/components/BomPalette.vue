<script setup lang="ts">
/** 物料库：主表数据的紧凑视图，支持搜索/分类筛选/多选后一次拖入。 */
import { computed, ref } from 'vue'
import type { BomItem } from '../api/bomClient'
import { useBomDrag } from '../composables/useBomDrag'

const props = defineProps<{ items: BomItem[] }>()
const { start, end } = useBomDrag()

const keyword = ref('')
const cat = ref('ALL')
const selected = ref<string[]>([])
const cats = [
  { v: 'ALL', t: '全部' }, { v: 'PRODUCT', t: '成品' }, { v: 'SEMI_FINISHED', t: '半成品' },
  { v: 'BASE_MATERIAL', t: '基材' }, { v: 'OUTSOURCED', t: '外协' }, { v: 'LABOR', t: '人工' }, { v: 'MACHINE', t: '机械' },
]
const catLabel: Record<string, string> = {
  PRODUCT: '成品', SEMI_FINISHED: '半成品', BASE_MATERIAL: '基材',
  OUTSOURCED: '外协', LABOR: '人工', MACHINE: '机械',
}

const filtered = computed(() => props.items.filter((i) =>
  (cat.value === 'ALL' || i.category === cat.value) &&
  (!keyword.value || `${i.sku_code}${i.name}`.toLowerCase().includes(keyword.value.toLowerCase()))))

function toggle(item: BomItem) {
  const idx = selected.value.indexOf(item.id)
  if (idx >= 0) selected.value.splice(idx, 1)
  else selected.value.push(item.id)
}

function onDragStart(e: DragEvent, item: BomItem) {
  const ids = selected.value.includes(item.id) ? [...selected.value] : [item.id]
  const picked = props.items.filter((i) => ids.includes(i.id))
  start({ kind: 'new', items: picked })
  e.dataTransfer?.setData('text/plain', ids.join(','))
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <aside class="palette">
    <div class="p-head">
      <strong>物料库</strong>
      <span class="hint">拖入画布</span>
    </div>
    <input v-model="keyword" class="search" placeholder="搜索 SKU / 名称" />
    <div class="chips">
      <button v-for="c in cats" :key="c.v" class="chip" :class="{ on: cat === c.v }" @click="cat = c.v">{{ c.t }}</button>
    </div>
    <div class="list">
      <div
        v-for="item in filtered" :key="item.id"
        class="mat" :class="{ picked: selected.includes(item.id) }"
        draggable="true"
        @click="toggle(item)"
        @dragstart="onDragStart($event, item)"
        @dragend="end()"
      >
        <div class="mat-top">
          <span class="mat-name">{{ item.name }}</span>
          <span class="mat-price">¥{{ item.base_price }}</span>
        </div>
        <div class="mat-sub">
          <span>{{ item.sku_code }}</span>
          <span>{{ catLabel[item.category] || item.category }} · {{ item.unit }}</span>
        </div>
      </div>
      <p v-if="!filtered.length" class="empty">没有匹配的物料</p>
    </div>
    <p class="foot">
      {{ selected.length ? `已选 ${selected.length} 项，拖动任一项即批量挂载` : '点击可多选，拖动单个也可直接挂载' }}
      <button v-if="selected.length" class="clear" @click="selected = []">清空</button>
    </p>
  </aside>
</template>

<style scoped>
.palette { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px; min-height: 420px; }
.p-head { display: flex; justify-content: space-between; align-items: baseline; font-size: 13px; }
.hint { font-size: 11px; color: var(--muted); }
.search { padding: 7px 9px; border: 1px solid var(--border); border-radius: 7px; font-size: 12px; width: 100%; box-sizing: border-box; background: #fff; }
.chips { display: flex; flex-wrap: wrap; gap: 5px; }
.chip { font-size: 11px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border); background: #fff; color: var(--muted); cursor: pointer; }
.chip.on { background: #dbeafe; border-color: #93c5fd; color: #1d4ed8; }
.list { display: flex; flex-direction: column; gap: 6px; overflow-y: auto; max-height: 340px; flex: 1; }
.mat { border: 1px solid var(--border); border-radius: 8px; padding: 8px 9px; background: #fff; cursor: grab; transition: border-color .15s, background .15s; }
.mat:hover { border-color: #93c5fd; }
.mat.picked { background: #eff6ff; border-color: #3b82f6; }
.mat:active { cursor: grabbing; }
.mat-top { display: flex; justify-content: space-between; gap: 6px; font-size: 12px; }
.mat-name { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mat-price { color: #b45309; flex: none; }
.mat-sub { display: flex; justify-content: space-between; gap: 6px; font-size: 11px; color: var(--muted); margin-top: 3px; }
.empty, .foot { font-size: 11px; color: var(--muted); margin: 0; }
.clear { font-size: 11px; border: none; background: none; color: #1d4ed8; cursor: pointer; padding: 0 0 0 6px; }
</style>
