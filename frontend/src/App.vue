<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { createSession, devLogin, fetchVisibleMenus, loginUser, registerUser, type SysMenuItem, type UserInfo } from "./api/client"
import ApiTester from "./components/ApiTester.vue"
import BomManager from "./components/BomManager.vue"
import ChatWorkspace from "./components/ChatWorkspace.vue"
import EvalDashboard from "./components/EvalDashboard.vue"
import FloatingCopilot from "./components/FloatingCopilot.vue"
import KnowledgeBase from "./components/KnowledgeBase.vue"
import MemoryManager from "./components/MemoryManager.vue"
import MenuManager from "./components/MenuManager.vue"
import PlatformOverview from "./components/PlatformOverview.vue"
import RetrievalLab from "./components/RetrievalLab.vue"
import WorkflowCenter from "./components/WorkflowCenter.vue"
import { useMemories } from "./composables/useMemories"

const activeTab = ref<string>("overview")
const token = ref("")
const sessionId = ref("")
const currentUser = ref<UserInfo | null>(null)
const menuItems = ref<SysMenuItem[]>([])
const collapsedGroups = ref<Record<string, boolean>>({})
const initError = ref("")

const showAuthModal = ref(false)
const authMode = ref<"login" | "register">("login")
const formUser = ref("")
const formPwd = ref("")
const formRole = ref<"user" | "admin" | "readonly" | "external_guest">("user")
const formGroups = ref("public,engineering")
const authErr = ref("")

const { memories, refreshMemories } = useMemories()

const groupedMenus = computed(() => {
  const map: Record<string, SysMenuItem[]> = {}
  for (const item of menuItems.value) {
    if (!map[item.group_name]) map[item.group_name] = []
    map[item.group_name].push(item)
  }
  return map
})

const currentMenuTitle = computed(() => menuItems.value.find((m) => m.menu_key === activeTab.value)?.title || "系统工作台")

async function loadMenus() {
  if (!token.value) return
  menuItems.value = await fetchVisibleMenus(token.value)
  if (menuItems.value.length && !menuItems.value.some((m) => m.menu_key === activeTab.value)) {
    activeTab.value = menuItems.value[0].menu_key
  }
}

async function applyAuth(auth: { access_token: string; user: UserInfo }) {
  token.value = auth.access_token
  currentUser.value = auth.user
  const sess = await createSession(token.value)
  sessionId.value = sess.id
  await Promise.all([loadMenus(), refreshMemories(token.value)])
}

async function quickSwitch(preset: "admin" | "eng" | "guest" | "ext") {
  initError.value = ""
  try {
    if (preset === "admin") await applyAuth(await devLogin("shenyang", "admin", ["public", "engineering", "finance"]))
    else if (preset === "eng") await applyAuth(await devLogin("dev_user", "user", ["public", "engineering"]))
    else if (preset === "guest") await applyAuth(await devLogin("guest", "readonly", ["public"]))
    else await applyAuth(await devLogin("ext_visitor", "external_guest", ["public"]))
  } catch (err) {
    initError.value = err instanceof Error ? err.message : "切换账号失败"
  }
}

async function submitAuthForm() {
  authErr.value = ""
  try {
    if (authMode.value === "login") {
      await applyAuth(await loginUser(formUser.value.trim(), formPwd.value))
    } else {
      const groups = formGroups.value.split(",").map((s) => s.trim()).filter(Boolean)
      await applyAuth(await registerUser(formUser.value.trim(), formPwd.value, formRole.value, groups))
    }
    showAuthModal.value = false
    formPwd.value = ""
  } catch (err) {
    authErr.value = err instanceof Error ? err.message : String(err)
  }
}

onMounted(() => quickSwitch("admin"))
</script>

<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="logo-box"><span class="logo-dot"></span><strong>工业智能体管理后台</strong></div>
      <div class="menu-scroll">
        <div v-for="(list, grp) in groupedMenus" :key="grp" class="menu-group">
          <div class="grp-title" @click="collapsedGroups[grp] = !collapsedGroups[grp]">
            <span>{{ grp }}</span><span>{{ collapsedGroups[grp] ? "+" : "−" }}</span>
          </div>
          <template v-if="!collapsedGroups[grp]">
            <button
              v-for="m in list" :key="m.menu_key" class="nav-item"
              :class="{ active: activeTab === m.menu_key }" @click="activeTab = m.menu_key"
            >
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
          <template v-if="currentUser">
            <span class="badge badge-ok">{{ currentUser.username }} · {{ currentUser.role }}</span>
            <span class="badge badge-blue">组: {{ currentUser.groups.join(",") }}</span>
          </template>
        </div>
        <div class="auth-actions">
          <button class="btn" @click="quickSwitch('admin')">切 Admin</button>
          <button class="btn" @click="quickSwitch('eng')">切 研发组</button>
          <button class="btn" @click="quickSwitch('guest')">切 只读</button>
          <button class="btn" @click="quickSwitch('ext')">切 外部访客</button>
          <button class="btn btn-primary" @click="showAuthModal = true">登录/注册</button>
        </div>
      </header>

      <main class="content-body">
        <div v-if="initError" class="err-banner">{{ initError }}</div>
        <template v-else-if="token">
          <PlatformOverview v-if="activeTab === 'overview'" @navigate="(t) => (activeTab = t)" />
          <BomManager v-else-if="activeTab === 'bom'" :token="token" />
          <WorkflowCenter v-else-if="activeTab === 'workflow'" :token="token" :role="currentUser?.role || 'user'" :current-user-id="currentUser?.user_id || currentUser?.id || ''" @go-chat="activeTab = 'chat'" />
          <ChatWorkspace v-else-if="activeTab === 'chat'" :token="token" @go-workflow="activeTab = 'workflow'" />
          <MemoryManager v-else-if="activeTab === 'mem'" :token="token" />
          <KnowledgeBase v-else-if="activeTab === 'kb'" :token="token" />
          <RetrievalLab v-else-if="activeTab === 'lab'" :token="token" />
          <EvalDashboard v-else-if="activeTab === 'eval'" :token="token" />
          <MenuManager v-else-if="activeTab === 'menu_admin'" :token="token" @menus-updated="loadMenus" />
          <ApiTester v-else :token="token" :session-id="sessionId" />
        </template>
        <p v-else class="loading">正在初始化鉴权与动态菜单...</p>
      </main>
    </div>

    <FloatingCopilot v-if="token" :token="token" @open-full-chat="activeTab = 'chat'" @go-workflow="activeTab = 'workflow'" />

    <div v-if="showAuthModal" class="modal-mask" @click.self="showAuthModal = false">
      <div class="modal">
        <h3>{{ authMode === "login" ? "账号密码登录" : "注册新账号" }}</h3>
        <input v-model="formUser" class="m-input" placeholder="用户名" />
        <input v-model="formPwd" type="password" class="m-input" placeholder="密码" />
        <template v-if="authMode === 'register'">
          <select v-model="formRole" class="m-input">
            <option value="user">user</option><option value="readonly">readonly</option>
            <option value="external_guest">external_guest</option>
          </select>
          <input v-model="formGroups" class="m-input" placeholder="分组如 public,engineering" />
        </template>
        <p v-if="authErr" class="err-txt">{{ authErr }}</p>
        <div class="m-actions">
          <button class="btn" @click="authMode = authMode === 'login' ? 'register' : 'login'">{{ authMode === "login" ? "去注册" : "去登录" }}</button>
          <button class="btn btn-primary" @click="submitAuthForm">确认</button>
        </div>
      </div>
    </div>
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
.crumb, .auth-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.content-body { padding: 20px 24px; max-width: 1320px; width: 100%; margin: 0 auto; }
.err-banner { background: var(--err-soft); color: var(--err); padding: 12px 16px; border-radius: 8px; }
.modal-mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--card); padding: 20px; border-radius: 12px; width: 320px; display: flex; flex-direction: column; gap: 10px; }
.m-input { padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
.m-actions { display: flex; justify-content: space-between; }
</style>
