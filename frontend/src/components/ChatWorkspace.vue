<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import {
  createSession,
  deleteSession,
  getRunTrace,
  listSessionMessages,
  listSessions,
  renameSession,
  updateWorkflowStatus,
  type ActionCardItem,
  type ChatDebugOptions,
  type EvalHit,
  type MessageItem,
  type RunTraceResponse,
  type SessionItem,
} from '../api/client'
import { useAgentStream } from '../composables/useAgentStream'
import { useChatSession } from '../composables/useChatSession'
import { useMemories } from '../composables/useMemories'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{ goWorkflow: [] }>()

const { sessions, activeSessionId, messages, ensureSession: ensureSharedSession, selectSession: selectSharedSession } = useChatSession()
const input = ref('')
const isComposing = ref(false)
const streamEl = ref<HTMLElement | null>(null)

const showDebugBar = ref(true)
const debugOpts = ref<ChatDebugOptions>({
  max_steps: 6,
  top_k: 3,
  min_score: 0.2,
  enable_rag: true,
})

const activeCitation = ref<EvalHit | null>(null)
const activeTrace = ref<RunTraceResponse | null>(null)
const activeCardDetail = ref<ActionCardItem | null>(null)
const traceLoading = ref(false)

const {
  streaming,
  answer,
  traces,
  citations,
  actionCards,
  lastRunId,
  errorMsg,
  sendMessage,
  stopStream,
} = useAgentStream()
const { memories, refreshMemories, removeMemory } = useMemories()

function scrollBottom() {
  nextTick(() => {
    if (streamEl.value) streamEl.value.scrollTop = streamEl.value.scrollHeight
  })
}

async function loadSessions() {
  await ensureSharedSession(props.token)
}

async function selectSession(sid: string) {
  await selectSharedSession(props.token, sid)
  scrollBottom()
}

async function handleNewSession() {
  const created = await createSession(props.token, `对话 ${sessions.value.length + 1}`)
  sessions.value.unshift(created)
  await selectSession(created.id)
}

async function handleRename(s: SessionItem) {
  const nextTitle = window.prompt('请输入新的会话标题：', s.title)?.trim()
  if (!nextTitle || nextTitle === s.title) return
  const updated = await renameSession(props.token, s.id, nextTitle)
  s.title = updated.title
}

async function handleDeleteSession(s: SessionItem) {
  await deleteSession(props.token, s.id)
  sessions.value = sessions.value.filter((item) => item.id !== s.id)
  if (activeSessionId.value === s.id) {
    if (sessions.value.length) await selectSession(sessions.value[0].id)
    else await handleNewSession()
  }
}

async function openTraceDrawer(runId: string) {
  traceLoading.value = true
  try {
    activeTrace.value = await getRunTrace(props.token, runId)
  } finally {
    traceLoading.value = false
  }
}

async function handleCardApprove(card: ActionCardItem) {
  if (!card.id || card.status !== 'submitted') return
  try {
    await updateWorkflowStatus(props.token, card.id, 'approved', 'chat_card')
    card.status = 'approved'
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '审批失败（可能已审批）')
  }
}

function onEnter(e: KeyboardEvent) {
  if (e.isComposing || isComposing.value || e.keyCode === 229) return
  e.preventDefault()
  submit()
}

async function submit() {
  const q = input.value.trim()
  if (!q || streaming.value || !activeSessionId.value) return
  input.value = ''
  activeCitation.value = null
  messages.value.push({ role: 'user', content: q })
  const assistantMsg: MessageItem = { role: 'assistant', content: '', citations: [], action_cards: [] }
  messages.value.push(assistantMsg)
  scrollBottom()

  await sendMessage(props.token, activeSessionId.value, q, debugOpts.value)
  assistantMsg.content = answer.value || '（已中止或无文本回复）'
  assistantMsg.citations = [...citations.value]
  assistantMsg.action_cards = [...actionCards.value]
  if (lastRunId.value) assistantMsg.run_id = lastRunId.value
  scrollBottom()
  await refreshMemories(props.token)
}

watch(answer, (val) => {
  const last = messages.value[messages.value.length - 1]
  if (streaming.value && last && last.role === 'assistant') {
    last.content = val
    scrollBottom()
  }
})

async function initWorkspace() {
  sessions.value = []
  messages.value = []
  await Promise.all([loadSessions(), refreshMemories(props.token)])
}

watch([() => messages.value.length, () => traces.value.length, answer, streaming], scrollBottom)
watch(() => props.token, initWorkspace)
onMounted(initWorkspace)
</script>

<template>
  <section class="chat-3col">
    <!-- 左栏：会话管理 -->
    <aside class="sess-aside">
      <div class="aside-head">
        <h3>历史会话</h3>
        <button class="btn btn-primary" @click="handleNewSession">+ 新建</button>
      </div>
      <ul class="sess-list">
        <li
          v-for="s in sessions"
          :key="s.id"
          :class="{ active: s.id === activeSessionId }"
          @click="selectSession(s.id)"
        >
          <div class="sess-row">
            <div class="sess-title">{{ s.title }}</div>
            <div class="sess-ops" @click.stop>
              <button class="icon-btn" title="重命名" @click="handleRename(s)">✎</button>
              <button class="icon-btn err" title="删除会话" @click="handleDeleteSession(s)">✕</button>
            </div>
          </div>
          <div class="sess-time">{{ new Date(s.updated_at).toLocaleTimeString() }}</div>
        </li>
      </ul>
    </aside>

    <!-- 中栏：完整多轮对话 + Action Cards + Trace -->
    <div class="chat-main">
      <div ref="streamEl" class="msg-stream">
        <div v-if="!messages.length" class="empty-chat">
          试试问：“查一下服务器库存”、“查一下最近发起的流程” 或 “发起一个 OA 采购申请”。
        </div>
        <div v-for="(m, idx) in messages" :key="idx" :class="['bubble', m.role]">
          <div class="bubble-head">
            <span class="bubble-role">{{ m.role === 'user' ? '我' : '智能体' }}</span>
            <button
              v-if="m.role === 'assistant' && m.run_id"
              class="trace-btn"
              @click="openTraceDrawer(m.run_id)"
            >
              🔍 Trace 回放
            </button>
          </div>
          <div v-if="m.role === 'user'" class="bubble-text">{{ m.content }}</div>
          <div
            v-else
            class="bubble-md"
            v-html="renderMarkdown(m.content || (streaming ? '思考中...' : ''))"
          />

          <!-- 引用溯源 -->
          <div v-if="m.citations?.length" class="cite-chips">
            <button v-for="c in m.citations" :key="c.index" class="cite-chip" @click="activeCitation = c">
              [{{ c.index }}] {{ c.title }}
            </button>
          </div>

          <!-- 结构化业务动作卡片（流程审批 / 详情 / 跳转 / 库存预警） -->
          <div v-if="m.action_cards?.length" class="cards-wrap">
            <div v-for="(card, ci) in m.action_cards" :key="ci" class="action-card">
              <template v-if="card.kind === 'workflow'">
                <div class="card-info">
                  <span class="badge badge-blue">{{ card.flow_code === 'srm_bidding' ? 'SRM 招标' : 'OA 审批' }}</span>
                  <strong>{{ card.title }}</strong>
                  <span :class="['badge', card.status === 'approved' ? 'badge-ok' : 'badge-muted']">{{ card.status }}</span>
                </div>
                <div class="card-btns">
                  <button
                    class="btn btn-primary"
                    :disabled="card.status !== 'submitted'"
                    @click="handleCardApprove(card)"
                  >
                    {{ card.status === 'approved' ? '✓ 已审批' : '⚡ 一键审批通过' }}
                  </button>
                  <button class="btn" @click="activeCardDetail = card">详情弹窗</button>
                  <button class="btn" @click="emit('goWorkflow')">前往流程中心 →</button>
                </div>
              </template>
              <template v-else-if="card.kind === 'bom_quote'">
                <div class="card-info">
                  <span class="badge badge-blue">BOM 试算报价</span>
                  <strong>{{ card.root_name }}</strong>
                  <span v-if="card.params_3d">
                    {{ card.params_3d.H }}×{{ card.params_3d.W }}×{{ card.params_3d.D }} · 板厚 {{ card.params_3d.T }}mm
                  </span>
                  <span>
                    直接成本 ¥{{ (card.direct_cost ?? 0).toFixed(2) }} · 报价
                    <strong class="quote-price">¥{{ (card.final_price ?? 0).toFixed(2) }}</strong>
                  </span>
                  <span v-if="card.cost_summary" class="quote-breakdown">
                    {{ Object.entries(card.cost_summary).filter(([, v]) => v > 0).map(([k, v]) => `${k} ¥${v.toFixed(2)}`).join(' / ') }}
                  </span>
                </div>
              </template>
              <template v-else>
                <div class="card-info">
                  <span class="badge badge-err">低库存预警</span>
                  <strong>{{ card.item_name }}</strong>
                  <span>当前 {{ card.stock_qty }}{{ card.unit }}（安全库存 {{ card.safety_stock }}{{ card.unit }} · {{ card.warehouse }}）</span>
                </div>
                <div class="card-btns">
                  <button class="btn btn-primary" @click="emit('goWorkflow')">前往发起采购 →</button>
                </div>
              </template>
            </div>
          </div>
        </div>

        <div v-if="streaming" class="msg assistant">
          <div class="msg-head">智能体 · 思考与执行中</div>
          <div class="trace-inline" style="background:#f8fafc;border:1px dashed #cbd5e1;border-radius:8px;padding:6px 10px;margin-bottom:6px;font-size:12px;color:#2563eb;">
            <div v-for="(t, ti) in traces" :key="ti">▸ {{ t.detail }}</div>
            <div v-if="!traces.length">▸ 正在连接智能体推理引擎...</div>
          </div>
          <div class="msg-body" v-html="renderMarkdown(answer || '生成中...')"></div>
        </div>
      </div>

      <p v-if="errorMsg" class="err-box">{{ errorMsg }}</p>

      <div class="debug-bar">
        <button class="toggle-debug" @click="showDebugBar = !showDebugBar">
          {{ showDebugBar ? '▼ 收起调试参数' : '▶ 展开调试参数' }}
        </button>
        <div v-if="showDebugBar" class="debug-controls">
          <label><input v-model="debugOpts.enable_rag" type="checkbox" /> 启用 RAG</label>
          <label>max_steps <input v-model.number="debugOpts.max_steps" type="number" min="1" max="12" class="num-in" /></label>
          <label>top_k <input v-model.number="debugOpts.top_k" type="number" min="1" max="10" class="num-in" /></label>
          <label>min_score <input v-model.number="debugOpts.min_score" type="number" step="0.05" min="0" max="1" class="num-in" /></label>
        </div>
      </div>

      <div class="prompt-bar">
        <input
          v-model="input"
          class="prompt-input"
          placeholder="试试：查一下服务器库存 / 查一下最近的流程 / 发起 SRM 招标..."
          @compositionstart="isComposing = true"
          @compositionend="isComposing = false"
          @keydown.enter="onEnter"
        />
        <button v-if="streaming" class="btn stop-btn" @click="stopStream">停止生成</button>
        <button v-else class="btn btn-primary" @click="submit">发送</button>
      </div>
    </div>

    <!-- 右栏：实时 SSE 轨迹 + 共享记忆列表 -->
    <aside class="right-aside">
      <div class="panel-box">
        <h3>实时调度轨迹 (EventContext)</h3>
        <ul class="trace-list">
          <li v-for="(t, i) in traces" :key="i">
            <span class="badge badge-blue">{{ t.type }}</span>
            <span>{{ t.detail }}</span>
          </li>
        </ul>
        <p v-if="!traces.length" class="empty-tip">发送消息后实时显示推理与工具调用。</p>
      </div>

      <div class="panel-box">
        <div class="aside-head"><h3>我的长期记忆 ({{ memories.length }})</h3></div>
        <ul class="mem-list">
          <li v-for="mem in memories" :key="mem.id" class="mem-item">
            <div class="mem-body">
              <span class="badge badge-muted">{{ mem.memory_type }}</span>
              <span>{{ mem.content }}</span>
            </div>
            <button class="del-btn" @click="removeMemory(token, mem.id)">删除</button>
          </li>
        </ul>
        <p v-if="!memories.length" class="empty-tip">暂无长期记忆，可前往「我的记忆」新增。</p>
      </div>
    </aside>
  </section>

  <!-- 引用原文抽屉 -->
  <div v-if="activeCitation" class="drawer-mask" @click.self="activeCitation = null">
    <aside class="drawer">
      <header class="drawer-head">
        <div>
          <span class="badge badge-blue">引用 [{{ activeCitation.index }}]</span>
          <h3>{{ activeCitation.title }}</h3>
        </div>
        <button class="btn" @click="activeCitation = null">关闭</button>
      </header>
      <div class="drawer-meta">
        <div><strong>文件路径：</strong><code>{{ activeCitation.source_path }}</code></div>
        <div><strong>章节路径：</strong>{{ activeCitation.heading_path }}</div>
        <div><strong>相关度得分：</strong>{{ activeCitation.score }}</div>
      </div>
      <pre class="snippet-pre">{{ activeCitation.snippet }}</pre>
    </aside>
  </div>

  <!-- 流程详情弹窗 -->
  <div v-if="activeCardDetail" class="drawer-mask" @click.self="activeCardDetail = null">
    <aside class="drawer">
      <header class="drawer-head">
        <div>
          <span class="badge badge-blue">{{ activeCardDetail.flow_code }}</span>
          <h3>{{ activeCardDetail.title }}</h3>
        </div>
        <button class="btn" @click="activeCardDetail = null">关闭</button>
      </header>
      <pre class="json-pre">{{ JSON.stringify(activeCardDetail.form_data, null, 2) }}</pre>
    </aside>
  </div>

  <!-- Trace 时间旅行抽屉 -->
  <div v-if="activeTrace || traceLoading" class="drawer-mask" @click.self="activeTrace = null">
    <aside class="drawer">
      <header class="drawer-head">
        <div>
          <span class="badge badge-ok">Trace 时间旅行</span>
          <h3>执行链路详情</h3>
        </div>
        <button class="btn" @click="activeTrace = null">关闭</button>
      </header>
      <p v-if="traceLoading">正在拉取轨迹...</p>
      <template v-else-if="activeTrace">
        <div class="drawer-meta">
          <div><strong>模型：</strong>{{ activeTrace.run.model_name }} · <strong>状态：</strong>{{ activeTrace.run.status }}</div>
          <div><strong>总 Token：</strong>{{ activeTrace.run.total_tokens }} · <strong>总耗时：</strong>{{ activeTrace.run.latency_ms ?? 0 }} ms</div>
        </div>
        <div v-for="(st, i) in activeTrace.steps" :key="i" class="step-card">
          <div class="step-top">
            <span class="badge badge-blue">Step {{ st.step_index }} · {{ st.step_type }}</span>
            <code>{{ st.tool_name || '-' }}</code>
            <span class="step-ms">{{ st.duration_ms ?? 0 }} ms</span>
          </div>
          <div class="step-sub">入参：</div>
          <pre class="json-pre">{{ JSON.stringify(st.input_payload, null, 2) }}</pre>
          <div class="step-sub">输出快照：</div>
          <pre class="json-pre">{{ JSON.stringify(st.output_payload, null, 2) }}</pre>
        </div>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.chat-3col { display: grid; grid-template-columns: 215px 1fr 310px; gap: 14px; height: calc(100vh - 116px); min-height: 540px; }
@media (max-width: 1024px) { .chat-3col { grid-template-columns: 1fr; height: auto; } }
.sess-aside, .chat-main, .panel-box { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
.sess-aside { display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }
.aside-head { display: flex; justify-content: space-between; align-items: center; }
h3 { margin: 0; font-size: 13px; color: var(--muted); }
.sess-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.sess-list li { padding: 8px 10px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; }
.sess-list li:hover { background: #f9fafb; }
.sess-list li.active { background: var(--primary-soft); border-color: var(--primary); }
.sess-row { display: flex; justify-content: space-between; align-items: center; gap: 4px; }
.sess-title { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sess-ops { display: flex; gap: 2px; }
.icon-btn { border: none; background: transparent; cursor: pointer; font-size: 12px; color: var(--muted); padding: 2px 4px; }
.icon-btn.err:hover { color: var(--err); }
.sess-time { font-size: 11px; color: var(--muted); margin-top: 2px; }

.chat-main { display: flex; flex-direction: column; gap: 8px; overflow: hidden; }
.msg-stream { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding-right: 4px; }
.empty-chat { margin: auto; color: var(--muted); font-size: 13px; }
.bubble { padding: 10px 14px; border-radius: 10px; max-width: 92%; }
.bubble.user { align-self: flex-end; background: var(--primary-soft); }
.bubble.assistant { align-self: flex-start; background: #f9fafb; border: 1px solid var(--border); width: 100%; }
.bubble-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.bubble-role { font-size: 11px; color: var(--muted); }
.trace-btn { border: 1px solid var(--border); background: #fff; font-size: 11px; padding: 2px 8px; border-radius: 6px; cursor: pointer; color: var(--primary); }
.bubble-text { white-space: pre-wrap; line-height: 1.55; font-size: 14px; }
.bubble-md { font-size: 14px; line-height: 1.6; }
.bubble-md :deep(p) { margin: 0 0 8px; }
.bubble-md :deep(p:last-child) { margin-bottom: 0; }
.bubble-md :deep(pre.md-pre) { border-radius: 8px; overflow-x: auto; padding: 10px 12px; margin: 8px 0; font-size: 12px; }

.cards-wrap { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.action-card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.card-info { display: flex; align-items: center; gap: 8px; font-size: 13px; flex-wrap: wrap; }
.card-btns { display: flex; gap: 6px; flex-wrap: wrap; }
.quote-price { color: #d93025; font-size: 15px; }
.quote-breakdown { color: var(--muted); font-size: 12px; width: 100%; }

.debug-bar { border-top: 1px solid var(--border); padding-top: 6px; font-size: 12px; color: var(--muted); }
.toggle-debug { border: none; background: transparent; color: var(--muted); cursor: pointer; padding: 0; font-size: 12px; }
.debug-controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-top: 6px; }
.num-in { width: 54px; padding: 2px 6px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; }
.prompt-bar { display: flex; gap: 8px; }
.prompt-input { flex: 1; padding: 9px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }
.stop-btn { background: var(--err); border-color: var(--err); color: #fff; }

.right-aside { display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
.panel-box { display: flex; flex-direction: column; gap: 8px; }
.trace-list, .mem-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; font-size: 12px; }
.trace-list li { display: flex; align-items: flex-start; gap: 6px; word-break: break-word; }
.mem-item { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; border-top: 1px solid var(--border); padding-top: 8px; }
.mem-body { display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
.del-btn { border: 1px solid var(--border); background: #fff; color: var(--err); border-radius: 6px; padding: 2px 8px; font-size: 11px; cursor: pointer; flex-shrink: 0; }
.empty-tip { font-size: 12px; color: var(--muted); margin: 0; }
.err-box { background: var(--err-soft); color: var(--err); padding: 8px 10px; border-radius: 8px; margin: 0; font-size: 12px; }
.cite-chips { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.cite-chip { border: 1px solid var(--primary); background: #fff; color: var(--primary); padding: 2px 8px; border-radius: 999px; font-size: 11px; cursor: pointer; }

.drawer-mask { position: fixed; inset: 0; background: rgba(17, 24, 39, 0.35); display: flex; justify-content: flex-end; z-index: 50; }
.drawer { width: min(500px, 94vw); height: 100%; background: var(--card); padding: 20px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
.drawer-head { display: flex; justify-content: space-between; align-items: flex-start; }
.drawer-head h3 { margin: 6px 0 0; font-size: 17px; color: var(--text); }
.drawer-meta { background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
.snippet-pre, .json-pre { margin: 0; white-space: pre-wrap; word-break: break-word; line-height: 1.5; background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 10px; font-size: 12px; }
.step-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
.step-top { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.step-ms { margin-left: auto; color: var(--muted); }
.step-sub { font-size: 12px; color: var(--muted); font-weight: 500; }
</style>
