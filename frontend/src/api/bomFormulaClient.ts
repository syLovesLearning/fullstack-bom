/** 公式 AI 录入接口：口述编译 / 模板下载 / 上传解析 / 批量校验。 */
import { request } from './client'

export type FormulaTarget = 'qty' | 'extra'

export interface FormulaSample {
  env: Record<string, number>
  value: number | null
  error: string
}

export interface FormulaDraft {
  ok: boolean
  expr: string
  explain: string
  steps: string[]
  assumptions: string[]
  samples: FormulaSample[]
  error: string
  tokens: number
}

export interface SheetRow {
  index: number
  env: Record<string, number>
  expected: number | null
  note: string
}

export interface ParsedSheet {
  rows: SheetRow[]
  warnings: string[]
  skipped: number
}

export type RowStatus = 'pass' | 'fail' | 'no_expect' | 'error'

export interface BatchRowResult {
  index: number
  env: Record<string, number>
  expected: number | null
  actual: number | null
  diff: number | null
  status: RowStatus
  error: string
  note: string
}

export interface BatchCheck {
  expr: string
  total: number
  passed: number
  failed: number
  errors: number
  no_expect: number
  all_ok: boolean
  summary: { min: number | null; max: number | null; avg: number | null }
  rows: BatchRowResult[]
}

async function authFetch(url: string, token: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
  const resp = await fetch(url, { ...init, headers })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      detail = (body as { detail?: string }).detail || detail
    } catch { /* 非 JSON 错误体，保留状态码 */ }
    throw new Error(detail)
  }
  return resp
}

export function draftBomFormula(
  token: string,
  payload: { intent: string; target: FormulaTarget; env?: Record<string, number>; base_qty?: number; qty?: number },
) {
  return request<FormulaDraft>('/api/v1/bom/formula/draft', token, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function batchCheckBomFormula(token: string, expr: string, rows: SheetRow[]) {
  return request<BatchCheck>('/api/v1/bom/formula/batch-check', token, {
    method: 'POST',
    body: JSON.stringify({ expr, rows }),
  })
}

export async function parseBomFormulaSheet(token: string, file: File): Promise<ParsedSheet> {
  const form = new FormData()
  form.append('file', file)
  const resp = await authFetch('/api/v1/bom/formula/parse-sheet', token, { method: 'POST', body: form })
  return (await resp.json()) as ParsedSheet
}

export async function downloadBomFormulaTemplate(token: string, target: FormulaTarget, expr: string): Promise<string> {
  const qs = `?target=${target}&expr=${encodeURIComponent(expr.slice(0, 400))}`
  const resp = await authFetch(`/api/v1/bom/formula/template${qs}`, token)
  const disposition = resp.headers.get('Content-Disposition') || ''
  const matched = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  const filename = matched ? decodeURIComponent(matched[1]) : `BOM公式测试数据_${target}.xlsx`
  const url = URL.createObjectURL(await resp.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
  return filename
}
