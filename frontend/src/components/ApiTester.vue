<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ token: string; sessionId: string }>()

interface ApiCase {
  id: string
  name: string
  method: 'GET' | 'POST' | 'DELETE'
  path: string
  body?: unknown
  status?: number
  passed?: boolean
  latencyMs?: number
  responsePreview?: string
}

const running = ref(false)
const cleanupMsg = ref('')
const cases = ref<ApiCase[]>([
  { id: 'API-01', name: '健康检查', method: 'GET', path: '/health' },
  { id: 'API-02', name: '获取当前登录身份', method: 'GET', path: '/api/v1/auth/me' },
  { id: 'API-03', name: '获取可用工具列表 (权限裁剪)', method: 'GET', path: '/api/v1/tools' },
  { id: 'API-04', name: '获取会话列表', method: 'GET', path: '/api/v1/sessions' },
  {
    id: 'API-05',
    name: '写入一条长期记忆',
    method: 'POST',
    path: '/api/v1/memories',
    body: { memory_type: 'preference', content: '接口测试：临时记忆', importance: 4 },
  },
  { id: 'API-06', name: '查询长期记忆列表', method: 'GET', path: '/api/v1/memories' },
  {
    id: 'API-07',
    name: '增量入库测试文档',
    method: 'POST',
    path: '/api/v1/docs/ingest',
    body: {
      title: 'API 测试文档',
      source_path: 'docs/api_test.md',
      category: 'test',
      content: '# API 测试\n\n## 验证\n接口自检测试切片，包含 pgvector 检索验证。',
    },
  },
  { id: 'API-08', name: '查看已入库文档列表', method: 'GET', path: '/api/v1/docs' },
  {
    id: 'API-09',
    name: 'RAG 独立检索调试',
    method: 'POST',
    path: '/api/v1/docs/search',
    body: { query: 'pgvector 检索验证', category: 'test', top_k: 2 },
  },
  { id: 'API-10', name: '拉取黄金测试集列表', method: 'GET', path: '/api/v1/eval/cases' },
])

let createdMemoryId = ''
let createdDocId = ''

async function runSingle(item: ApiCase) {
  const t0 = performance.now()
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (item.path !== '/health') headers.Authorization = `Bearer ${props.token}`
    const resp = await fetch(item.path, {
      method: item.method,
      headers,
      body: item.body ? JSON.stringify(item.body) : undefined,
    })
    const text = await resp.text()
    item.status = resp.status
    item.passed = resp.ok
    item.latencyMs = Math.round(performance.now() - t0)
    item.responsePreview = text.slice(0, 260)

    if (resp.ok && item.id === 'API-05') {
      createdMemoryId = JSON.parse(text).id ?? ''
    } else if (resp.ok && item.id === 'API-07') {
      createdDocId = JSON.parse(text).document_id ?? ''
    }
  } catch (err) {
    item.status = 0
    item.passed = false
    item.latencyMs = Math.round(performance.now() - t0)
    item.responsePreview = err instanceof Error ? err.message : String(err)
  }
}

async function runAll() {
  running.value = true
  cleanupMsg.value = ''
  createdMemoryId = ''
  createdDocId = ''
  try {
    for (const item of cases.value) {
      await runSingle(item)
    }
    const headers = { Authorization: `Bearer ${props.token}` }
    if (createdMemoryId) await fetch(`/api/v1/memories/${createdMemoryId}`, { method: 'DELETE', headers })
    if (createdDocId) await fetch(`/api/v1/docs/${createdDocId}`, { method: 'DELETE', headers })
    if (createdMemoryId || createdDocId) {
      cleanupMsg.value = '全量测试完成，已自动清理本轮产生的临时记忆与测试文档。'
    }
  } finally {
    running.value = false
  }
}
</script>

<template>
  <section class="api-panel">
    <header class="panel-head">
      <div>
        <h2>后端接口自动化测试台</h2>
        <p class="sub">覆盖鉴权、工具权限、记忆持久化、知识库入库与混合检索，全量跑完后自动清理临时测试数据。</p>
      </div>
      <button class="btn btn-primary" :disabled="running" @click="runAll">
        {{ running ? '正在执行测试...' : '一键全量测试 API' }}
      </button>
    </header>

    <p v-if="cleanupMsg" class="ok-tip">{{ cleanupMsg }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>用例</th>
            <th>方法 &amp; 路径</th>
            <th>状态</th>
            <th>耗时</th>
            <th>响应预览</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in cases" :key="c.id">
            <td>
              <div><code>{{ c.id }}</code></div>
              <div class="case-name">{{ c.name }}</div>
            </td>
            <td>
              <span class="badge badge-blue">{{ c.method }}</span>
              <code class="path">{{ c.path }}</code>
            </td>
            <td>
              <span v-if="c.status === undefined" class="badge badge-muted">未运行</span>
              <span v-else-if="c.passed" class="badge badge-ok">{{ c.status }} OK</span>
              <span v-else class="badge badge-err">{{ c.status }} FAIL</span>
            </td>
            <td>{{ c.latencyMs !== undefined ? `${c.latencyMs} ms` : '--' }}</td>
            <td class="preview-col"><code>{{ c.responsePreview || '--' }}</code></td>
            <td><button class="btn" :disabled="running" @click="runSingle(c)">单测</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.api-panel { display: flex; flex-direction: column; gap: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.ok-tip { margin: 0; color: var(--ok); font-size: 13px; font-weight: 500; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: #f9fafb; color: var(--muted); font-weight: 600; }
.case-name { font-weight: 500; margin-top: 2px; }
.path { margin-left: 6px; font-size: 12px; }
.preview-col { max-width: 340px; word-break: break-all; font-size: 12px; color: #374151; }
</style>
