<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useMemories } from '../composables/useMemories'

const props = defineProps<{ token: string }>()
const { memories, loading, refreshMemories, addMemory, removeMemory } = useMemories()

const memoryType = ref<'fact' | 'preference' | 'summary'>('fact')
const content = ref('')
const importance = ref(4)
const saving = ref(false)

async function handleAdd() {
  if (!content.value.trim()) return
  saving.value = true
  try {
    await addMemory(props.token, memoryType.value, content.value.trim(), importance.value)
    content.value = ''
  } finally {
    saving.value = false
  }
}

onMounted(() => refreshMemories(props.token))
</script>

<template>
  <section class="mem-panel">
    <header class="panel-head">
      <div>
        <h2>用户个人记忆系统 (PostgreSQL memories 表)</h2>
        <p class="sub">当前账号的长期记忆严格按 user_id 隔离，每次对话会自动注入重要度最高的前 5 条；与聊天页实时同步。</p>
      </div>
      <button class="btn" :disabled="loading" @click="refreshMemories(token)">刷新记忆</button>
    </header>

    <div class="add-card">
      <select v-model="memoryType" class="sel">
        <option value="fact">事实 (fact)</option>
        <option value="preference">偏好 (preference)</option>
        <option value="summary">摘要 (summary)</option>
      </select>
      <input v-model="content" class="txt-input" placeholder="输入希望智能体长期记住的事实或偏好..." @keyup.enter="handleAdd" />
      <label class="imp-label">重要度
        <select v-model.number="importance" class="sel">
          <option :value="5">5 (最高)</option>
          <option :value="4">4</option>
          <option :value="3">3</option>
          <option :value="2">2</option>
          <option :value="1">1</option>
        </select>
      </label>
      <button class="btn btn-primary" :disabled="!content.trim() || saving" @click="handleAdd">
        {{ saving ? '写入中...' : '新增记忆' }}
      </button>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>类型</th>
            <th>记忆内容</th>
            <th>重要度</th>
            <th>写入时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in memories" :key="m.id">
            <td><span class="badge badge-blue">{{ m.memory_type }}</span></td>
            <td class="content-col">{{ m.content }}</td>
            <td>★ {{ m.importance }}</td>
            <td>{{ new Date(m.created_at).toLocaleString() }}</td>
            <td>
              <button class="btn" @click="removeMemory(token, m.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!memories.length">
            <td colspan="5" class="empty">暂无长期记忆，可在上方手动添加或在对话中由智能体自动记录。</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.mem-panel { display: flex; flex-direction: column; gap: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.add-card { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; background: var(--card); border: 1px solid var(--border); padding: 12px; border-radius: 10px; }
.sel { padding: 8px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: #fff; }
.txt-input { flex: 1; min-width: 240px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
.imp-label { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 11px 12px; border-bottom: 1px solid var(--border); }
th { background: #f9fafb; color: var(--muted); font-weight: 600; }
.content-col { max-width: 480px; }
.empty { text-align: center; color: var(--muted); padding: 24px; }
</style>
