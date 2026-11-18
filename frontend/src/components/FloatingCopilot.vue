<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import {
  createSession,
  listSessionMessages,
  listSessions,
  updateWorkflowStatus,
  type ActionCardItem,
  type MessageItem,
} from '../api/client'
import { useAgentStream } from '../composables/useAgentStream'
import { useMemories } from '../composables/useMemories'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{ openFullChat: []; goWorkflow: [] }>()

const isOpen = ref(false)
const sessionId = ref('')
const messages = ref<MessageItem[]>([])
const input = ref('')
const bodyEl = ref<HTMLElement | null>(null)

const { streaming, answer, statusText, actionCards, streamChat } = useAgentStream()
const { memories, refreshMemories } = useMemories()

async function ensureSession() {
  if (!props.token) return
  const list = await listSessions(props.token)
  if (list.length > 0) {
    sessionId.value = list[0].id
    messages.value = await listSessionMessages(props.token, sessionId.value)
  } else {
    const created = await createSession(props.token, '右下角悬浮助手')
    sessionId.value = created.id
    messages.value = []
  }
}

async function sendQuick(promptText?: string) {
  const q = (promptText ?? input.value).trim()
  if (!q || streaming.value) return
  if (!sessionId.value) await ensureSession()
  input.value = ''
  messages.value.push({ role: 'user', content: q })
  await nextTick(() => bodyEl.value?.scrollTo({ top: bodyEl.value.scrollHeight }))

  await streamChat(props.token, sessionId.value, q, {
    max_steps: 6,
    top_k: 3,
    min_score: 0.2,
    enable_rag: true,
  })
  messages.value.push({
    role: 'assistant',
    content: answer.value || '已完成处理。',
    action_cards: actionCards.value.length ? [...actionCards.value] : undefined,
  })
  await refreshMemories(props.token)
  await nextTick(() => bodyEl.value?.scrollTo({ top: bodyEl.value.scrollHeight, behavior: 'smooth' }))
}

async function handleCardDecision(card: ActionCardItem, status: 'approved' | 'rejected') {
  if (!card.id) return
  await updateWorkflowStatus(props.token, card.id, status, 'chat_card')
  card.status = status
}

watch(() => props.token, () => {
  ensureSession()
  refreshMemories(props.token)
})

onMounted(() => {
  ensureSession()
  refreshMemories(props.token)
})
</script>

<template>
  <div class="copilot-root">
    <button class="fab-btn" @click="isOpen = !isOpen">
      <span>✦ AI 助手</span>
      <span class="mem-pill">记忆 {{ memories.length }}</span>
    </button>

    <aside v-if="isOpen" class="copilot-win">
      <header class="win-head">
        <div>
          <strong>智能体悬浮副驾</strong>
          <span class="sub-info">已挂载 {{ memories.length }} 条长期记忆</span>
        </div>
        <div class="win-actions">
          <button class="mini-btn" title="切换到完整AI工作台" @click="emit('openFullChat'); isOpen = false">全屏工作台 ↗</button>
          <button class="mini-btn" @click="isOpen = false">✕</button>
        </div>
      </header>

      <div class="quick-bar">
        <button class="chip" @click="sendQuick('帮我发起一条采购测试设备的 OA 审批，金额 6800 元')">⚡ 发起 OA 审批</button>
        <button class="chip" @click="sendQuick('帮我查一下机架式GPU服务器和交换机的库存')">📦 查库存预警</button>
        <button class="chip" @click="sendQuick('记住我的偏好：报价单默认保留 15% 毛利')">◉ 写入长期记忆</button>
      </div>

      <div ref="bodyEl" class="win-body">
        <div v-for="(m, idx) in messages" :key="idx" class="msg-row" :class="m.role">
          <div class="bubble" v-html="renderMarkdown(m.content)"></div>
          <div v-for="(c, cIdx) in m.action_cards || []" :key="cIdx" class="inline-card">
            <template v-if="c.kind === 'workflow'">
              <div class="card-title">📋 {{ c.title }} ({{ c.status }})</div>
              <div class="card-btns" v-if="c.status === 'submitted'">
                <button class="mini-btn ok" @click="handleCardDecision(c, 'approved')">一键通过</button>
                <button class="mini-btn err" @click="handleCardDecision(c, 'rejected')">驳回</button>
                <button class="mini-btn" @click="emit('goWorkflow')">去流程中心</button>
              </div>
            </template>
            <template v-else>
              <div class="card-title">⚠️ 库存预警：{{ c.item_name }} (余 {{ c.stock_qty }}{{ c.unit }})</div>
            </template>
          </div>
        </div>

        <div v-if="streaming" class="msg-row assistant">
          <div class="status-line">{{ statusText || '思考与调用工具中...' }}</div>
          <div class="bubble" v-html="renderMarkdown(answer || '...')"></div>
        </div>
      </div>

      <footer class="win-foot">
        <input
          v-model="input"
          class="chat-inp"
          placeholder="随时提问、查库存、记偏好或直接发起审批流..."
          @keyup.enter="sendQuick()"
        />
        <button class="btn btn-primary" :disabled="streaming" @click="sendQuick()">发送</button>
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.copilot-root { position: fixed; right: 22px; bottom: 22px; z-index: 90; }
.fab-btn {
  display: flex; align-items: center; gap: 8px; padding: 11px 18px; border-radius: 999px;
  background: #2563eb; color: #fff; border: none; font-weight: 600; cursor: pointer;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
}
.mem-pill { background: rgba(255, 255, 255, 0.2); padding: 2px 8px; border-radius: 999px; font-size: 11px; }
.copilot-win {
  position: absolute; right: 0; bottom: 54px; width: 390px; height: 540px;
  background: var(--card); border: 1px solid var(--border); border-radius: 14px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18); display: flex; flex-direction: column; overflow: hidden;
}
.win-head { padding: 11px 14px; background: #0f172a; color: #f8fafc; display: flex; justify-content: space-between; align-items: center; }
.sub-info { display: block; font-size: 11px; color: #94a3b8; }
.win-actions { display: flex; gap: 6px; }
.mini-btn { padding: 4px 8px; font-size: 11px; border-radius: 6px; border: 1px solid #334155; background: #1e293b; color: #e2e8f0; cursor: pointer; }
.mini-btn.ok { background: #059669; border-color: #059669; }
.mini-btn.err { background: #dc2626; border-color: #dc2626; }
.quick-bar { display: flex; gap: 6px; padding: 8px 10px; border-bottom: 1px solid var(--border); overflow-x: auto; background: #f8fafc; }
.chip { white-space: nowrap; font-size: 11px; padding: 4px 8px; border-radius: 999px; border: 1px solid var(--border); background: #fff; cursor: pointer; }
.win-body { flex: 1; padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.msg-row.user { align-self: flex-end; max-width: 85%; }
.msg-row.assistant { align-self: flex-start; max-width: 92%; }
.bubble { padding: 8px 12px; border-radius: 10px; font-size: 13px; line-height: 1.45; background: #f1f5f9; }
.msg-row.user .bubble { background: #2563eb; color: #fff; }
.status-line { font-size: 11px; color: #2563eb; margin-bottom: 4px; }
.inline-card { margin-top: 6px; padding: 8px 10px; border-radius: 8px; border: 1px solid #bfdbfe; background: #eff6ff; font-size: 12px; }
.card-title { font-weight: 600; margin-bottom: 6px; }
.card-btns { display: flex; gap: 6px; }
.win-foot { padding: 10px; border-top: 1px solid var(--border); display: flex; gap: 6px; background: #fff; }
.chat-inp { flex: 1; padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
</style>
