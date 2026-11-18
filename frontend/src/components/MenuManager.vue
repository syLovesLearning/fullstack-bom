<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchAllMenus, updateSysMenu, type SysMenuItem } from '../api/client'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{ menusUpdated: [] }>()

const menus = ref<SysMenuItem[]>([])
const loading = ref(false)
const savingKey = ref('')
const msg = ref('')

const ALL_ROLES = ['admin', 'user', 'readonly', 'external_guest']
const GROUPS = ['工作台', '业务中心', 'AI 与记忆', '系统管理']

async function loadAll() {
  loading.value = true
  try {
    menus.value = await fetchAllMenus(props.token)
  } finally {
    loading.value = false
  }
}

function toggleRole(item: SysMenuItem, role: string) {
  if (item.menu_key === 'menu_admin' && role === 'admin') return
  const idx = item.allowed_roles.indexOf(role)
  if (idx >= 0) item.allowed_roles.splice(idx, 1)
  else item.allowed_roles.push(role)
}

async function saveRow(item: SysMenuItem) {
  savingKey.value = item.menu_key
  msg.value = ''
  try {
    await updateSysMenu(props.token, item.menu_key, {
      title: item.title,
      group_name: item.group_name,
      icon: item.icon,
      sort_order: item.sort_order,
      allowed_roles: item.allowed_roles,
      is_enabled: item.is_enabled,
    })
    msg.value = `已保存「${item.title}」，左侧导航已实时同步。`
    emit('menusUpdated')
  } catch (err) {
    msg.value = err instanceof Error ? err.message : String(err)
  } finally {
    savingKey.value = ''
  }
}

onMounted(loadAll)
</script>

<template>
  <section class="menu-admin">
    <header class="panel-head">
      <div>
        <h2>数据库动态菜单配置 (PostgreSQL sys_menus 表)</h2>
        <p class="sub">实时修改左侧菜单的名称、所属分组、排序权重、角色可见性与启用状态；保存后立即刷新左侧导航树。</p>
      </div>
      <button class="btn" :disabled="loading" @click="loadAll">刷新配置</button>
    </header>

    <p v-if="msg" class="notice">{{ msg }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>唯一键</th>
            <th>图标</th>
            <th>菜单名称</th>
            <th>所属左侧分组</th>
            <th>排序</th>
            <th>允许访问角色 (RBAC)</th>
            <th>启用</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in menus" :key="m.menu_key">
            <td><span class="badge badge-blue">{{ m.menu_key }}</span></td>
            <td><input v-model="m.icon" class="inp-sm" style="width: 44px" /></td>
            <td><input v-model="m.title" class="inp-sm" style="width: 130px" /></td>
            <td>
              <select v-model="m.group_name" class="inp-sm">
                <option v-for="g in GROUPS" :key="g" :value="g">{{ g }}</option>
              </select>
            </td>
            <td><input v-model.number="m.sort_order" type="number" class="inp-sm" style="width: 64px" /></td>
            <td>
              <div class="role-tags">
                <label v-for="r in ALL_ROLES" :key="r" class="role-chk">
                  <input
                    type="checkbox"
                    :checked="m.allowed_roles.includes(r)"
                    :disabled="m.menu_key === 'menu_admin' && r === 'admin'"
                    @change="toggleRole(m, r)"
                  />
                  {{ r }}
                </label>
              </div>
            </td>
            <td>
              <input
                v-model="m.is_enabled"
                type="checkbox"
                :disabled="m.menu_key === 'menu_admin'"
              />
            </td>
            <td>
              <button class="btn btn-primary" :disabled="savingKey === m.menu_key" @click="saveRow(m)">
                {{ savingKey === m.menu_key ? '保存中' : '保存' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.menu-admin { display: flex; flex-direction: column; gap: 14px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.notice { margin: 0; padding: 8px 12px; background: #ecfdf5; color: #047857; border-radius: 8px; font-size: 13px; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
th { background: #f9fafb; color: var(--muted); font-weight: 600; }
.inp-sm { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; }
.role-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.role-chk { display: flex; align-items: center; gap: 3px; font-size: 12px; cursor: pointer; }
</style>
