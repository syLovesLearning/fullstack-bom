<script setup lang="ts">
import { computed } from 'vue'
import type { BomNode, BomRollupResponse } from '../api/bomTypes'

const props = defineProps<{ rollup: BomRollupResponse | null; marginPct: number; taxPct: number }>()

const stats = computed(() => {
  const root = props.rollup?.root
  if (!root) return null
  let nodes = 0, maxDepth = 1, errCnt = 0, scrapTotal = 0
  const walk = (n: BomNode, depth: number) => {
    nodes += 1
    if (depth > maxDepth) maxDepth = depth
    if (n.formula_error) errCnt += 1
    if (n.scrap_qty && n.base_price) scrapTotal += n.scrap_qty * n.base_price
    for (const c of n.children || []) walk(c, depth + 1)
  }
  walk(root, 1)
  const cost = root.subtotal || 0
  const finalPrice = Math.round(cost * (1 + props.marginPct / 100) * (1 + props.taxPct / 100) * 100) / 100
  const matPct = cost ? Math.round(((props.rollup?.bom_summary['材料'] || 0) / cost) * 100) : 0
  const labPct = cost ? Math.round(((props.rollup?.bom_summary['人工'] || 0) / cost) * 100) : 0
  const macPct = Math.max(0, 100 - matPct - labPct)
  return { nodes, maxDepth, errCnt, scrapTotal: Math.round(scrapTotal * 100) / 100, cost, finalPrice, matPct, labPct, macPct }
})
</script>

<template>
  <div v-if="stats" class="health-bar">
    <div class="kpi"><span>零件节点</span><strong>{{ stats.nodes }} 个</strong></div>
    <div class="kpi"><span>递归层级</span><strong>{{ stats.maxDepth }} 级</strong></div>
    <div class="kpi" :class="{ warn: stats.errCnt > 0 }"><span>公式异常</span><strong>{{ stats.errCnt }} 项</strong></div>
    <div class="kpi"><span>余料损耗额</span><strong>¥{{ stats.scrapTotal }}</strong></div>
    <div class="kpi"><span>直接成本 → 含税报价</span><strong class="price">¥{{ stats.cost }} → ¥{{ stats.finalPrice }}</strong></div>
    <div class="ratio-box">
      <div class="ratio-lbl">料 {{ stats.matPct }}% · 工 {{ stats.labPct }}% · 机 {{ stats.macPct }}%</div>
      <div class="ratio-track">
        <div class="seg mat" :style="{ width: stats.matPct + '%' }"></div>
        <div class="seg lab" :style="{ width: stats.labPct + '%' }"></div>
        <div class="seg mac" :style="{ width: stats.macPct + '%' }"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.health-bar { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; background: var(--card); border: 1px solid var(--border); padding: 10px 14px; border-radius: 10px; font-size: 12px; }
.kpi { display: flex; flex-direction: column; gap: 2px; padding-right: 12px; border-right: 1px solid var(--border); }
.kpi span { font-size: 11px; color: var(--muted); }
.kpi.warn strong { color: #dc2626; }
.price { color: #1d4ed8; }
.ratio-box { flex: 1; min-width: 180px; }
.ratio-lbl { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
.ratio-track { height: 8px; border-radius: 999px; background: #e2e8f0; display: flex; overflow: hidden; }
.seg.mat { background: #3b82f6; }
.seg.lab { background: #10b981; }
.seg.mac { background: #f59e0b; }
</style>
