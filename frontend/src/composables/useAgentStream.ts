import { ref } from "vue"
import type { ActionCardItem, ChatDebugOptions, EvalHit } from "../api/client"

export interface TraceLog {
  type: string
  detail: string
}

const streaming = ref(false)
const answer = ref("")
const traces = ref<TraceLog[]>([])
const citations = ref<EvalHit[]>([])
const actionCards = ref<ActionCardItem[]>([])
const lastRunId = ref("")
const errorMsg = ref("")
let controller: AbortController | null = null

export function useAgentStream() {
  function stopStream() {
    if (controller) {
      controller.abort()
      controller = null
      streaming.value = false
      traces.value.push({ type: "stopped", detail: "已手动中止生成" })
    }
  }

  async function sendMessage(
    token: string,
    sessionId: string,
    message: string,
    options?: Partial<ChatDebugOptions>,
  ) {
    streaming.value = true
    answer.value = ""
    traces.value = []
    citations.value = []
    actionCards.value = []
    lastRunId.value = ""
    errorMsg.value = ""
    controller = new AbortController()

    try {
      const resp = await fetch(`/api/v1/sessions/${sessionId}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message, ...options }),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) throw new Error(`流式请求失败: HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split("\n\n")
        buffer = frames.pop() ?? ""

        for (const frame of frames) {
          const lines = frame.split("\n")
          const evLine = lines.find((l) => l.startsWith("event:"))
          const dataLine = lines.find((l) => l.startsWith("data:"))
          if (!evLine || !dataLine) continue
          const event = evLine.slice(6).trim()
          const data = JSON.parse(dataLine.slice(5).trim())

          if (event === "thought") {
            const detail = data.step === 0 ? String(data.status) : `第 ${data.step} 步推理中...`
            traces.value.push({ type: "thought", detail })
          } else if (event === "tool_start") {
            traces.value.push({ type: "tool_start", detail: `调用 ${data.tool}(${JSON.stringify(data.args)})` })
          } else if (event === "tool_result") {
            traces.value.push({ type: "tool_result", detail: `${data.tool} 完成 (${data.duration_ms}ms)` })
          } else if (event === "citations") {
            citations.value = data.items ?? []
          } else if (event === "action_cards") {
            actionCards.value.push(...(data.items ?? []))
          } else if (event === "token") {
            answer.value += data.text ?? ""
          } else if (event === "done") {
            lastRunId.value = data.run_id ?? ""
            traces.value.push({ type: "done", detail: `完成 · tokens=${data.total_tokens}, 耗时=${data.latency_ms}ms` })
          } else if (event === "error") {
            errorMsg.value = data.message ?? "未知错误"
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return
      errorMsg.value = err instanceof Error ? err.message : String(err)
    } finally {
      streaming.value = false
      controller = null
    }
  }

  return { streaming, answer, traces, citations, actionCards, lastRunId, errorMsg, sendMessage, stopStream }
}
