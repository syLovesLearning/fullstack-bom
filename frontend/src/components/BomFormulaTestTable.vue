<script setup lang="ts">
import { computed } from 'vue'
import type { BatchRowResult, SheetRow } from '../api/bomFormulaClient'

const props = defineProps<{
  rows: SheetRow[]
  results?: BatchRowResult[] | null
  editable?: boolean
}>()
const emit = defineEmits<{ expected: [index: number, value: string]; remove: [index: number] }>()

const resultMap = computed(() => {
  const map = new Map<number, BatchRowResult>()
  for (const r of props.results ?? []) map.set(r.index, r)
  return map
})

const STATUS_TEXT: Record<string, string> = { pass: '通过', fail: '不通过', no_expect: '仅回显', error: '求值异常' }

const colCount = computed(() => 7 + 1 + (props.results ? 3 : 0) + (props.editable ? 1 : 0))

function diffText(diff: number | null): string {
  if (diff === null) return '—'
  return `${diff > 0 ? '+' : ''}${diff}`
}
</script>

<template>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th><th>H</th><th>W</th><th>D</th><th>T</th><th>base_qty</th><th>qty</th>
          <th>预期</th>
          <template v-if="results"><th>实算</th><th>差额</th><th>状态</th></template>
          <th v-else-if="editable">预期结果</th>
          <th v-if="editable"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.index" :class="resultMap.get(row.index)?.status">
          <td class="idx">{{ row.index }}</td>
          <td>{{ row.env.H }}</td>
          <td>{{ row.env.W }}</td>
          <td>{{ row.env.D }}</td>
          <td>{{ row.env.T }}</td>
          <td>{{ row.env.base_qty ?? 1 }}</td>
          <td>{{ row.env.qty ?? 1 }}</td>
          <td>
            <input
              v-if="editable"
              class="cell-inp"
              type="number"
              step="any"
              :value="row.expected ?? ''"
              placeholder="留空=不判定"
              @change="emit('expected', row.index, ($event.target as HTMLInputElement).value)"
            />
            <span v-else>{{ row.expected ?? '—' }}</span>
          </td>
          <template v-if="results">
            <td class="num">{{ resultMap.get(row.index)?.actual ?? '—' }}</td>
            <td class="num" :class="{ bad: resultMap.get(row.index)?.status === 'fail' }">{{ diffText(resultMap.get(row.index)?.diff ?? null) }}</td>
            <td>
              <span class="st" :class="resultMap.get(row.index)?.status">
                {{ STATUS_TEXT[resultMap.get(row.index)?.status || ''] || '—' }}
              </span>
            </td>
          </template>
          <td v-if="editable">
            <button class="del" title="删除该行" @click="emit('remove', row.index)">✕</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td class="empty" :colspan="colCount">还没有测试数据：下载模板填写后上传，或手工添加一行</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tbl-wrap { max-height: 260px; overflow: auto; border: 1px solid var(--border); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th { position: sticky; top: 0; background: #f8fafc; color: var(--muted); font-weight: 600; padding: 6px 8px; text-align: left; white-space: nowrap; z-index: 1; }
td { padding: 5px 8px; border-top: 1px solid #f1f5f9; color: #0f172a; white-space: nowrap; }
.idx { color: var(--muted); }
.num { font-variant-numeric: tabular-nums; }
.num.bad { color: #d93025; }
tr.fail td { background: #fff5f5; }
tr.pass td { background: #f0fdf4; }
tr.error td { background: #fef2f2; }
.st { font-size: 11px; padding: 1px 7px; border-radius: 999px; }
.st.pass { background: #dcfce7; color: #15803d; }
.st.fail { background: #fee2e2; color: #b91c1c; }
.st.no_expect { background: #e2e8f0; color: #475569; }
.st.error { background: #fde68a; color: #92400e; }
.cell-inp { width: 96px; padding: 3px 6px; border: 1px solid var(--border); border-radius: 5px; font-size: 12px; }
.empty { text-align: center; color: var(--muted); padding: 18px; }
.del { border: none; background: transparent; color: #94a3b8; cursor: pointer; font-size: 12px; }
.del:hover { color: #d93025; }
</style>
