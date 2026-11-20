<script setup lang="ts">
import { ref } from 'vue'
import { deliverToolDemand } from '../api/roles'
import type { WorkflowItem } from '../api/client'

const props = defineProps<{ token: string; item: WorkflowItem }>()
const emit = defineEmits<{ close: []; delivered: [] }>()

const fd = (props.item.form_data || {}) as Record<string, string>
const devReply = ref(fd.dev_reply || '已完成研发并通过测试，现已挂载上线。')
const deliveryMode = ref<'EXTERNAL_SERVICE' | 'LOCAL_MODULE'>(
  fd.delivery_mode === 'LOCAL_MODULE' ? 'LOCAL_MODULE' : 'EXTERNAL_SERVICE',
)
const menuKey = ref(fd.menu_key || `tool_${props.item.id.slice(0, 6)}`)
const menuTitle = ref(props.item.title || '定制微工具')
const externalUrl = ref(fd.external_url || 'https://example.com')
const targetRoles = ref(fd.target_roles || 'admin,user')
const activateMenu = ref(true)
const saving = ref(false)
const err = ref('')

async function submitDeliver() {
  err.value = ''
  if (!/^[a-z0-9_]{2,40}$/.test(menuKey.value.trim())) {
    err.value = '菜单编码仅支持小写字母、数字和下划线（2-40位）'
    return
  }
  saving.value = true
  try {
    await deliverToolDemand(props.token, props.item.id, {
      dev_reply: devReply.value.trim(),
      delivery_mode: deliveryMode.value,
      menu_key: menuKey.value.trim(),
      menu_title: menuTitle.value.trim(),
      external_url: externalUrl.value.trim(),
      target_roles: targetRoles.value.split(',').map((s) => s.trim()).filter(Boolean),
      activate_menu: activateMenu.value,
    })
    emit('delivered')
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="mask" @click.self="emit('close')">
    <div class="modal">
      <div class="m-head">
        <h3>需求交付与微工具挂载</h3>
        <button class="btn" @click="emit('close')">关闭</button>
      </div>
      <div class="req-box">
        <strong>{{ item.title }}</strong>
        <p>{{ fd.problem_desc }}</p>
      </div>
      <label><span>交付方式</span>
        <select v-model="deliveryMode" class="inp">
          <option value="EXTERNAL_SERVICE">外部微服务挂载 (iframe 地址)</option>
          <option value="LOCAL_MODULE">本地开发更新 (绑定组件菜单)</option>
        </select>
      </label>
      <label><span>研发回复说明</span><textarea v-model="devReply" rows="2" class="inp" /></label>
      <div class="row2">
        <label><span>菜单编码 (menu_key)</span><input v-model="menuKey" class="inp" /></label>
        <label><span>左侧菜单名称</span><input v-model="menuTitle" class="inp" /></label>
      </div>
      <label v-if="deliveryMode === 'EXTERNAL_SERVICE'">
        <span>外部微服务地址 (URL)</span>
        <input v-model="externalUrl" class="inp" placeholder="http://127.0.0.1:5174" />
      </label>
      <label><span>开放角色 (逗号分隔)</span><input v-model="targetRoles" class="inp" /></label>
      <label class="chk"><input v-model="activateMenu" type="checkbox" /> 保存后立即挂载到左侧菜单栏</label>
      <p v-if="err" class="err">{{ err }}</p>
      <div class="acts">
        <button class="btn" @click="emit('close')">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submitDeliver">
          {{ saving ? '挂载中...' : '保存回复并挂载上线' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 60; }
.modal { background: var(--card); border-radius: 12px; padding: 18px; width: min(480px, 92vw); display: flex; flex-direction: column; gap: 10px; }
.m-head, .acts { display: flex; justify-content: space-between; align-items: center; }
.m-head h3 { margin: 0; font-size: 16px; }
.req-box { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 12px; }
.req-box p { margin: 4px 0 0; color: var(--muted); }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.chk { flex-direction: row; align-items: center; color: var(--text); }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.inp { padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; color: var(--text); }
.err { margin: 0; color: var(--err); font-size: 12px; }
</style>
