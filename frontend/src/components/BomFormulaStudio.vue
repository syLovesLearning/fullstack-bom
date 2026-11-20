<script setup lang="ts">
import { ref, watch } from 'vue'
import BomFormulaTestTable from './BomFormulaTestTable.vue'
import { useBomFormulaStudio } from '../composables/useBomFormulaStudio'

const props = defineProps<{
  visible: boolean
  token: string
  target: 'qty' | 'extra'
  initialExpr?: string
}>()
const emit = defineEmits<{ close: []; apply: [payload: { target: 'qty' | 'extra'; expr: string }] }>()

const {
  step, intent, expr, draft, rows, warnings, result, fileName, busy, errorMsg, notice, canDraft, allOk,
  reset, runDraft, downloadTemplate, upload, setExpected, removeRow, addRow, runCheck, goNext, goBack,
} = useBomFormulaStudio()
const fileInput = ref<HTMLInputElement | null>(null)
const EXAMPLES = [
  '柜体宽度≥1000mm 时每台加收 120 元特殊工艺费，否则减 10 元',
  '钢板用量按展开面积算：(2*(H*W+H*D+W*D)/1000000)*T*7.85',
  '数量超过 150 台时，每台再加 80 元加急费',
  '宽度超过 1200 时铜排用量多算 20%',
]
const STEPS = ['口述逻辑', '测试数据', '验证录入']

watch(() => props.visible, (v) => {
  if (v) reset(props.target, props.initialExpr || '')
}, { immediate: true })

async function onFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) await upload(props.token, file)
  input.value = ''
}

function applyFormula() {
  const value = expr.value.trim()
  if (!value || !allOk.value) return
  emit('apply', { target: props.target, expr: value })
}
</script>

<template>
  <div v-if="visible" class="mask" @click.self="emit('close')">
    <div class="box">
      <header class="head">
        <div>
          <h3>AI 录入{{ target === 'qty' ? '用量公式' : '附加成本公式' }}</h3>
          <div class="steps">
            <span v-for="(label, i) in STEPS" :key="label" class="stp" :class="{ on: step === i + 1, done: step > i + 1 }">
              <b>{{ i + 1 }}</b>{{ label }}
            </span>
          </div>
        </div>
        <button class="btn" @click="emit('close')">✕</button>
      </header>

      <div class="body">
        <!-- 第 1 步：口述 -->
        <section v-if="step === 1" class="pane">
          <p class="hint">用中文把规则说清楚，AI 会编译成受限 DSL 表达式（只允许四则、比较、<code>iif</code>、<code>dist3d</code> 等白名单函数，不会执行任意代码）。</p>
          <textarea v-model="intent" class="ta" rows="4" placeholder="例：柜体宽度 ≥ 1000mm 时，每台加收 120 元特殊工艺费；否则按标准柜减 10 元" />
          <div class="chips">
            <button v-for="eg in EXAMPLES" :key="eg" class="chip" @click="intent = eg">{{ eg.slice(0, 22) }}…</button>
          </div>
          <div class="row-btns">
            <button class="btn btn-primary" :disabled="!canDraft" @click="runDraft(token)">{{ busy ? '生成中…' : '✨ 让 AI 生成公式' }}</button>
            <button v-if="draft?.ok && expr.trim()" class="btn" @click="emit('apply', { target: props.target, expr: expr.trim() })">✓ 直接采纳此公式</button>
          </div>

          <div v-if="draft" class="draft-card">
            <label class="lbl">公式（可直接改）
              <input v-model="expr" class="inp mono" />
            </label>
            <p v-if="draft.explain" class="explain">{{ draft.explain }}</p>
            <ol v-if="draft.steps.length" class="steps-list">
              <li v-for="(s, i) in draft.steps" :key="i">{{ s }}</li>
            </ol>
            <ul v-if="draft.assumptions.length" class="assume">
              <li v-for="(a, i) in draft.assumptions" :key="i">假设：{{ a }}</li>
            </ul>
            <div v-if="draft.samples.length" class="samples">
              <div class="s-head">样例求值（点「下一步」可下载模板批量验证）</div>
              <table>
                <thead><tr><th>H</th><th>W</th><th>D</th><th>T</th><th>qty</th><th>结果</th></tr></thead>
                <tbody>
                  <tr v-for="(s, i) in draft.samples" :key="i">
                    <td>{{ s.env.H }}</td><td>{{ s.env.W }}</td><td>{{ s.env.D }}</td>
                    <td>{{ s.env.T }}</td><td>{{ s.env.qty }}</td>
                    <td class="val">{{ s.error ? s.error : s.value }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <!-- 第 2 步：测试数据 -->
        <section v-else-if="step === 2" class="pane">
          <ol class="howto">
            <li>下载 Excel 模板（已带 3 行常用尺寸，第二张表写明变量与判定口径）</li>
            <li>填 <b>H/W/D/T</b> 尺寸与业务上的 <b>预期结果</b>（留空表示只回显不判定）</li>
            <li>上传回来 → 下一步自动逐行核对</li>
          </ol>
          <div class="row-btns">
            <button class="btn" :disabled="busy" @click="downloadTemplate(token)">⬇ 下载 Excel 模板</button>
            <button class="btn" :disabled="busy" @click="fileInput?.click()">⬆ 上传填好的文件</button>
            <input ref="fileInput" type="file" accept=".xlsx,.xlsm,.csv" hidden @change="onFile" />
            <button class="btn" @click="addRow()">＋ 手工加一行</button>
            <span v-if="fileName" class="file-tag">{{ fileName }} · {{ rows.length }} 行</span>
          </div>
          <ul v-if="warnings.length" class="warns"><li v-for="w in warnings" :key="w">⚠ {{ w }}</li></ul>
          <BomFormulaTestTable :rows="rows" editable @expected="setExpected" @remove="removeRow" />
        </section>

        <!-- 第 3 步：验证录入 -->
        <section v-else class="pane">
          <div class="expr-line">当前公式：<code>{{ expr }}</code></div>
          <div v-if="result" class="sum-bar" :class="allOk ? 'ok' : 'bad'">
            <b>{{ allOk ? '✓ 全部通过' : '✗ 存在未通过' }}</b>
            <span>共 {{ result.total }} 行</span>
            <span>通过 {{ result.passed }}</span>
            <span>失败 {{ result.failed }}</span>
            <span>异常 {{ result.errors }}</span>
            <span>仅回显 {{ result.no_expect }}</span>
          </div>
          <BomFormulaTestTable :rows="rows" :results="result?.rows" />
          <div class="row-btns">
            <button class="btn" :disabled="busy" @click="runCheck(token)">{{ busy ? '核对中…' : '↻ 重新核对' }}</button>
            <span v-if="result && !allOk" class="tip">可直接在上一步改预期结果，或回第 1 步重述规则后再验证</span>
          </div>
        </section>
      </div>

      <div v-if="errorMsg" class="msg-err">{{ errorMsg }}</div>
      <div v-else-if="notice" class="msg-ok">{{ notice }}</div>

      <footer class="foot">
        <button v-if="step > 1" class="btn" @click="goBack()">上一步</button>
        <div class="spacer" />
        <button class="btn" @click="emit('close')">取消</button>
        <button v-if="step < 3" class="btn btn-primary" :disabled="busy" @click="goNext(token)">下一步</button>
        <button v-else class="btn btn-primary" :disabled="!allOk" @click="applyFormula">✓ 写入公式</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 130; }
.box { background: #fff; width: 880px; max-width: 95vw; max-height: 92vh; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
.head { display: flex; justify-content: space-between; align-items: flex-start; padding: 14px 16px 10px; border-bottom: 1px solid var(--border); }
.head h3 { margin: 0 0 8px; font-size: 15px; }
.steps { display: flex; gap: 14px; }
.stp { font-size: 12px; color: #94a3b8; display: flex; align-items: center; gap: 5px; }
.stp b { width: 17px; height: 17px; border-radius: 50%; background: #e2e8f0; color: #64748b; font-size: 11px; display: grid; place-items: center; }
.stp.on { color: #1d4ed8; font-weight: 600; }
.stp.on b { background: #1d4ed8; color: #fff; }
.stp.done b { background: #dcfce7; color: #15803d; }
.body { padding: 14px 16px; overflow-y: auto; flex: 1; }
.pane { display: flex; flex-direction: column; gap: 10px; }
.hint { margin: 0; font-size: 12px; color: var(--muted); line-height: 1.6; }
.hint code, .expr-line code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.ta { width: 100%; box-sizing: border-box; padding: 9px 11px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; resize: vertical; color: #0f172a; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { font-size: 11px; padding: 3px 9px; border-radius: 999px; border: 1px solid #bfdbfe; background: #eff6ff; color: #1d4ed8; cursor: pointer; }
.draft-card { border: 1px solid #dbeafe; background: #f8fbff; border-radius: 9px; padding: 11px; display: flex; flex-direction: column; gap: 8px; }
.lbl { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.inp { padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; color: #0f172a; background: #fff; }
.explain { margin: 0; font-size: 12.5px; color: #1e293b; }
.steps-list { margin: 0; padding-left: 18px; font-size: 12px; color: #334155; line-height: 1.7; }
.assume { margin: 0; padding-left: 16px; font-size: 11.5px; color: #92400e; background: #fffbeb; border-radius: 6px; padding: 6px 6px 6px 20px; }
.samples { font-size: 12px; }
.s-head { color: var(--muted); margin-bottom: 4px; font-size: 11.5px; }
.samples table { border-collapse: collapse; width: 100%; }
.samples th { text-align: left; font-weight: 600; color: var(--muted); padding: 3px 8px; background: #eff6ff; }
.samples td { padding: 3px 8px; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; font-variant-numeric: tabular-nums; }
.val { font-weight: 600; color: #1d4ed8; }
.howto { margin: 0; padding-left: 18px; font-size: 12.5px; color: #334155; line-height: 1.8; }
.row-btns { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 12px; }
.file-tag { color: #15803d; font-size: 11.5px; }
.warns { margin: 0; padding-left: 16px; color: #92400e; font-size: 11.5px; }
.expr-line { font-size: 12px; color: var(--muted); }
.expr-line code { color: #1d4ed8; background: #eff6ff; padding: 2px 6px; border-radius: 5px; }
.sum-bar { display: flex; gap: 12px; align-items: center; font-size: 12px; padding: 7px 11px; border-radius: 8px; flex-wrap: wrap; }
.sum-bar.ok { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }
.sum-bar.bad { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.tip { color: var(--muted); font-size: 11.5px; }
.msg-err, .msg-ok { margin: 0 16px 8px; font-size: 12px; padding: 7px 10px; border-radius: 7px; }
.msg-err { background: #fef2f2; color: #b91c1c; }
.msg-ok { background: #f0fdf4; color: #15803d; }
.foot { display: flex; gap: 8px; align-items: center; padding: 11px 16px; border-top: 1px solid var(--border); }
.spacer { flex: 1; }
.btn { padding: 6px 13px; border: 1px solid var(--border); background: #fff; border-radius: 6px; font-size: 12.5px; cursor: pointer; color: #0f172a; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
</style>
