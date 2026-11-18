<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  fetchEvalCases,
  runEvalSuite,
  seedEvalDocs,
  type EvalCase,
  type EvalCaseResult,
  type EvalRunResponse,
} from '../api/client'

const props = defineProps<{ token: string }>()

const cases = ref<EvalCase[]>([])
const runResult = ref<EvalRunResponse | null>(null)
const running = ref(false)
const seeding = ref(false)
const statusMsg = ref('')
const expandedId = ref<string | null>(null)

const resultMap = computed(() => {
  const map = new Map<string, EvalCaseResult>()
  for (const r of runResult.value?.results ?? []) {
    map.set(r.id, r)
  }
  return map
})

async function loadCases() {
  cases.value = await fetchEvalCases(props.token)
}

async function handleSeed() {
  seeding.value = true
  statusMsg.value = ''
  try {
    await seedEvalDocs(props.token)
    statusMsg.value = '示例研发文档已增量入库至 PostgreSQL'
  } finally {
    seeding.value = false
  }
}

async function handleRun() {
  running.value = true
  statusMsg.value = ''
  try {
    runResult.value = await runEvalSuite(props.token, true)
    statusMsg.value = `评测完成：${runResult.value.summary.passed} / ${runResult.value.summary.total} 通过`
  } finally {
    running.value = false
  }
}

onMounted(loadCases)
</script>

<template>
  <section class="eval-panel">
    <header class="panel-head">
      <div>
        <h2>RAG 黄金测试集控制台 (eval/golden_qa.json)</h2>
        <p class="sub">页面直接加载测试集并驱动后端混合检索（pgvector + BM25 + RRF + Rerank），实时量化评估召回质量。</p>
      </div>
      <div class="actions">
        <button class="btn" :disabled="seeding" @click="handleSeed">
          {{ seeding ? '入库中...' : '初始化示例知识库' }}
        </button>
        <button class="btn btn-primary" :disabled="running" @click="handleRun">
          {{ running ? '正在运行评测...' : '一键运行测试集' }}
        </button>
      </div>
    </header>

    <p v-if="statusMsg" class="status-tip">{{ statusMsg }}</p>

    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">用例总数</span>
        <strong class="kpi-val">{{ cases.length }}</strong>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">通过数</span>
        <strong class="kpi-val">{{ runResult ? `${runResult.summary.passed} / ${runResult.summary.total}` : '--' }}</strong>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Hit Rate@3</span>
        <strong class="kpi-val">{{ runResult ? `${(runResult.summary.hit_rate_at_3 * 100).toFixed(0)}%` : '--' }}</strong>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">MRR</span>
        <strong class="kpi-val">{{ runResult ? runResult.summary.mrr : '--' }}</strong>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">平均耗时</span>
        <strong class="kpi-val">{{ runResult ? `${runResult.summary.avg_latency_ms} ms` : '--' }}</strong>
      </div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>分类</th>
            <th>测试问题</th>
            <th>期望来源 &amp; 关键词</th>
            <th>状态</th>
            <th>排名 / 耗时</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="item in cases" :key="item.id">
            <tr>
              <td><code>{{ item.id }}</code></td>
              <td><span class="badge badge-blue">{{ item.category }}</span></td>
              <td class="q-col">{{ item.question }}</td>
              <td>
                <div class="expected-src">{{ item.expected_source }}</div>
                <div class="kw-list">
                  <span v-for="kw in item.expected_keywords" :key="kw" class="kw">{{ kw }}</span>
                </div>
              </td>
              <td>
                <span v-if="!resultMap.get(item.id)" class="badge badge-muted">待运行</span>
                <span v-else-if="resultMap.get(item.id)?.passed" class="badge badge-ok">通过</span>
                <span v-else class="badge badge-err">未命中</span>
              </td>
              <td>
                <template v-if="resultMap.get(item.id)">
                  Rank {{ resultMap.get(item.id)?.rank || '-' }} · {{ resultMap.get(item.id)?.latency_ms }}ms
                </template>
                <template v-else>--</template>
              </td>
              <td>
                <button
                  v-if="resultMap.get(item.id)?.top_hit"
                  class="btn"
                  @click="expandedId = expandedId === item.id ? null : item.id"
                >
                  {{ expandedId === item.id ? '收起' : '查看召回' }}
                </button>
              </td>
            </tr>
            <tr v-if="expandedId === item.id && resultMap.get(item.id)?.top_hit" class="expand-row">
              <td colspan="7">
                <div class="hit-box">
                  <div>
                    <strong>Top-1 命中：</strong>{{ resultMap.get(item.id)?.top_hit?.title }}
                    （{{ resultMap.get(item.id)?.top_hit?.heading_path }} · 分数 {{ resultMap.get(item.id)?.top_hit?.score }}）
                  </div>
                  <p class="snippet">{{ resultMap.get(item.id)?.top_hit?.snippet }}</p>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.eval-panel { display: flex; flex-direction: column; gap: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.actions { display: flex; gap: 8px; }
.status-tip { margin: 0; font-size: 13px; color: var(--ok); font-weight: 500; }
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.kpi-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.kpi-label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.kpi-val { font-size: 20px; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: #f9fafb; color: var(--muted); font-weight: 600; }
.q-col { max-width: 280px; font-weight: 500; }
.expected-src { font-family: monospace; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.kw-list { display: flex; gap: 4px; flex-wrap: wrap; }
.kw { background: #f3f4f6; padding: 1px 6px; border-radius: 4px; font-size: 11px; }
.expand-row td { background: #f9fafb; }
.hit-box { font-size: 13px; }
.snippet { margin: 6px 0 0; color: #374151; white-space: pre-wrap; }
</style>
