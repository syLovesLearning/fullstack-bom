<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  fetchWorkflowSkills,
  listWorkflows,
  submitWorkflow,
  updateWorkflowStatus,
  upsertWorkflowDefinition,
  type WorkflowDefinition,
  type WorkflowItem,
} from '../api/client'

const props = defineProps<{ token: string; role: string; currentUserId?: string }>()
const emit = defineEmits<{ goChat: [] }>()

const definitions = ref<WorkflowDefinition[]>([])
const activeFlow = ref('')
const dynamicForm = ref<Record<string, string | number>>({})
const submitting = ref(false)
const formMsg = ref('')
const formErr = ref('')

// 配置新流程弹窗（仅管理员）
const showDefModal = ref(false)
const defCode = ref('eqp_repair')
const defName = ref('设备报修流程')
const defRoles = ref('admin,user')
const defFieldsJson = ref(
  JSON.stringify(
    [
      { key: 'title', label: '设备名称', type: 'text', required: true, default: 'CNC 加工中心' },
      { key: 'urgency', label: '紧急程度', type: 'select', required: true, options: ['normal', 'urgent'], default: 'urgent' },
      { key: 'expected_date', label: '期望维修日期', type: 'date', required: true, default: '2026-11-22' },
    ],
    null,
    2,
  ),
)
const defErr = ref('')

// 分页台账
const items = ref<WorkflowItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(6)
const filterFlow = ref('')
const loading = ref(false)
const detailItem = ref<WorkflowItem | null>(null)
// admin 走 scope=all 审批视图（可看到他人发起的流程）；普通用户只看自己的台账
const isAdmin = computed(() => props.role === 'admin')

const currentDef = computed(() => definitions.value.find((d) => d.flow_code === activeFlow.value) ?? null)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

/** 是否可审批该条：admin 视角且非本人发起（防自审自批，与后端校验一致）。 */
function canApprove(w: WorkflowItem): boolean {
  return isAdmin.value && w.status === 'submitted' && !!w.user_id && w.user_id !== props.currentUserId
}

function resetFormDefaults(def: WorkflowDefinition | null) {
  if (!def) {
    dynamicForm.value = {}
    return
  }
  const obj: Record<string, string | number> = {}
  for (const f of def.fields) {
    obj[f.key] = f.default ?? (f.type === 'number' ? 0 : f.options?.[0] ?? '')
  }
  dynamicForm.value = obj
}

async function loadSkills() {
  definitions.value = await fetchWorkflowSkills(props.token)
  if (definitions.value.length) {
    if (!definitions.value.some((d) => d.flow_code === activeFlow.value)) {
      activeFlow.value = definitions.value[0].flow_code
    }
    resetFormDefaults(currentDef.value)
  } else {
    activeFlow.value = ''
    dynamicForm.value = {}
  }
}

async function fetchList() {
  loading.value = true
  try {
    const res = await listWorkflows(props.token, filterFlow.value, page.value, pageSize.value, isAdmin.value ? 'all' : 'mine')
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!currentDef.value) return
  submitting.value = true
  formMsg.value = ''
  formErr.value = ''
  try {
    const created = await submitWorkflow(props.token, currentDef.value.flow_code, dynamicForm.value)
    formMsg.value = `流程发起成功：${created.title} (${created.flow_code})`
    page.value = 1
    await fetchList()
  } catch (err) {
    formErr.value = err instanceof Error ? err.message : String(err)
  } finally {
    submitting.value = false
  }
}

async function saveNewDefinition() {
  defErr.value = ''
  try {
    const fields = JSON.parse(defFieldsJson.value)
    const roles = defRoles.value.split(',').map((s) => s.trim()).filter(Boolean)
    await upsertWorkflowDefinition(props.token, {
      flow_code: defCode.value.trim(),
      name: defName.value.trim(),
      description: '管理员页面配置',
      allowed_roles: roles,
      fields,
    })
    showDefModal.value = false
    await loadSkills()
    activeFlow.value = defCode.value.trim()
    resetFormDefaults(currentDef.value)
  } catch (err) {
    defErr.value = err instanceof Error ? err.message : String(err)
  }
}

async function handleApprove(item: WorkflowItem, status: 'approved' | 'rejected') {
  try {
    await updateWorkflowStatus(props.token, item.id, status, 'form')
    await fetchList()
  } catch (err) {
    window.alert(err instanceof Error ? err.message : '状态更新失败')
  }
}

function changePage(next: number) {
  if (next < 1 || next > totalPages.value) return
  page.value = next
  fetchList()
}

watch(activeFlow, () => resetFormDefaults(currentDef.value))
watch([() => props.token, filterFlow], () => {
  page.value = 1
  loadSkills()
  fetchList()
})

onMounted(async () => {
  await Promise.all([loadSkills(), fetchList()])
})
</script>

<template>
  <section class="wf-layout">
    <!-- 左侧：基于权限动态渲染的配置化表单 -->
    <div class="form-card">
      <div class="card-head">
        <h2>配置化流程中心</h2>
        <div class="head-btns">
          <button v-if="role === 'admin'" class="btn" @click="showDefModal = true">+ 配置新流程</button>
          <button class="btn" @click="emit('goChat')">AI 对话填单 →</button>
        </div>
      </div>
      <p class="sub">当前角色 (<code>{{ role }}</code>) 仅展示有权限发起的流程类型；新配流程实时生效。</p>

      <div v-if="definitions.length" class="flow-tabs">
        <button
          v-for="d in definitions"
          :key="d.flow_code"
          class="btn"
          :class="{ 'btn-primary': activeFlow === d.flow_code }"
          @click="activeFlow = d.flow_code"
        >
          {{ d.name }}
        </button>
      </div>
      <p v-else class="err-tip">当前角色无权发起任何流程。</p>

      <div v-if="currentDef" class="fields">
        <label v-for="f in currentDef.fields" :key="f.key">
          <span>{{ f.label }} <em v-if="f.required" class="req">*</em></span>
          <select v-if="f.type === 'select'" v-model="dynamicForm[f.key]" class="inp">
            <option v-for="opt in f.options ?? []" :key="opt" :value="opt">{{ opt }}</option>
          </select>
          <input
            v-else-if="f.type === 'number'"
            v-model.number="dynamicForm[f.key]"
            type="number"
            class="inp"
          />
          <input v-else-if="f.type === 'date'" v-model="dynamicForm[f.key]" type="date" class="inp" />
          <input v-else v-model="dynamicForm[f.key]" class="inp" />
        </label>
      </div>

      <p v-if="formMsg" class="ok-tip">{{ formMsg }}</p>
      <p v-if="formErr" class="err-tip">{{ formErr }}</p>
      <button v-if="currentDef" class="btn btn-primary submit-btn" :disabled="submitting" @click="handleSubmit">
        {{ submitting ? '校验并入库中...' : `提交 ${currentDef.name}` }}
      </button>
    </div>

    <!-- 右侧：支持筛选与分页的流程台账 -->
    <div class="list-card">
      <div class="card-head">
        <h2>{{ isAdmin ? '全量流程台账（审批视图）' : `已发起流程台账 (共 ${total} 条)` }}</h2>
        <div class="filters">
          <select v-model="filterFlow" class="sel">
            <option value="">全部流程</option>
            <option v-for="d in definitions" :key="d.flow_code" :value="d.flow_code">{{ d.name }}</option>
          </select>
          <button class="btn" :disabled="loading" @click="fetchList">刷新</button>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>流程编码</th>
              <th>标题 / 项目</th>
              <th v-if="isAdmin">发起人</th>
              <th>状态</th>
              <th>发起时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="w in items" :key="w.id">
              <td><span class="badge badge-blue">{{ w.flow_code }}</span></td>
              <td><strong>{{ w.title }}</strong></td>
              <td v-if="isAdmin">{{ w.owner_name ?? '-' }}</td>
              <td>
                <span :class="['badge', w.status === 'approved' ? 'badge-ok' : w.status === 'rejected' ? 'badge-err' : 'badge-muted']">
                  {{ w.status }}
                </span>
              </td>
              <td>{{ new Date(w.created_at).toLocaleString() }}</td>
              <td class="ops-cell">
                <button class="btn" @click="detailItem = w">详情</button>
                <button v-if="canApprove(w)" class="btn" @click="handleApprove(w, 'approved')">通过</button>
                <button v-if="canApprove(w)" class="btn" @click="handleApprove(w, 'rejected')">驳回</button>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td :colspan="isAdmin ? 6 : 5" class="empty">暂无已发起流程。</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pager">
        <span>第 {{ page }} / {{ totalPages }} 页（每页 {{ pageSize }} 条）</span>
        <div class="pager-btns">
          <button class="btn" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <button class="btn" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
        </div>
      </div>
    </div>
  </section>

  <!-- 流程详情抽屉 -->
  <div v-if="detailItem" class="drawer-mask" @click.self="detailItem = null">
    <aside class="drawer">
      <header class="drawer-head">
        <div>
          <span class="badge badge-blue">{{ detailItem.flow_code }}</span>
          <h3>{{ detailItem.title }}</h3>
        </div>
        <button class="btn" @click="detailItem = null">关闭</button>
      </header>
      <pre class="json-pre">{{ JSON.stringify(detailItem.form_data, null, 2) }}</pre>
    </aside>
  </div>

  <!-- 管理员配置新流程类型弹窗 -->
  <div v-if="showDefModal" class="drawer-mask" @click.self="showDefModal = false">
    <div class="modal">
      <h3>配置新流程类型 (写入 workflow_definitions)</h3>
      <input v-model="defCode" class="inp" placeholder="flow_code（小写字母/下划线）" />
      <input v-model="defName" class="inp" placeholder="中文名称" />
      <input v-model="defRoles" class="inp" placeholder="允许角色（逗号分隔，如 admin,user,external_guest）" />
      <textarea v-model="defFieldsJson" rows="7" class="inp json-area" />
      <p v-if="defErr" class="err-tip">{{ defErr }}</p>
      <div class="head-btns">
        <button class="btn" @click="showDefModal = false">取消</button>
        <button class="btn btn-primary" @click="saveNewDefinition">保存配置</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wf-layout { display: grid; grid-template-columns: 370px 1fr; gap: 16px; }
@media (max-width: 980px) { .wf-layout { grid-template-columns: 1fr; } }
.form-card, .list-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.card-head h2 { margin: 0; font-size: 16px; }
.head-btns, .flow-tabs, .filters { display: flex; gap: 6px; flex-wrap: wrap; }
.sub { margin: 0; font-size: 12px; color: var(--muted); }
.fields { display: flex; flex-direction: column; gap: 8px; font-size: 12px; color: var(--muted); }
.fields label { display: flex; flex-direction: column; gap: 4px; }
.req { color: var(--err); font-style: normal; }
.inp, .sel { padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; color: var(--text); background: #fff; }
.json-area { font-family: monospace; font-size: 12px; }
.submit-btn { margin-top: 4px; }
.ok-tip { margin: 0; color: var(--ok); font-size: 12px; }
.err-tip { margin: 0; color: var(--err); font-size: 12px; }
.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
th { background: #f9fafb; color: var(--muted); }
.ops-cell { display: flex; gap: 4px; }
.empty { text-align: center; color: var(--muted); padding: 24px; }
.pager { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--muted); }
.pager-btns { display: flex; gap: 6px; }
.drawer-mask { position: fixed; inset: 0; background: rgba(17, 24, 39, 0.35); display: flex; justify-content: flex-end; align-items: center; z-index: 50; }
.drawer { width: min(440px, 92vw); height: 100%; background: var(--card); padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.drawer-head { display: flex; justify-content: space-between; align-items: flex-start; }
.drawer-head h3 { margin: 6px 0 0; font-size: 17px; }
.json-pre { margin: 0; white-space: pre-wrap; background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-size: 12px; }
.modal { margin: auto; background: var(--card); border-radius: 12px; padding: 20px; width: min(460px, 92vw); display: flex; flex-direction: column; gap: 10px; }
.modal h3 { margin: 0; font-size: 16px; }
</style>
