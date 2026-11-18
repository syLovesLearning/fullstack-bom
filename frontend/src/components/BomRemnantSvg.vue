<script setup lang="ts">
import { computed } from 'vue'
import type { BomNode } from '../api/bomTypes'

const props = defineProps<{ root?: BomNode }>()

const remnantNode = computed(() => {
  const walk = (n: BomNode | undefined): BomNode | null => {
    if (!n) return null
    if (n.remnant_policy && n.remnant_policy !== 'CONTINUOUS' && (n.unit_pack_size || 0) > 1) return n
    for (const c of n.children || []) { const hit = walk(c); if (hit) return hit }
    return null
  }
  return walk(props.root)
})

const metrics = computed(() => {
  const n = remnantNode.value
  if (!n) return null
  const pack = n.unit_pack_size || 1
  const raw = n.raw_qty ?? n.qty
  const remInPack = raw % pack
  const usedInLast = remInPack === 0 && raw > 0 ? pack : remInPack
  const usedPct = Math.min(100, Math.round((usedInLast / pack) * 100))
  const scrapPct = n.scrap_qty ? Math.max(0, 100 - usedPct) : 0
  const keepPct = n.scrap_qty ? 0 : Math.max(0, 100 - usedPct)
  return { name: n.name, unit: n.unit, pack, raw, scrap: n.scrap_qty || 0, note: n.remnant_note || '整料开料', usedPct, scrapPct, keepPct }
})
</script>

<template>
  <div v-if="metrics" class="rem-card">
    <div class="rem-head">
      <strong>2D 整料开料示意图 · {{ metrics.name }} (整料 {{ metrics.pack }}{{ metrics.unit }})</strong>
      <span class="badge badge-blue">{{ metrics.note }}</span>
    </div>
    <svg viewBox="0 0 600 44" class="rem-svg">
      <rect x="0" y="6" :width="metrics.usedPct * 6" height="32" rx="4" fill="#3b82f6" />
      <rect v-if="metrics.scrapPct > 0" :x="metrics.usedPct * 6" y="6" :width="metrics.scrapPct * 6" height="32" rx="4" fill="#ef4444" />
      <rect v-if="metrics.keepPct > 0" :x="metrics.usedPct * 6" y="6" :width="metrics.keepPct * 6" height="32" rx="4" fill="#10b981" />
      <text x="10" y="26" fill="#fff" font-size="12">有效用料 {{ metrics.raw }}{{ metrics.unit }} ({{ metrics.usedPct }}%)</text>
      <text v-if="metrics.scrapPct > 0" :x="Math.min(460, metrics.usedPct * 6 + 6)" y="26" fill="#fff" font-size="11">报废 {{ metrics.scrap }}{{ metrics.unit }}</text>
      <text v-if="metrics.keepPct > 0" :x="Math.min(460, metrics.usedPct * 6 + 6)" y="26" fill="#fff" font-size="11">可留库余料</text>
    </svg>
  </div>
</template>

<style scoped>
.rem-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; }
.rem-head { display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 6px; flex-wrap: wrap; gap: 6px; }
.rem-svg { width: 100%; height: 44px; display: block; }
</style>
