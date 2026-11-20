<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useBom } from '../composables/useBom'
import { downloadBomXlsx } from '../api/roles'
import Bom3DPreview from './Bom3DPreview.vue'

const props = defineProps<{ token: string }>()
const emit = defineEmits<{ openExpert: [] }>()

const { items, rollup, sandbox3d, refreshTreeOnly, createQuote } = useBom()
const rootId = ref('')
const marginPct = ref(15)
const taxPct = ref(13)
const msg = ref('')
const errMsg = ref('')

const products = computed(() => items.value.filter((i) => i.category === 'PRODUCT'))
const directCost = computed(() => Number(rollup.value?.root?.subtotal ?? 0))
const finalPrice = computed(() => +(directCost.value * (1 + marginPct.value / 100) * (1 + taxPct.value / 100)).toFixed(2))

watch(products, (list) => {
  if (list.length && !rootId.value) {
    rootId.value = list[0].id
    void refreshTreeOnly(props.token, rootId.value)
  }
}, { immediate: true })

async function onChangeProduct() {
  if (rootId.value) await refreshTreeOnly(props.token, rootId.value)
}

async function saveSnap() {
  if (!rootId.value) return
  errMsg.value = ''; msg.value = ''
  try {
    const q = await createQuote(props.token, rootId.value, '极简报价模式快照', marginPct.value / 100, taxPct.value / 100)
    msg.value = `已保存报价单 ${q.quote_no}（含税 ¥${q.final_price}）`
  } catch (e) { errMsg.value = e instanceof Error ? e.message : String(e) }
}

async function exportXlsx() {
  if (!rootId.value) return
  errMsg.value = ''
  try {
    await downloadBomXlsx(props.token, rootId.value, sandbox3d.value, marginPct.value / 100, taxPct.value / 100)
    msg.value = 'Excel 报价单 (.xlsx) 已开始下载。'
  } catch (e) { errMsg.value = e instanceof Error ? e.message : String(e) }
}

onMounted(() => {
  if (products.value.length && !rootId.value) {
    rootId.value = products.value[0].id
    void refreshTreeOnly(props.token, rootId.value)
  }
})
</script>

<template>
  <div class="simple-grid">
    <section class="ctrl-card">
      <div class="step-head"><strong>① 选择产品</strong><button class="link-btn" @click="emit('openExpert')">切到专家模式 →</button></div>
      <select v-model="rootId" class="inp" @change="onChangeProduct">
        <option v-for="p in products" :key="p.id" :value="p.id">{{ p.sku_code }} · {{ p.name }}</option>
      </select>

      <strong style="margin-top: 8px">② 调整三维尺寸 (mm)</strong>
      <label><span>高 H：<b>{{ sandbox3d.h }}</b> mm</span><input v-model.number="sandbox3d.h" type="range" min="700" max="2600" step="50" @change="onChangeProduct" /></label>
      <label><span>宽 W：<b>{{ sandbox3d.w }}</b> mm</span><input v-model.number="sandbox3d.w" type="range" min="600" max="2400" step="50" @change="onChangeProduct" /></label>
      <label><span>深 D：<b>{{ sandbox3d.d }}</b> mm</span><input v-model.number="sandbox3d.d" type="range" min="400" max="1200" step="50" @change="onChangeProduct" /></label>
      <label><span>板厚 T：<b>{{ sandbox3d.t }}</b> mm</span><input v-model.number="sandbox3d.t" type="range" min="1" max="5" step="0.5" @change="onChangeProduct" /></label>

      <div class="rate-row">
        <label><span>毛利 %</span><input v-model.number="marginPct" type="number" class="inp" min="0" max="80" /></label>
        <label><span>税率 %</span><input v-model.number="taxPct" type="number" class="inp" min="0" max="30" /></label>
      </div>

      <div class="price-box">
        <div><span>直接成本</span><strong>¥{{ directCost.toFixed(2) }}</strong></div>
        <div class="final"><span>含税报价</span><strong>¥{{ finalPrice.toFixed(2) }}</strong></div>
      </div>

      <div class="act-row">
        <button class="btn btn-primary" @click="exportXlsx">⬇ 导出 Excel 报价单</button>
        <button class="btn" @click="saveSnap">保存报价快照</button>
      </div>
      <p v-if="msg" class="ok-txt">{{ msg }}</p>
      <p v-if="errMsg" class="err-txt">{{ errMsg }}</p>
    </section>

    <section class="view-card">
      <Bom3DPreview :params="sandbox3d" :rollup="rollup" :margin-pct="marginPct" :tax-pct="taxPct" />
    </section>
  </div>
</template>

<style scoped>
.simple-grid { display: grid; grid-template-columns: 360px 1fr; gap: 16px; align-items: start; }
@media (max-width: 960px) { .simple-grid { grid-template-columns: 1fr; } }
.ctrl-card, .view-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.step-head { display: flex; justify-content: space-between; align-items: center; }
.link-btn { border: none; background: none; color: #2563eb; font-size: 12px; cursor: pointer; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.inp { padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; color: var(--text); background: #fff; }
.rate-row, .act-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.price-box { background: #f8fafc; border: 1px solid var(--border); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.price-box > div { display: flex; justify-content: space-between; }
.price-box .final { font-size: 16px; color: #047857; border-top: 1px dashed var(--border); padding-top: 6px; }
.ok-txt { margin: 0; font-size: 12px; color: #047857; }
.err-txt { margin: 0; font-size: 12px; color: var(--err); }
</style>
