<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchAllMenus, updateSysMenu, type SysMenuItem } from '../api/client'
import { createSysMenu, deleteSysMenu, fetchRoles } from '../api/roles'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{ menusUpdated: [] }>()

const menus = ref<SysMenuItem[]>([])
const roleCodes = ref<string[]>(['admin', 'user', 'readonly', 'external_guest'])
const loading = ref(false); const savingKey = ref(''); const msg = ref(''); const err = ref('')
const showAdd = ref(false)
const nKey = ref(''); const nTitle = ref(''); const nGroup = ref('业务中心'); const nIcon = ref('🌐'); const nUrl = ref('http://127.0.0.1:8090')
const GROUPS = ['工作台', '业务中心', 'AI 与记忆', '系统管理']

async function loadAll() {
  loading.value = true
  try {
    const [mList, rList] = await Promise.all([fetchAllMenus(props.token), fetchRoles(props.token).catch(() => [])])
    menus.value = mList
    if (rList.length) roleCodes.value = rList.map((r) => r.role_code)
  } finally { loading.value = false }
}

function toggleRole(item: SysMenuItem, role: string) {
  if ((item.menu_key === 'menu_admin' || item.menu_key === 'role_admin') && role === 'admin') return
  const idx = item.allowed_roles.indexOf(role)
  if (idx >= 0) item.allowed_roles.splice(idx, 1)
  else item.allowed_roles.push(role)
}

async function saveRow(item: SysMenuItem) {
  savingKey.value = item.menu_key; msg.value = ''; err.value = ''
  try {
    await updateSysMenu(props.token, item.menu_key, {
      title: item.title, group_name: item.group_name, icon: item.icon, sort_order: item.sort_order,
      allowed_roles: item.allowed_roles, is_enabled: item.is_enabled, external_url: item.external_url || '',
    })
    msg.value = `已保存「${item.title}」，左侧导航已实时同步。`
    emit('menusUpdated')
  } catch (e) { err.value = e instanceof Error ? e.message : String(e) }
  finally { savingKey.value = '' }
}

async function addExternalMenu() {
  msg.value = ''; err.value = ''
  const key = nKey.value.trim().toLowerCase()
  if (!/^[a-z0-9_]{2,40}$/.test(key)) { err.value = '唯一键仅支持小写字母、数字和下划线'; return }
  try {
    await createSysMenu(props.token, {
      menu_key: key, title: nTitle.value.trim() || key, group_name: nGroup.value, icon: nIcon.value || '🌐',
      sort_order: 55, allowed_roles: ['admin', 'user'], is_enabled: true, external_url: nUrl.value.trim(),
    })
    nKey.value = ''; nTitle.value = ''; showAdd.value = false
    msg.value = '已挂载新外部页面到左侧菜单。'
    await loadAll(); emit('menusUpdated')
  } catch (e) { err.value = e instanceof Error ? e.message : String(e) }
}

async function removeMenu(menuKey: string) {
  msg.value = ''; err.value = ''
  try { await deleteSysMenu(props.token, menuKey); await loadAll(); emit('menusUpdated') }
  catch (e) { err.value = e instanceof Error ? e.message : String(e) }
}

onMounted(loadAll)
</script>

<template>
  <section class="menu-admin">
    <header class="panel-head">
      <div>
        <h2>数据库动态菜单 & 外部页面挂载 (sys_menus)</h2>
        <p class="sub">支持直接新增外部 Nginx/微服务 URL 挂进左侧导航，或实时修改现有菜单的分组、排序与角色权限。</p>
      </div>
      <div class="acts">
        <button class="btn btn-primary" @click="showAdd = !showAdd">{{ showAdd ? '收起' : '+ 挂载外部页面' }}</button>
        <button class="btn" :disabled="loading" @click="loadAll">刷新</button>
      </div>
    </header>

    <div v-if="showAdd" class="add-box">
      <input v-model="nKey" class="inp-sm" placeholder="唯一键 (如 erp_bi)" />
      <input v-model="nTitle" class="inp-sm" placeholder="菜单名称 (如 外部数据看板)" />
      <input v-model="nIcon" class="inp-sm" style="width: 48px" placeholder="🌐" />
      <select v-model="nGroup" class="inp-sm"><option v-for="g in GROUPS" :key="g" :value="g">{{ g }}</option></select>
      <input v-model="nUrl" class="inp-sm" style="flex: 1; min-width: 200px" placeholder="外部 URL (如 http://127.0.0.1:8091)" />
      <button class="btn btn-primary" @click="addExternalMenu">添加并挂载</button>
    </div>

    <p v-if="msg" class="notice">{{ msg }}</p>
    <p v-if="err" class="err-bar">{{ err }}</p>

    <div class="table-wrap">
      <table>
        <thead><tr><th>唯一键</th><th>图标</th><th>菜单名称</th><th>分组</th><th>排序</th><th>外部 URL (可选)</th><th>允许角色</th><th>启用</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="m in menus" :key="m.menu_key">
            <td><span class="badge badge-blue">{{ m.menu_key }}</span></td>
            <td><input v-model="m.icon" class="inp-sm" style="width: 42px" /></td>
            <td><input v-model="m.title" class="inp-sm" style="width: 118px" /></td>
            <td><select v-model="m.group_name" class="inp-sm"><option v-for="g in GROUPS" :key="g" :value="g">{{ g }}</option></select></td>
            <td><input v-model.number="m.sort_order" type="number" class="inp-sm" style="width: 58px" /></td>
            <td><input v-model="m.external_url" class="inp-sm" style="width: 170px" placeholder="内部页留空" /></td>
            <td>
              <div class="role-tags">
                <label v-for="r in roleCodes" :key="r" class="role-chk">
                  <input type="checkbox" :checked="m.allowed_roles.includes(r)" :disabled="(m.menu_key === 'menu_admin' || m.menu_key === 'role_admin') && r === 'admin'" @change="toggleRole(m, r)" />
                  {{ r }}
                </label>
              </div>
            </td>
            <td><input v-model="m.is_enabled" type="checkbox" :disabled="m.menu_key === 'menu_admin' || m.menu_key === 'role_admin'" /></td>
            <td class="acts">
              <button class="btn btn-primary" :disabled="savingKey === m.menu_key" @click="saveRow(m)">{{ savingKey === m.menu_key ? '...' : '保存' }}</button>
              <button v-if="m.external_url" class="btn" @click="removeMenu(m.menu_key)">删</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.menu-admin { display: flex; flex-direction: column; gap: 12px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.acts { display: flex; gap: 6px; align-items: center; }
.add-box { display: flex; gap: 8px; flex-wrap: wrap; background: var(--card); border: 1px solid var(--border); padding: 12px; border-radius: 10px; }
.notice { margin: 0; padding: 8px 12px; background: #ecfdf5; color: #047857; border-radius: 8px; font-size: 13px; }
.err-bar { margin: 0; padding: 8px 12px; background: var(--err-soft); color: var(--err); border-radius: 8px; font-size: 13px; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { background: #f9fafb; color: var(--muted); font-weight: 600; }
.inp-sm { padding: 5px 7px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; }
.role-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.role-chk { display: flex; align-items: center; gap: 3px; font-size: 11px; cursor: pointer; }
</style>
