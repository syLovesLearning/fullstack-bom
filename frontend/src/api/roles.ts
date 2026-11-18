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

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

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
