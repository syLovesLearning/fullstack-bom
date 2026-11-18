export interface UserInfo {
  user_id?: string
  id?: string
  username: string
  role: 'admin' | 'user' | 'readonly' | 'external_guest'
  allowed_tools: string[]
  groups: string[]
}

export interface EvalCase {
  id: string
  category: string
  question: string
  expected_source: string
  expected_keywords: string[]
  expected_tool?: string
}

export interface EvalHit {
  index: number
  title: string
  source_path: string
  heading_path: string
  score: number
  snippet: string
}

export interface EvalCaseResult extends EvalCase {
  matched_keywords: string[]
  rank: number
  passed: boolean
  latency_ms: number
  top_hit: EvalHit | null
}

export interface EvalRunResponse {
  summary: {
    total: number
    passed: number
    hit_rate_at_3: number
    mrr: number
    avg_latency_ms: number
  }
  results: EvalCaseResult[]
}

export interface DocItem {
  id: string
  source_path: string
  title: string
  category: string
  allowed_groups: string[]
  updated_at: string
  chunk_count: number
}

export interface BatchUploadResponse {
  total: number
  indexed: number
  skipped: number
  failed: number
  results: { filename: string; status: string; chunks: number; error?: string }[]
}

export interface DebugStageHit {
  id: number
  title: string
  heading_path: string
  score: number
  preview: string
}

export interface DebugRerankHit {
  id: number
  rank: number
  title: string
  source_path: string
  heading_path: string
  score: number
  passed: boolean
  snippet: string
}

export interface DebugSearchResponse {
  query: string
  tokens: string[]
  min_score: number
  rejected: boolean
  latency_ms: number
  vec_hits: DebugStageHit[]
  fts_hits: DebugStageHit[]
  reranked_hits: DebugRerankHit[]
}

export interface SessionItem {
  id: string
  agent_name: string
  title: string
  updated_at: string
}

export interface ActionCardItem {
  kind: 'workflow' | 'inventory_alert' | 'bom_quote'
  id?: string
  flow_code?: 'oa_approval' | 'srm_bidding'
  title?: string
  status?: 'submitted' | 'approved' | 'rejected'
  form_data?: Record<string, unknown>
  sku?: string
  item_name?: string
  stock_qty?: number
  safety_stock?: number
  unit?: string
  warehouse?: string
  root_name?: string
  params_3d?: { H: number; W: number; D: number; T: number }
  direct_cost?: number
  final_price?: number
  cost_summary?: Record<string, number>
}

export interface MessageItem {
  id?: number
  run_id?: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  citations?: EvalHit[]
  action_cards?: ActionCardItem[]
}

export interface MemoryItem {
  id: string
  memory_type: 'fact' | 'preference' | 'summary'
  content: string
  importance: number
  created_at: string
}

export async function request<T>(url: string, token?: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  const resp = await fetch(url, { ...init, headers: { ...headers, ...(init?.headers as Record<string, string>) } })
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${await resp.text()}`)
  }
  return resp.json() as Promise<T>
}

export function devLogin(username = 'shenyang', role = 'admin', groups?: string[]) {
  return request<{ access_token: string; user: UserInfo }>('/api/v1/auth/dev-login', undefined, {
    method: 'POST',
    body: JSON.stringify({ username, role, groups: groups ?? null }),
  })
}

export function loginUser(username: string, password: string) {
  return request<{ access_token: string; user: UserInfo }>('/api/v1/auth/login', undefined, {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function registerUser(username: string, password: string, role: string, groups: string[]) {
  return request<{ access_token: string; user: UserInfo }>('/api/v1/auth/register', undefined, {
    method: 'POST',
    body: JSON.stringify({ username, password, role, groups }),
  })
}

export function listSessions(token: string) {
  return request<SessionItem[]>('/api/v1/sessions', token)
}

export function createSession(token: string, title = '新对话') {
  return request<SessionItem>('/api/v1/sessions', token, {
    method: 'POST',
    body: JSON.stringify({ agent_name: 'default', title }),
  })
}

export function listSessionMessages(token: string, sessionId: string) {
  return request<MessageItem[]>(`/api/v1/sessions/${sessionId}/messages`, token)
}

export function listMemories(token: string) {
  return request<MemoryItem[]>('/api/v1/memories', token)
}

export function createMemory(
  token: string,
  memory_type: 'fact' | 'preference' | 'summary',
  content: string,
  importance = 4,
) {
  return request<MemoryItem>('/api/v1/memories', token, {
    method: 'POST',
    body: JSON.stringify({ memory_type, content, importance }),
  })
}

export function deleteMemory(token: string, memoryId: string) {
  return request<{ deleted: boolean }>(`/api/v1/memories/${memoryId}`, token, { method: 'DELETE' })
}

export function fetchEvalCases(token: string) {
  return request<EvalCase[]>('/api/v1/eval/cases', token)
}

export function seedEvalDocs(token: string) {
  return request<{ seeded: unknown[] }>('/api/v1/eval/seed', token, { method: 'POST' })
}

export function runEvalSuite(token: string, seedIfEmpty = true) {
  return request<EvalRunResponse>('/api/v1/eval/run', token, {
    method: 'POST',
    body: JSON.stringify({ seed_if_empty: seedIfEmpty, top_k: 3 }),
  })
}

export function listDocs(token: string) {
  return request<DocItem[]>('/api/v1/docs', token)
}

export function deleteDoc(token: string, docId: string) {
  return request<{ deleted: boolean }>(`/api/v1/docs/${docId}`, token, { method: 'DELETE' })
}

export async function uploadDocs(
  token: string,
  files: File[],
  category: string,
  allowedGroups = 'private',
) {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  form.append('category', category)
  form.append('allowed_groups', allowedGroups)
  const resp = await fetch('/api/v1/docs/upload', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`)
  return resp.json() as Promise<BatchUploadResponse>
}

export function debugRagPipeline(
  token: string,
  query: string,
  category: string,
  minScore: number,
  topK = 5,
) {
  return request<DebugSearchResponse>('/api/v1/docs/search-debug', token, {
    method: 'POST',
    body: JSON.stringify({
      query,
      category: category.trim() || null,
      min_score: minScore,
      top_k: topK,
    }),
  })
}

export interface ChatDebugOptions {
  max_steps: number
  top_k: number
  min_score: number
  enable_rag: boolean
}

export interface RunStepItem {
  step_index: number
  step_type: string
  tool_name: string | null
  input_payload: Record<string, unknown>
  output_payload: Record<string, unknown>
  duration_ms: number | null
  status: string
  created_at: string
}

export interface RunTraceResponse {
  run: {
    id: string
    status: string
    model_name: string
    total_tokens: number
    latency_ms: number | null
    started_at: string
  }
  steps: RunStepItem[]
}

export function renameSession(token: string, sessionId: string, title: string) {
  return request<SessionItem>(`/api/v1/sessions/${sessionId}`, token, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export function deleteSession(token: string, sessionId: string) {
  return request<{ deleted: boolean }>(`/api/v1/sessions/${sessionId}`, token, { method: 'DELETE' })
}

export function getRunTrace(token: string, runId: string) {
  return request<RunTraceResponse>(`/api/v1/runs/${runId}/trace`, token)
}

export interface WorkflowItem {
  id: string
  user_id?: string
  owner_name?: string
  flow_code: string
  title: string
  form_data: Record<string, unknown>
  status: 'submitted' | 'approved' | 'rejected'
  created_at: string
}

export interface WorkflowListResponse {
  items: WorkflowItem[]
  total: number
  page: number
  page_size: number
}

/** scope='all' 为管理员审批视图（可见他人发起的流程）；默认 'mine' 只看自己的台账。 */
export function listWorkflows(token: string, flowCode = '', page = 1, pageSize = 8, scope: 'mine' | 'all' = 'mine') {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), scope })
  if (flowCode) params.set('flow_code', flowCode)
  return request<WorkflowListResponse>(`/api/v1/workflows?${params.toString()}`, token)
}

export function submitWorkflow(
  token: string,
  flow_code: string,
  form_data: Record<string, unknown>,
) {
  return request<WorkflowItem>('/api/v1/workflows', token, {
    method: 'POST',
    body: JSON.stringify({ flow_code, form_data }),
  })
}

export function updateWorkflowStatus(
  token: string,
  id: string,
  status: 'approved' | 'rejected',
  channel: 'form' | 'chat_card' = 'form',
) {
  return request<WorkflowItem>(`/api/v1/workflows/${id}/status`, token, {
    method: 'PATCH',
    body: JSON.stringify({ status, channel }),
  })
}

export interface WorkflowFieldDef {
  key: string
  label: string
  type: 'text' | 'number' | 'date' | 'select'
  required?: boolean
  options?: string[]
  default?: string | number
}

export interface WorkflowDefinition {
  flow_code: string
  name: string
  description: string
  allowed_roles: string[]
  fields: WorkflowFieldDef[]
}

export function fetchWorkflowSkills(token: string) {
  return request<WorkflowDefinition[]>('/api/v1/workflows/skills', token)
}

export function upsertWorkflowDefinition(token: string, payload: WorkflowDefinition) {
  return request<WorkflowDefinition>('/api/v1/workflows/definitions', token, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}


// BOM 相关接口已拆分至 ./bomClient.ts（物料/结构/试算/报价/齐套/公式校验）



export interface SysMenuItem {
  menu_key: string
  title: string
  group_name: string
  icon: string
  sort_order: number
  allowed_roles: string[]
  is_enabled: boolean
}

export function fetchVisibleMenus(token: string) {
  return request<SysMenuItem[]>('/api/v1/menus', token)
}

export function fetchAllMenus(token: string) {
  return request<SysMenuItem[]>('/api/v1/menus/all', token)
}

export function updateSysMenu(token: string, menuKey: string, payload: Omit<SysMenuItem, 'menu_key'>) {
  return request<SysMenuItem>(`/api/v1/menus/${menuKey}`, token, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

