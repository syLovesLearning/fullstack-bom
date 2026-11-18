<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { devLogin, fetchAuthMode, fetchMe, fetchVisibleMenus, loginUser, registerUser, type SysMenuItem, type UserInfo } from "./api/client"
import { fetchRoles, type SysRoleItem } from "./api/roles"
import ApiTester from "./components/ApiTester.vue"
import BomManager from "./components/BomManager.vue"
import ChatWorkspace from "./components/ChatWorkspace.vue"
import EvalDashboard from "./components/EvalDashboard.vue"
import FloatingCopilot from "./components/FloatingCopilot.vue"
import KnowledgeBase from "./components/KnowledgeBase.vue"
import MemoryManager from "./components/MemoryManager.vue"
import MenuManager from "./components/MenuManager.vue"
import PasscodeGate from "./components/PasscodeGate.vue"
import PlatformOverview from "./components/PlatformOverview.vue"
import RetrievalLab from "./components/RetrievalLab.vue"
import RoleManager from "./components/RoleManager.vue"
import WorkflowCenter from "./components/WorkflowCenter.vue"
import { useChatSession } from "./composables/useChatSession"
import { useMemories } from "./composables/useMemories"

const activeTab = ref("overview")
const token = ref(""); const sessionId = ref("")
const currentUser = ref<UserInfo | null>(null)
const menuItems = ref<SysMenuItem[]>([]); const rolesList = ref<SysRoleItem[]>([])
const collapsedGroups = ref<Record<string, boolean>>({})
const initError = ref(""); const isDevMode = ref(true)
const showAuthModal = ref(false); const authMode = ref<"login" | "register">("login")
const formUser = ref(""); const formPwd = ref(""); const authErr = ref("")
const formRole = ref("user"); const formGroups = ref("public,engineering")

const { memories, refreshMemories } = useMemories()
const { activeSessionId: sharedSessionId, ensureSession, resetSessionState } = useChatSession()

const groupedMenus = computed(() => {
  const map: Record<string, SysMenuItem[]> = {}
  for (const item of menuItems.value) { (map[item.group_name] ||= []).push(item) }
  return map
})
const currentMenuTitle = computed(() => menuItems.value.find((m) => m.menu_key === activeTab.value)?.title || "系统工作台")

async function loadMenus() {
  if (!token.value) return
  menuItems.value = await fetchVisibleMenus(token.value)
  if (menuItems.value.length && !menuItems.value.some((m) => m.menu_key === activeTab.value)) activeTab.value = menuItems.value[0].menu_key
}

async function loadRoles() {
  if (!token.value) return
  try { rolesList.value = await fetchRoles(token.value) } catch { /* ignore */ }
}

async function applyAuth(auth: { access_token: string; user: UserInfo }) {
  token.value = auth.access_token; currentUser.value = auth.user
  localStorage.setItem("agent_token", auth.access_token)
  resetSessionState()
  await Promise.all([loadMenus(), loadRoles(), refreshMemories(token.value), ensureSession(token.value, true)])
  sessionId.value = sharedSessionId.value
}

function logout() {
  localStorage.removeItem("agent_token")
  token.value = ""; currentUser.value = null; menuItems.value = []; rolesList.value = []; resetSessionState()
}

async function switchDevRole(roleCode: string) {
  initError.value = ""
  const uname = roleCode === "admin" ? "shenyang" : `preview_${roleCode}`
  const groups = roleCode === "admin" ? ["public", "engineering", "finance"] : roleCode === "user" ? ["public", "engineering"] : ["public"]
  try { await applyAuth(await devLogin(uname, roleCode, groups)) }
  catch (err) { initError.value = err instanceof Error ? err.message : "切换角色失败" }
}

async function submitAuthForm() {
  authErr.value = ""
  try {
    if (authMode.value === "login") await applyAuth(await loginUser(formUser.value.trim(), formPwd.value))
    else await applyAuth(await registerUser(formUser.value.trim(), formPwd.value, formRole.value, formGroups.value.split(",").map((s) => s.trim()).filter(Boolean)))
    showAuthModal.value = false; formPwd.value = ""
  } catch (err) { authErr.value = err instanceof Error ? err.message : String(err) }
}

onMounted(async () => {
  try { isDevMode.value = !(await fetchAuthMode()).require_passcode } catch { isDevMode.value = true }
  const saved = localStorage.getItem("agent_token")
  if (saved) {
    try { await applyAuth({ access_token: saved, user: await fetchMe(saved) }); return } catch { localStorage.removeItem("agent_token") }
  }
  if (isDevMode.value) await switchDevRole("admin")
})
</script>

<template>
  <PasscodeGate v-if="!token" @authenticated="applyAuth" />
  <div v-else class="admin-layout">
    <aside class="sidebar">
      <div class="logo-box"><span class="logo-dot"></span><strong>工业智能体管理后台</strong></div>
      <div class="menu-scroll">
        <div v-for="(list, grp) in groupedMenus" :key="grp" class="menu-group">
          <div class="grp-title" @click="collapsedGroups[grp] = !collapsedGroups[grp]"><span>{{ grp }}</span><span>{{ collapsedGroups[grp] ? "+" : "−" }}</span></div>
          <template v-if="!collapsedGroups[grp]">
            <button v-for="m in list" :key="m.menu_key" class="nav-item" :class="{ active: activeTab === m.menu_key }" @click="activeTab = m.menu_key">
              <span>{{ m.icon }}</span><span>{{ m.title }}</span>
            </button>
          </template>
        </div>
      </div>
      <div class="sidebar-foot" @click="activeTab = 'mem'">◉ 活跃长期记忆：{{ memories.length }} 条</div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div class="crumb">
          <strong>{{ currentMenuTitle }}</strong>
          <template v-if="currentUser"><span class="badge badge-ok">{{ currentUser.username }} · {{ currentUser.role }}</span><span class="badge badge-blue">组: {{ currentUser.groups.join(",") }}</span></template>
        </div>
        <div class="auth-actions">
          <label v-if="isDevMode && rolesList.length" class="dev-switch">
            <span>预览角色</span>
            <select class="m-input" :value="currentUser?.role || 'admin'" @change="switchDevRole(($event.target as HTMLSelectElement).value)">
              <option v-for="r in rolesList" :key="r.role_code" :value="r.role_code">{{ r.role_name }} ({{ r.role_code }})</option>
            </select>
          </label>
          <button class="btn btn-primary" @click="showAuthModal = true">登录/注册</button><button class="btn" @click="logout">退出</button>
        </div>
      </header>
      <main class="content-body">
        <div v-if="initError" class="err-banner">{{ initError }}</div>
        <template v-else>
          <PlatformOverview v-if="activeTab === 'overview'" @navigate="(t) => (activeTab = t)" />
          <BomManager v-else-if="activeTab === 'bom'" :token="token" />
          <WorkflowCenter v-else-if="activeTab === 'workflow'" :token="token" :role="currentUser?.role || 'user'" @go-chat="activeTab = 'chat'" />
          <ChatWorkspace v-else-if="activeTab === 'chat'" :token="token" @go-workflow="activeTab = 'workflow'" />
          <MemoryManager v-else-if="activeTab === 'mem'" :token="token" />
          <KnowledgeBase v-else-if="activeTab === 'kb'" :token="token" />
          <RetrievalLab v-else-if="activeTab === 'lab'" :token="token" />
          <EvalDashboard v-else-if="activeTab === 'eval'" :token="token" />
          <MenuManager v-else-if="activeTab === 'menu_admin'" :token="token" @menus-updated="loadMenus" />
          <RoleManager v-else-if="activeTab === 'role_admin'" :token="token" @roles-updated="loadRoles" />
          <ApiTester v-else :token="token" :session-id="sessionId" />
        </template>
      </main>
    </div>

    <FloatingCopilot :token="token" :role="currentUser?.role || 'user'" @open-full-chat="activeTab = 'chat'" @go-workflow="activeTab = 'workflow'" @go-bom="activeTab = 'bom'" />

    <div v-if="showAuthModal" class="modal-mask" @click.self="showAuthModal = false"><div class="modal">
      <h3>{{ authMode === "login" ? "账号密码登录" : "注册新账号" }}</h3>
      <input v-model="formUser" class="m-input" placeholder="用户名" /><input v-model="formPwd" type="password" class="m-input" placeholder="密码" />
      <template v-if="authMode === 'register'">
        <select v-model="formRole" class="m-input"><option value="user">user</option><option value="readonly">readonly</option><option value="external_guest">external_guest</option></select>
        <input v-model="formGroups" class="m-input" placeholder="分组如 public,engineering" />
      </template>
      <p v-if="authErr" class="err-txt">{{ authErr }}</p>
      <div class="m-actions"><button class="btn" @click="authMode = authMode === 'login' ? 'register' : 'login'">{{ authMode === "login" ? "去注册" : "去登录" }}</button><button class="btn btn-primary" @click="submitAuthForm">确认</button></div>
    </div></div>
  </div>
</template>

<style scoped>
.admin-layout { display: flex; min-height: 100vh; background: #f1f5f9; }
.sidebar { width: 230px; background: #0f172a; color: #e2e8f0; display: flex; flex-direction: column; flex-shrink: 0; }
.logo-box { padding: 16px 18px; font-size: 15px; border-bottom: 1px solid #1e293b; display: flex; align-items: center; gap: 8px; }
.logo-dot { width: 10px; height: 10px; border-radius: 50%; background: #38bdf8; }
.menu-scroll { flex: 1; padding: 10px; overflow-y: auto; }
.menu-group { margin-bottom: 12px; }
.grp-title { font-size: 11px; color: #64748b; padding: 6px 10px; display: flex; justify-content: space-between; cursor: pointer; text-transform: uppercase; }
.nav-item { width: 100%; text-align: left; padding: 9px 12px; border: none; border-radius: 8px; background: transparent; color: #cbd5e1; font-size: 13px; display: flex; align-items: center; gap: 8px; cursor: pointer; margin-bottom: 2px; }
.nav-item:hover { background: #1e293b; color: #fff; }
.nav-item.active { background: #2563eb; color: #fff; font-weight: 600; }
.sidebar-foot { padding: 12px 16px; border-top: 1px solid #1e293b; font-size: 12px; color: #94a3b8; cursor: pointer; }
.main-area { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.topbar { background: var(--card); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.crumb, .auth-actions, .dev-switch { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
.content-body { padding: 20px 24px; max-width: 1320px; width: 100%; margin: 0 auto; }
.err-banner { background: var(--err-soft); color: var(--err); padding: 12px 16px; border-radius: 8px; }
.modal-mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--card); padding: 20px; border-radius: 12px; width: 320px; display: flex; flex-direction: column; gap: 10px; }
.m-input { padding: 6px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
.m-actions { display: flex; justify-content: space-between; }
</style>
