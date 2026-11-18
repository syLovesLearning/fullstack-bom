/** 公式 AI 录入三步状态机：口述 → 测试数据 → 验证录入。 */
import { computed, ref } from 'vue'
import {
  batchCheckBomFormula,
  downloadBomFormulaTemplate,
  draftBomFormula,
  parseBomFormulaSheet,
  type BatchCheck,
  type FormulaDraft,
  type FormulaTarget,
  type SheetRow,
} from '../api/bomFormulaClient'

export function useBomFormulaStudio() {
  const step = ref<1 | 2 | 3>(1)
  const target = ref<FormulaTarget>('qty')
  const intent = ref('')
  const expr = ref('')
  const draft = ref<FormulaDraft | null>(null)
  const rows = ref<SheetRow[]>([])
  const warnings = ref<string[]>([])
  const result = ref<BatchCheck | null>(null)
  const fileName = ref('')
  const busy = ref(false)
  const errorMsg = ref('')
  const notice = ref('')

  const canDraft = computed(() => intent.value.trim().length >= 4 && !busy.value)
  const canCheck = computed(() => expr.value.trim().length > 0 && rows.value.length > 0 && !busy.value)
  const allOk = computed(() => result.value?.all_ok === true)

  function reset(next: FormulaTarget, initialExpr = '') {
    step.value = 1
    target.value = next
    intent.value = ''
    expr.value = initialExpr
    draft.value = null
    rows.value = []
    warnings.value = []
    result.value = null
    fileName.value = ''
    errorMsg.value = ''
    notice.value = ''
    busy.value = false
  }

  async function guard<T>(task: () => Promise<T>): Promise<T | null> {
    busy.value = true
    errorMsg.value = ''
    notice.value = ''
    try {
      return await task()
    } catch (err) {
      errorMsg.value = err instanceof Error ? err.message : String(err)
      return null
    } finally {
      busy.value = false
    }
  }

  async function runDraft(token: string) {
    const data = await guard(() => draftBomFormula(token, { intent: intent.value.trim(), target: target.value }))
    if (!data) return
    draft.value = data
    if (data.expr) expr.value = data.expr
    if (!data.ok) errorMsg.value = data.error || '未能生成可求值的公式，请换一种说法'
    else notice.value = `已生成公式，消耗 ${data.tokens} tokens`
  }

  async function downloadTemplate(token: string) {
    const name = await guard(() => downloadBomFormulaTemplate(token, target.value, expr.value))
    if (name) notice.value = `模板已下载：${name}，请填好 H/W/D/T 与预期结果后上传`
  }

  async function upload(token: string, file: File) {
    const parsed = await guard(() => parseBomFormulaSheet(token, file))
    if (!parsed) return
    rows.value = parsed.rows
    warnings.value = parsed.warnings
    fileName.value = file.name
    result.value = null
    notice.value = `已解析 ${parsed.rows.length} 行，可先修正预期结果再验证`
  }

  function setExpected(index: number, raw: string) {
    const row = rows.value.find((r) => r.index === index)
    if (!row) return
    const text = String(raw).trim()
    row.expected = text === '' ? null : Number(text)
    result.value = null
  }

  function removeRow(index: number) {
    rows.value = rows.value.filter((r) => r.index !== index)
    result.value = null
  }

  function addRow() {
    const base = rows.value[rows.value.length - 1]?.env ?? { H: 2200, W: 800, D: 600, T: 2.0, base_qty: 1, qty: 1 }
    rows.value = [...rows.value, { index: rows.value.length + 1, env: { ...base }, expected: null, note: '' }]
    result.value = null
  }

  async function runCheck(token: string) {
    const data = await guard(() => batchCheckBomFormula(token, expr.value.trim(), rows.value))
    if (!data) return false
    result.value = data
    if (data.all_ok) notice.value = `全部校验通过：${data.total} 行（含 ${data.no_expect} 行仅回显）`
    else if (data.total > 0 && data.no_expect === data.total) errorMsg.value = '所有行都没填预期结果，请至少填 1 行预期值，否则无法判定公式是否符合业务'
    else errorMsg.value = `未通过：失败 ${data.failed} 行，求值异常 ${data.errors} 行`
    return data.all_ok
  }

  async function goNext(token: string): Promise<boolean> {
    if (step.value === 1) {
      if (!expr.value.trim()) {
        errorMsg.value = '请先生成或手填公式'
        return false
      }
      step.value = 2
      return true
    }
    if (step.value === 2) {
      if (!rows.value.length) {
        errorMsg.value = '请先下载模板填写并上传，或直接点「手工添加行」'
        return false
      }
      step.value = 3
      await runCheck(token)
      return true
    }
    return false
  }

  function goBack() {
    if (step.value > 1) step.value = (step.value - 1) as 1 | 2
    errorMsg.value = ''
  }

  return {
    step, target, intent, expr, draft, rows, warnings, result, fileName, busy, errorMsg, notice,
    canDraft, canCheck, allOk,
    reset, runDraft, downloadTemplate, upload, setExpected, removeRow, addRow, runCheck, goNext, goBack,
  }
}
