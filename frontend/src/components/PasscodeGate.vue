<script setup lang="ts">
import { ref } from 'vue'
import { passcodeLogin, type UserInfo } from '../api/client'

const emit = defineEmits<{ authenticated: [auth: { access_token: string; user: UserInfo }] }>()
const passcode = ref('')
const loading = ref(false)
const errMsg = ref('')

async function handleSubmit() {
  const code = passcode.value.trim()
  if (!code || loading.value) return
  loading.value = true
  errMsg.value = ''
  try {
    const auth = await passcodeLogin(code)
    emit('authenticated', auth)
  } catch (err) {
    errMsg.value = err instanceof Error && err.message.includes('401') ? '密钥错误，请确认简历中的联系电话' : '登录失败，请检查后端服务是否已启动'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="gate-wrap">
    <div class="gate-card">
      <div class="gate-badge">3D BOM · Agent + RAG Full-Stack</div>
      <h1>工业智能体与 3D BOM 工作台</h1>
      <p class="gate-sub">请输入作者简历中的个人密钥（联系电话）解锁完整系统体验</p>
      <input
        v-model="passcode"
        type="password"
        class="gate-inp"
        placeholder="请输入访问密钥..."
        @keyup.enter="handleSubmit"
      />
      <p v-if="errMsg" class="gate-err">{{ errMsg }}</p>
      <button class="gate-btn" :disabled="!passcode.trim() || loading" @click="handleSubmit">
        {{ loading ? '验证中...' : '解锁进入系统' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.gate-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #0f172a; padding: 20px; }
.gate-card { width: 380px; max-width: 100%; background: #fff; border-radius: 16px; padding: 28px; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35); display: flex; flex-direction: column; gap: 12px; }
.gate-badge { align-self: flex-start; font-size: 11px; padding: 3px 10px; border-radius: 999px; background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.gate-card h1 { margin: 0; font-size: 20px; color: #0f172a; }
.gate-sub { margin: 0; font-size: 13px; color: #64748b; line-height: 1.5; }
.gate-inp { padding: 11px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; }
.gate-err { margin: 0; color: #dc2626; font-size: 12px; }
.gate-btn { padding: 11px; border: none; border-radius: 8px; background: #2563eb; color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
.gate-btn:disabled { opacity: 0.55; cursor: not-allowed; }
</style>
