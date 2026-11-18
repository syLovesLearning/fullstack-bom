<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchAllMenus, fetchWorkflowSkills, type SysMenuItem, type WorkflowSkill } from '../api/client'
import { deleteRole, fetchRoles, fetchToolsCatalog, upsertRole, type SysRoleItem, type ToolCatalogItem } from '../api/roles'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{ rolesUpdated: [] }>()

const roles = ref<SysRoleItem[]>([])
const tools = ref<ToolCatalogItem[]>([])
const menus = ref<SysMenuItem[]>([])
const workflows = ref<WorkflowSkill[]>([])
const activeCode = ref('admin')
const showNew = ref(false)
const newCode = ref('')
const newName = ref('')
const newDesc = ref('')
const saving = ref(false)
const msg = ref('')
const errMsg = ref('')

const activeRole = computed(() => roles.value.find((r) => r.role_code === activeCode.value) || null)
const linkedMenus = computed(() => menus.value.filter((m) => m.allowed_roles.includes(activeCode.value)))
const linkedFlows = computed(() => workflows.value.filter((w) => w.allowed_roles.includes(activeCode.value)))

async function loadAll() {
  errMsg.value = ''
  try {
    const [rList, tList, mList, wList] = await Promise.all([
      fetchRoles(props.token),
      fetchToolsCatalog(props.token),
      fetchAllMenus(props.token).catch(() => []),
      fetchWorkflowSkills(props.token).catch(() => []),
    ])
    roles.value = rList
    tools.value = tList
    menus.value = mList
    workflows.value = wList
    if (rList.length && !rList.some((r) => r.role_code === activeCode.value)) activeCode.value = rList[0].role_code
  } catch (err) {
    errMsg.value = err instanceof Error ? err.message : String(err)
  }
}
function toggleTool(toolName: string) {
  if (!activeRole.value) return
  const list = activeRole.value.allowed_tools
  const idx = list.indexOf(toolName)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(toolName)
}
async function saveCurrent() {
  if (!activeRole.value) return
  saving.value = true
  msg.value = ''
  errMsg.value = ''
  try {
    const saved = await upsertRole(props.token, {
      role_code: activeRole.value.role_code,
      role_name: activeRole.value.role_name,
      description: activeRole.value.description,
      allowed_tools: activeRole.value.allowed_tools,
    })
    const idx = roles.value.findIndex((r) => r.role_code === saved.role_code)
    if (idx >= 0) roles.value[idx] = saved
    msg.value = `已保存角色「${saved.role_name}」，AI 聊天框接口权限已实时生效。`
    emit('rolesUpdated')
  } catch (err) {
    errMsg.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}
async function createRole() {
  errMsg.value = ''
  const code = newCode.value.trim().toLowerCase()
  if (!/^[a-z0-9_]{2,40}$/.test(code)) {
    errMsg.value = '角色编码仅支持小写字母、数字和下划线（2-40位）'
    return
  }
  try {
    const created = await upsertRole(props.token, {
      role_code: code,
      role_name: newName.value.trim() || code,
      description: newDesc.value.trim(),
      allowed_tools: ['rag_search'],
    })
    roles.value.push(created)
    activeCode.value = created.role_code
    newCode.value = ''; newName.value = ''; newDesc.value = ''; showNew.value = false
    msg.value = `已新建角色「${created.role_name}」，请在右侧勾选允许它在 AI 聊天框中发起的接口。`
    emit('rolesUpdated')
  } catch (err) {
    errMsg.value = err instanceof Error ? err.message : String(err)
  }
}
async function removeRole() {
  if (!activeRole.value || activeRole.value.is_system) return
  try {
    await deleteRole(props.token, activeRole.value.role_code)
    roles.value = roles.value.filter((r) => r.role_code !== activeRole.value?.role_code)
    activeCode.value = roles.value[0]?.role_code || 'admin'
    msg.value = '已删除自定义角色。'
    emit('rolesUpdated')
  } catch (err) {
    errMsg.value = err instanceof Error ? err.message : String(err)
  }
}
onMounted(loadAll)
</script>
<template>
  <section class="role-page">
    <header class="head">
      <div>
        <h2>角色与 AI 能力权限管理 (sys_roles)</h2>
        <p class="sub">为不同角色挂载允许在 AI 聊天框中调用的接口，保存后无需重新登录即可实时生效；顶部预览角色可一键切换体验。</p>
      </div>
      <div class="acts">
        <button class="btn" @click="showNew = !showNew">{{ showNew ? '取消新建' : '+ 新建角色' }}</button>
        <button class="btn" @click="loadAll">刷新</button>
      </div>
    </header>

    <p v-if="msg" class="ok-bar">{{ msg }}</p>
    <p v-if="errMsg" class="err-bar">{{ errMsg }}</p>

    <div v-if="showNew" class="new-box">
      <input v-model="newCode" class="inp" placeholder="角色编码 (如 sales_rep)" />
      <input v-model="newName" class="inp" placeholder="角色名称 (如 销售报价专员)" />
      <input v-model="newDesc" class="inp" placeholder="职责说明" style="flex: 1" />
      <button class="btn btn-primary" @click="createRole">创建角色</button>
    </div>

    <div class="grid">
      <aside class="role-list">
        <button v-for="r in roles" :key="r.role_code" class="role-item" :class="{ active: r.role_code === activeCode }" @click="activeCode = r.role_code">
          <div class="r-top"><strong>{{ r.role_name }}</strong><span class="badge">{{ r.allowed_tools.length }} 接口</span></div>
          <div class="r-code">{{ r.role_code }} {{ r.is_system ? '· 内置' : '· 自定义' }}</div>
        </button>
      </aside>

      <div v-if="activeRole" class="role-detail">
        <div class="meta-row">
          <label>名称 <input v-model="activeRole.role_name" class="inp" /></label>
          <label style="flex: 1">说明 <input v-model="activeRole.description" class="inp" style="width: 100%" /></label>
          <button class="btn btn-primary" :disabled="saving" @click="saveCurrent">{{ saving ? '保存中...' : '保存能力配置' }}</button>
          <button v-if="!activeRole.is_system" class="btn btn-danger" @click="removeRole">删除</button>
        </div>

        <h4>允许在 AI 聊天框发起的接口 ({{ activeRole.allowed_tools.length }}/{{ tools.length }})</h4>
        <div class="tool-grid">
          <label v-for="t in tools" :key="t.name" class="tool-card" :class="{ checked: activeRole.allowed_tools.includes(t.name) }">
            <div class="t-head">
              <input type="checkbox" :checked="activeRole.allowed_tools.includes(t.name)" @change="toggleTool(t.name)" />
              <code>{{ t.name }}</code>
            </div>
            <p class="t-desc">{{ t.description }}</p>
          </label>
        </div>

        <div class="link-box">
          <div><strong>关联可见菜单：</strong><span v-for="m in linkedMenus" :key="m.menu_key" class="chip">{{ m.title }}</span><span v-if="!linkedMenus.length" class="muted">无（可在“动态菜单配置”中勾选 {{ activeCode }}）</span></div>
          <div><strong>关联可发起流程：</strong><span v-for="w in linkedFlows" :key="w.flow_code" class="chip chip-b">{{ w.name }}</span><span v-if="!linkedFlows.length" class="muted">无</span></div>
        </div>
      </div>
    </div>
  </section>
</template>
<style scoped>
.role-page { display: flex; flex-direction: column; gap: 14px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.head h2 { margin: 0 0 4px; font-size: 18px; }
.sub, .muted { margin: 0; font-size: 13px; color: var(--muted); }
.acts, .new-box, .meta-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.new-box, .role-detail { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }
.ok-bar { margin: 0; padding: 8px 12px; background: #ecfdf5; color: #047857; border-radius: 8px; font-size: 13px; }
.err-bar { margin: 0; padding: 8px 12px; background: var(--err-soft); color: var(--err); border-radius: 8px; font-size: 13px; }
.grid { display: grid; grid-template-columns: 240px 1fr; gap: 14px; align-items: start; }
.role-list { display: flex; flex-direction: column; gap: 6px; }
.role-item { text-align: left; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--card); cursor: pointer; }
.role-item.active { border-color: #2563eb; background: #eff6ff; }
.r-top { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.r-code { font-size: 11px; color: var(--muted); margin-top: 3px; }
.badge { font-size: 11px; padding: 2px 6px; border-radius: 99px; background: #e2e8f0; }
.inp { padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; }
.tool-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; margin: 10px 0 14px; }
.tool-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px; cursor: pointer; display: flex; flex-direction: column; gap: 4px; }
.tool-card.checked { border-color: #2563eb; background: #f8fafc; }
.t-head { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; }
.t-desc { margin: 0; font-size: 12px; color: var(--muted); line-height: 1.4; }
.link-box { border-top: 1px solid var(--border); padding-top: 10px; display: flex; flex-direction: column; gap: 6px; font-size: 12px; }
.chip { display: inline-block; padding: 2px 8px; border-radius: 6px; background: #f1f5f9; margin-right: 6px; }
.chip-b { background: #e0f2fe; color: #0369a1; }
.btn-danger { background: #fee2e2; color: #b91c1c; border-color: #fecaca; }
</style>
