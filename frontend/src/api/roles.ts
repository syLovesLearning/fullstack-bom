export interface SysRoleItem {
  role_code: string
  role_name: string
  description: string
  allowed_tools: string[]
  is_system: boolean
  updated_at?: string
}

export interface ToolCatalogItem {
  name: string
  description: string
  parameters?: Record<string, unknown>
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8001'

async function req<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init.headers || {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

export function fetchRoles(token: string) {
  return req<SysRoleItem[]>('/api/v1/roles', token)
}

export function fetchToolsCatalog(token: string) {
  return req<ToolCatalogItem[]>('/api/v1/roles/tools-catalog', token)
}

export function upsertRole(token: string, payload: Omit<SysRoleItem, 'is_system' | 'updated_at'>) {
  return req<SysRoleItem>(`/api/v1/roles/${payload.role_code}`, token, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteRole(token: string, roleCode: string) {
  return req<{ deleted: boolean; role_code: string }>(`/api/v1/roles/${roleCode}`, token, {
    method: 'DELETE',
  })
}

export function deliverToolDemand(
  token: string,
  instanceId: string,
  payload: {
    dev_reply: string
    delivery_mode: 'EXTERNAL_SERVICE' | 'LOCAL_MODULE'
    menu_key: string
    menu_title: string
    external_url: string
    target_roles: string[]
    activate_menu: boolean
  },
) {
  return req<{ workflow: unknown; menu: unknown }>(`/api/v1/workflows/${instanceId}/deliver`, token, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createSysMenu(
  token: string,
  payload: {
    menu_key: string
    title: string
    group_name: string
    icon: string
    sort_order: number
    allowed_roles: string[]
    is_enabled: boolean
    external_url: string
  },
) {
  return req<unknown>('/api/v1/menus', token, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteSysMenu(token: string, menuKey: string) {
  return req<{ deleted: boolean }>(`/api/v1/menus/${menuKey}`, token, {
    method: 'DELETE',
  })
}

export async function downloadBomXlsx(
  token: string,
  rootId: string,
  params: { h: number; w: number; d: number; t: number },
  marginRate = 0.15,
  taxRate = 0.13,
) {
  const qs = new URLSearchParams({
    h: String(params.h),
    w: String(params.w),
    d: String(params.d),
    t: String(params.t),
    margin_rate: String(marginRate),
    tax_rate: String(taxRate),
  })
  const res = await fetch(`${API_BASE}/api/v1/bom/export-xlsx/${rootId}?${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`导出失败: HTTP ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `bom_quote_${rootId.slice(0, 8)}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}
