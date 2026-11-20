<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useBom } from '../composables/useBom'
import BomItemPanel from './BomItemPanel.vue'
import BomSimpleQuote from './BomSimpleQuote.vue'
import BomTreeEditor from './BomTreeEditor.vue'

const props = defineProps<{ token: string }>()
const { loading, refreshItems, seedDemo } = useBom()
const subTab = ref<'simple' | 'tree' | 'items'>('simple')

async function handleSeed() {
  await seedDemo(props.token)
  subTab.value = 'tree'
}

onMounted(() => refreshItems(props.token))
</script>

<template>
  <section class="bom-shell">
    <header class="panel-head">
      <div>
        <h2>BOM 结构与工程算料维护 (独立库 bom_db)</h2>
        <p class="sub">左树右表多级递归 · 行内编辑 · 被引用防误删 · 3D 参数沙盒公式试算</p>
      </div>
      <div class="head-btns">
        <button class="btn" :class="{ 'btn-primary': subTab === 'simple' }" @click="subTab = 'simple'">极简报价模式</button>
        <button class="btn" :class="{ 'btn-primary': subTab === 'tree' }" @click="subTab = 'tree'">专家模式 (BOM 树)</button>
        <button class="btn" :class="{ 'btn-primary': subTab === 'items' }" @click="subTab = 'items'">2. 物料与资源主表</button>
        <button class="btn" :disabled="loading" @click="handleSeed">一键写入示例机柜 BOM</button>
      </div>
    </header>

    <BomSimpleQuote v-if="subTab === 'simple'" :token="token" @open-expert="subTab = 'tree'" />
    <BomTreeEditor v-else-if="subTab === 'tree'" :token="token" />
    <BomItemPanel v-else :token="token" />
  </section>
</template>

<style scoped>
.bom-shell { display: flex; flex-direction: column; gap: 14px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.head-btns { display: flex; gap: 6px; flex-wrap: wrap; }
</style>
