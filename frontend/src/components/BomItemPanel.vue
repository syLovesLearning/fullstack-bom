<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useBom } from '../composables/useBom'
import type { BomItem } from '../api/client'

const props = defineProps<{ token: string }>()
const { items, saveItem, removeItem } = useBom()

const keyword = ref('')
const catFilter = ref('ALL')
const errMsg = ref('')

const CATS = [
  { key: 'ALL', label: '全部' },
  { key: 'PRODUCT', label: '成品' },
  { key: 'SEMI_FINISHED', label: '半成品' },
  { key: 'BASE_MATERIAL', label: '基材' },
  { key: 'OUTSOURCED', label: '外购' },
  { key: 'LABOR', label: '人工' },
  { key: 'MACHINE', label: '机械' },
]

const itemForm = reactive<Omit<BomItem, 'id' | 'created_at'>>({
  sku_code: '', name: '', category: 'BASE_MATERIAL', sub_type: 'FIXED', unit: '个', base_price: 0,
})

const filteredItems = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return items.value.filter((i) => {
    const okCat = catFilter.value === 'ALL' || i.category === catFilter.value
    const okKw = !kw || i.sku_code.toLowerCase().includes(kw) || i.name.toLowerCase().includes(kw)
    return okCat && okKw
  })
})

async function handleSave() {
  errMsg.value = ''
  if (!itemForm.sku_code.trim() || !itemForm.name.trim()) return
  await saveItem(props.token, { ...itemForm, sku_code: itemForm.sku_code.trim(), name: itemForm.name.trim() })
  itemForm.sku_code = ''
  itemForm.name = ''
}

function fillEdit(it: BomItem) {
  Object.assign(itemForm, { sku_code: it.sku_code, name: it.name, category: it.category, sub_type: it.sub_type, unit: it.unit, base_price: it.base_price })
}

async function handleDelete(id: string) {
  errMsg.value = ''
  try {
    await removeItem(props.token, id)
  } catch (err) {
    errMsg.value = err instanceof Error ? err.message : String(err)
  }
}
</script>

<template>
  <div class="item-panel">
    <div class="filter-bar">
      <input v-model="keyword" class="search-inp" placeholder="搜索 SKU 编码或物料名称..." />
      <div class="cat-tabs">
        <button v-for="c in CATS" :key="c.key" class="chip" :class="{ active: catFilter === c.key }" @click="catFilter = c.key">
          {{ c.label }}
        </button>
      </div>
    </div>

    <div class="add-card">
      <input v-model="itemForm.sku_code" class="sel" placeholder="SKU (同名更新)" />
      <input v-model="itemForm.name" class="txt-input" placeholder="物料/半成品/人工名称..." />
      <select v-model="itemForm.category" class="sel">
        <option value="PRODUCT">成品</option><option value="SEMI_FINISHED">半成品</option>
        <option value="BASE_MATERIAL">基材</option><option value="OUTSOURCED">外购</option>
        <option value="LABOR">人工</option><option value="MACHINE">机械</option>
      </select>
      <select v-model="itemForm.sub_type" class="sel">
        <option value="FIXED">固定</option><option value="NON_FIXED">非固定</option>
        <option value="INTERNAL">人工(内)</option><option value="EXTERNAL">人工(外)</option>
        <option value="SPECIAL_PROCESS">特殊工艺</option><option value="STANDARD">标准</option>
      </select>
      <input v-model="itemForm.unit" class="sel" style="width: 58px" placeholder="单位" />
      <input v-model.number="itemForm.base_price" type="number" step="0.1" class="sel" style="width: 84px" placeholder="单价" />
      <button class="btn btn-primary" @click="handleSave">保存物料</button>
    </div>

    <p v-if="errMsg" class="err-line">{{ errMsg }}</p>

    <div class="table-wrap">
      <table>
        <thead><tr><th>SKU</th><th>名称</th><th>大类</th><th>子属性</th><th>单位</th><th>基准单价</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="it in filteredItems" :key="it.id">
            <td><span class="badge badge-blue">{{ it.sku_code }}</span></td>
            <td>{{ it.name }}</td><td>{{ it.category }}</td><td>{{ it.sub_type }}</td><td>{{ it.unit }}</td><td>¥ {{ it.base_price }}</td>
            <td>
              <button class="btn" @click="fillEdit(it)">编辑</button>
              <button class="btn" style="margin-left: 6px" @click="handleDelete(it.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!filteredItems.length"><td colspan="7" class="empty">无匹配物料记录。</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.item-panel { display: flex; flex-direction: column; gap: 12px; }
.filter-bar { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.search-inp { padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; width: 240px; font-size: 13px; }
.cat-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { padding: 5px 10px; border-radius: 999px; border: 1px solid var(--border); background: #fff; font-size: 12px; cursor: pointer; }
.chip.active { background: #2563eb; color: #fff; border-color: #2563eb; }
.add-card { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; background: var(--card); border: 1px solid var(--border); padding: 12px; border-radius: 10px; }
.sel { padding: 7px 8px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: #fff; }
.txt-input { flex: 1; min-width: 150px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
th { background: #f9fafb; color: var(--muted); font-weight: 600; }
.empty { text-align: center; color: var(--muted); padding: 20px; }
.err-line { color: var(--err); font-size: 13px; margin: 0; background: var(--err-soft); padding: 8px 12px; border-radius: 8px; }
</style>
