import { ref } from "vue"
import { createSession, listSessionMessages, listSessions, type MessageItem, type SessionItem } from "../api/client"

const sessions = ref<SessionItem[]>([])
const activeSessionId = ref("")
const messages = ref<MessageItem[]>([])
let loadedToken = ""
let inflight: Promise<string> | null = null

export function useChatSession() {
  async function selectSession(token: string, sid: string) {
    activeSessionId.value = sid
    const rows = await listSessionMessages(token, sid)
    messages.value = rows.filter((m) => m.role === "user" || m.role === "assistant")
  }

  async function ensureSession(token: string, forceRefresh = false): Promise<string> {
    if (!token) return ""
    if (!forceRefresh && loadedToken === token && activeSessionId.value && sessions.value.length) return activeSessionId.value
    if (inflight && !forceRefresh) return inflight

    inflight = (async () => {
      if (loadedToken !== token) {
        activeSessionId.value = ""
        messages.value = []
        loadedToken = token
      }
      sessions.value = await listSessions(token)
      if (!sessions.value.length) {
        const created = await createSession(token, "默认对话")
        sessions.value = [created]
      }
      const targetId = sessions.value.some((s) => s.id === activeSessionId.value) ? activeSessionId.value : sessions.value[0].id
      await selectSession(token, targetId)
      return targetId
    })().finally(() => { inflight = null })
    return inflight
  }

  async function startNewSession(token: string, title = "新对话") {
    const created = await createSession(token, title)
    sessions.value = [created, ...sessions.value]
    activeSessionId.value = created.id
    messages.value = []
    return created
  }

  function resetSessionState() {
    sessions.value = []
    activeSessionId.value = ""
    messages.value = []
    loadedToken = ""
    inflight = null
  }

  return { sessions, activeSessionId, messages, ensureSession, selectSession, startNewSession, resetSessionState }
}
