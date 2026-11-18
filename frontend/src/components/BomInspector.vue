<script setup lang="ts">
/** 属性检查器：选中卡片后就地改量/公式/余料策略，公式失焦或停止输入即试算。 */
import { reactive, ref, watch } from 'vue'
import { checkBomFormula, type BomEdge, type BomEdgeRule, type BomNode, type FormulaCheckResult } from '../api/bomClient'

const props = defineProps<{
  token: string
  node: BomNode | null
  edge: BomEdge | null
  params: { h: number; w: number; d: number; t: number }
}>()
const emit = defineEmits<{ save: [rule: BomEdgeRule]; remove: [] }>()

const blank: BomEdgeRule = {
  qty_mode: 'FIXED', base_qty: 1, formula_expr: '', extra_cost_expr: '',
  remnant_policy: 'CONTINUOUS', unit_pack_size: 1, min_remnant: 0, loss_rate: 0,
  float_factor: 1, bom_group: '材料', cost_group: '基材',
}
const form = reactive<BomEdgeRule>({ ...blank })
const check = ref<FormulaCheckResult | null>(null)
const checking = ref(false)
let timer: number | undefined

watch(() => props.edge, (e) => {
  if (e) Object.assign(form, {
    qty_mode: e.qty_mode, base_qty: e.base_qty, formula_expr: e.formula_expr,
    extra_cost_expr: e.extra_cost_expr || '', remnant_policy: e.remnant_policy || 'CONTINUOUS',
    unit_pack_size: e.unit_pack_size ?? 1, min_remnant: e.min_remnant ?? 0,
    loss_rate: e.loss_rate ?? 0, float_factor: e.float_factor,
    bom_group: e.bom_group, cost_group: e.cost_group,
  })
  check.value = null
}, { immediate: true })

watch(() => [form.qty_mode, form.formula_expr], () => {
  window.clearTimeout(timer)
  check.value = null
  if (form.qty_mode !== 'FORMULA_3D' || !form.formula_expr.trim()) return
  checking.value = true
  timer = window.setTimeout(async () => {
    try {
      check.value = await checkBomFormula(props.token, form.formula_expr, {
        H: props.params.h, W: props.params.w, D: props.params.d, T: props.params.t,
      })
    } catch { check.value = { ok: false, value: null, error: '试算服务不可用' } }
    finally { checking.value = false }
  }, 300)
})

function submit() { emit('save', { ...form }) }
function step(delta: number) {
  form.base_qty = Math.max(0.01, +(form.base_qty + delta).toFixed(3))
}
</script>

<template>
  <aside class="inspector">
    <div class="i-head"><strong>属性检查器</strong></div>
    <template v-if="node && edge">
      <p class="target">{{ node.name }}<span>{{ node.sku_code }}</span></p>
      <div class="metrics">
        <div><label>当前用量</label><b>{{ node.qty }} {{ node.unit }}</b></div>
        <div><label>本行小计</label><b>¥{{ node.subtotal }}</b></div>
      </div>

      <label class="fld">用量模式
        <div class="seg">
          <button :class="{ on: form.qty_mode === 'FIXED' }" @click="form.qty_mode = 'FIXED'">固定量</button>
          <button :class="{ on: form.qty_mode === 'FORMULA_3D' }" @click="form.qty_mode = 'FORMULA_3D'">3D 公式</button>
        </div>
      </label>

      <label v-if="form.qty_mode === 'FIXED'" class="fld">基础用量
        <div class="stepper">
          <button @click="step(-1)">−</button>
          <input v-model.number="form.base_qty" type="number" min="0.01" step="1" />
          <button @click="step(1)">＋</button>
        </div>
      </label>

      <label v-else class="fld">用量公式 <small>H/W/D/T · dist3d · iif · ceil</small>
        <input v-model="form.formula_expr" class="inp mono" placeholder="(2*(H*W+H*D+W*D)/1000000)*T*7.85" />
        <span v-if="checking" class="hint">试算中…</span>
        <span v-else-if="check && check.ok" class="ok">✓ 试算 {{ check.value }}（当前 3D 参数下）</span>
        <span v-else-if="check" class="err">✗ {{ check.error }}</span>
      </label>

      <label class="fld">附加成本公式
        <input v-model="form.extra_cost_expr" class="inp mono" placeholder="iif(W >= 1000, 120, -10)" />
      </label>

      <label class="fld">余料策略
        <select v-model="form.remnant_policy" class="inp">
          <option value="CONTINUOUS">CONTINUOUS 连续套裁</option>
          <option value="WHOLE_PACK">WHOLE_PACK 整料取整</option>
          <option value="THRESHOLD_SCRAP">THRESHOLD_SCRAP 阈值报废</option>
        </select>
      </label>
      <div class="grid3">
        <label class="fld">整料规格<input v-model.number="form.unit_pack_size" class="inp" type="number" min="0.01" /></label>
        <label class="fld">留库阈值<input v-model.number="form.min_remnant" class="inp" type="number" min="0" /></label>
        <label class="fld">损耗率<input v-model.number="form.loss_rate" class="inp" type="number" min="0" max="1" step="0.01" /></label>
      </div>
      <div class="grid3">
        <label class="fld">浮动系数<input v-model.number="form.float_factor" class="inp" type="number" min="0.5" max="2" step="0.05" /></label>
        <label class="fld">BOM 向
          <select v-model="form.bom_group" class="inp"><option>人工</option><option>材料</option><option>机械</option></select>
        </label>
        <label class="fld">成本向
          <select v-model="form.cost_group" class="inp"><option>半成品</option><option>基材</option><option>人工费</option></select>
        </label>
      </div>

      <div class="actions">
        <button class="btn btn-primary" @click="submit">保存并重算</button>
        <button class="btn btn-danger" @click="emit('remove')">移除此行</button>
      </div>
      <p class="foot">保存后本卡与所有祖先卡金额同步更新，可用 ⌘Z 撤销。</p>
    </template>
    <div v-else class="empty">点击画布中的一张卡片<br />在此编辑用量与成本规则</div>
  </aside>
</template>

<style scoped>
.inspector { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px; min-height: 420px; }
.i-head { font-size: 13px; }
.target { margin: 0; font-size: 12px; font-weight: 500; }
.target span { display: block; font-size: 11px; color: var(--muted); font-weight: 400; margin-top: 2px; }
.metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.metrics div { background: #f8fafc; border-radius: 7px; padding: 8px; }
.metrics label { display: block; font-size: 11px; color: var(--muted); }
.metrics b { font-size: 14px; }
.fld { display: block; font-size: 11px; color: var(--muted); }
.fld small { font-size: 10px; color: #94a3b8; }
.inp { width: 100%; box-sizing: border-box; margin-top: 4px; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; background: #fff; color: #0f172a; }
.mono { font-family: ui-monospace, monospace; font-size: 11px; }
.seg { display: flex; gap: 5px; margin-top: 4px; }
.seg button { flex: 1; font-size: 11px; padding: 5px; border: 1px solid var(--border); background: #fff; border-radius: 6px; cursor: pointer; }
.seg button.on { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.stepper { display: flex; align-items: center; gap: 4px; margin-top: 4px; }
.stepper button { width: 28px; height: 28px; border: 1px solid var(--border); background: #fff; border-radius: 6px; cursor: pointer; }
.stepper input { flex: 1; min-width: 0; text-align: center; padding: 5px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; }
.grid3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.hint, .ok, .err { display: block; font-size: 11px; margin-top: 4px; }
.hint { color: var(--muted); } .ok { color: #047857; } .err { color: #dc2626; }
.actions { display: flex; gap: 6px; margin-top: auto; }
.btn { flex: 1; font-size: 12px; padding: 7px; border: 1px solid var(--border); background: #fff; border-radius: 7px; cursor: pointer; }
.btn-primary { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
.btn-danger { color: #dc2626; border-color: #fecaca; }
.foot, .empty { font-size: 11px; color: var(--muted); margin: 0; }
.empty { text-align: center; padding-top: 60px; line-height: 1.8; }
</style>
