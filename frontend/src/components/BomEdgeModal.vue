<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { checkBomFormula, type FormulaCheckResult, type BomItem } from '../api/bomClient'

const props = defineProps<{
  visible: boolean
  token: string
  items: BomItem[]
  editingEdge: Record<string, any> | null
}>()
const emit = defineEmits<{ close: []; submit: [payload: Record<string, any>] }>()

const form = reactive({
  child_item_id: '', qty_mode: 'FIXED', base_qty: 1, formula_expr: '', extra_cost_expr: '',
  remnant_policy: 'CONTINUOUS', unit_pack_size: 1, min_remnant: 0, loss_rate: 0,
  float_factor: 1.0, bom_group: '材料', cost_group: '基材',
})

const formulaCheck = ref<FormulaCheckResult | null>(null)
const extraCheck = ref<FormulaCheckResult | null>(null)
const checking = ref(false)
const SANDBOX_ENV = { H: 2200, W: 800, D: 600, T: 2.0 }

watch(() => props.editingEdge, (val) => {
  formulaCheck.value = null
  extraCheck.value = null
  if (val) Object.assign(form, val)
  else Object.assign(form, {
    child_item_id: props.items[0]?.id || '', qty_mode: 'FIXED', base_qty: 1, formula_expr: '', extra_cost_expr: '',
    remnant_policy: 'CONTINUOUS', unit_pack_size: 1, min_remnant: 0, loss_rate: 0, float_factor: 1.0, bom_group: '材料', cost_group: '基材',
  })
}, { immediate: true })

async function validateExpr(target: 'formula' | 'extra') {
  const expr = target === 'formula' ? form.formula_expr : form.extra_cost_expr
  const holder = target === 'formula' ? formulaCheck : extraCheck
  if (!expr.trim() || !props.token) { holder.value = null; return }
  checking.value = true
  try { holder.value = await checkBomFormula(props.token, expr, SANDBOX_ENV) }
  finally { checking.value = false }
}

function insertTpl(target: 'formula' | 'extra', expr: string) {
  if (target === 'formula') { form.qty_mode = 'FORMULA_3D'; form.formula_expr = expr }
  else form.extra_cost_expr = expr
  void validateExpr(target)
}
</script>

<template>
  <div v-if="visible" class="modal-mask" @click.self="emit('close')">
    <div class="modal-box">
      <header class="m-head">
        <h3>{{ editingEdge ? '高级子件规则配置' : '新增子件与余料/特殊逻辑配置' }}</h3>
        <button class="btn" @click="emit('close')">✕</button>
      </header>

      <div class="grid-2">
        <label>子件物料
          <select v-model="form.child_item_id" class="inp" :disabled="!!editingEdge">
            <option v-for="c in items" :key="c.id" :value="c.id">{{ c.sku_code }} · {{ c.name }}</option>
          </select>
        </label>
        <label>计价模式
          <select v-model="form.qty_mode" class="inp">
            <option value="FIXED">固定数量 (FIXED)</option>
            <option value="FORMULA_3D">3D/条件公式 (FORMULA_3D)</option>
          </select>
        </label>
        <label>基准用量 <input v-model.number="form.base_qty" type="number" step="0.1" class="inp" /></label>
        <label>损耗率 (如 0.08) <input v-model.number="form.loss_rate" type="number" step="0.01" class="inp" /></label>
        <label>整料规格 (如 200) <input v-model.number="form.unit_pack_size" type="number" step="1" class="inp" /></label>
        <label>余料处理策略
          <select v-model="form.remnant_policy" class="inp">
            <option value="CONTINUOUS">连续按实计价</option>
            <option value="WHOLE_PACK">整料买单 (余料全废)</option>
            <option value="THRESHOLD_SCRAP">按最小留库阈值判定</option>
          </select>
        </label>
        <label v-if="form.remnant_policy === 'THRESHOLD_SCRAP'">最小留库阈值 (如 50)
          <input v-model.number="form.min_remnant" type="number" step="1" class="inp" />
        </label>
        <label>人工浮动系数 <input v-model.number="form.float_factor" type="number" step="0.05" class="inp" /></label>
        <label>BOM 向归类
          <select v-model="form.bom_group" class="inp"><option value="材料">材料</option><option value="人工">人工</option><option value="机械">机械</option></select>
        </label>
        <label>成本向归类
          <select v-model="form.cost_group" class="inp"><option value="半成品">半成品</option><option value="基材">基材</option><option value="人工费">人工费</option></select>
        </label>
      </div>

      <label v-if="form.qty_mode === 'FORMULA_3D'" class="full-lbl">用量公式 (`H/W/D/T`、`dist3d`、`iif`)
        <input v-model="form.formula_expr" class="inp" placeholder="例: iif(W >= 1000, base_qty * 1.2, base_qty)" @blur="validateExpr('formula')" />
        <div v-if="formulaCheck" :class="['check-line', formulaCheck.ok ? 'check-ok' : 'check-err']">
          {{ formulaCheck.ok ? `✓ 试算通过（沙盒 2200×800×600×2.0 → ${formulaCheck.value}）` : `✗ ${formulaCheck.error}` }}
        </div>
        <div class="tpl-row">
          <button class="chip" @click="insertTpl('formula', 'iif(W >= 1000, base_qty * 1.2, base_qty)')">宽度>=1000加量20%</button>
          <button class="chip" @click="insertTpl('formula', '(2*(H*W+H*D+W*D)/1000000.0)*T*7.85')">钢板展开重量</button>
        </div>
      </label>

      <label class="full-lbl">特殊附加成本公式 (元，可直接加减特殊料/工艺费)
        <input v-model="form.extra_cost_expr" class="inp" placeholder="例: iif(W >= 1000, 120, -10)" @blur="validateExpr('extra')" />
        <div v-if="extraCheck" :class="['check-line', extraCheck.ok ? 'check-ok' : 'check-err']">
          {{ extraCheck.ok ? `✓ 试算通过（沙盒 → ¥${extraCheck.value}）` : `✗ ${extraCheck.error}` }}
        </div>
        <div class="tpl-row">
          <button class="chip" @click="insertTpl('extra', 'iif(W >= 1000, 120, -10)')">iif(W>=1000, +120, -10)</button>
          <button class="chip" @click="insertTpl('extra', 'iif(qty > 150, 80, 0)')">超150加收特殊料费80</button>
        </div>
      </label>

      <footer class="m-foot">
        <button class="btn" @click="emit('close')">取消</button>
        <button class="btn btn-primary" @click="emit('submit', { ...form })">保存配置</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 120; }
.modal-box { background: #fff; width: 640px; max-width: 94vw; max-height: 90vh; overflow-y: auto; border-radius: 12px; padding: 18px; display: flex; flex-direction: column; gap: 12px; }
.m-head, .m-foot { display: flex; justify-content: space-between; align-items: center; }
.m-head h3 { margin: 0; font-size: 16px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.inp { padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; color: #0f172a; }
.tpl-row { display: flex; gap: 6px; margin-top: 4px; flex-wrap: wrap; }
.chip { font-size: 11px; padding: 3px 8px; border-radius: 999px; border: 1px solid #bfdbfe; background: #eff6ff; color: #1d4ed8; cursor: pointer; }
.check-line { font-size: 12px; margin-top: 2px; }
.check-ok { color: #15803d; }
.check-err { color: #d93025; }
</style>
