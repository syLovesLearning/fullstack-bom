import { ref } from 'vue'
import { createMemory, deleteMemory, listMemories, type MemoryItem } from '../api/client'

const memories = ref<MemoryItem[]>([])
const loading = ref(false)

export function useMemories() {
  async function refreshMemories(token: string) {
    if (!token) return
    loading.value = true
    try {
      memories.value = await listMemories(token)
    } finally {
      loading.value = false
    }
  }

  async function addMemory(
    token: string,
    type: 'fact' | 'preference' | 'summary',
    content: string,
    importance = 4,
  ) {
    await createMemory(token, type, content, importance)
    await refreshMemories(token)
  }

  async function removeMemory(token: string, id: string) {
    await deleteMemory(token, id)
    memories.value = memories.value.filter((m) => m.id !== id)
  }

  return { memories, loading, refreshMemories, addMemory, removeMemory }
}
