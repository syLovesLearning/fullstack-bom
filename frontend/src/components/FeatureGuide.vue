<script setup lang="ts">
import { computed, ref } from 'vue'
import { FEATURE_DOCS } from '../data/featureDocs'

const emit = defineEmits<{ navigate: [menuKey: string] }>()

const keyword = ref('')
const activeCategory = ref<'全部' | '业务中心' | 'AI 与记忆' | '系统管理' | '基础底座'>('全部')
const categories = ['全部', '业务中心', 'AI 与记忆', '系统管理', '基础底座'] as const

const filteredDocs = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return FEATURE_DOCS.filter((item) => {
    if (activeCategory.value !== '全部' && item.category !== activeCategory.value) return false
    if (!q) return true
    return (
      item.title.toLowerCase().includes(q) ||
      item.subtitle.toLowerCase().includes(q) ||
      item.capabilities.some((c) => c.toLowerCase().includes(q)) ||
      item.steps.some((s) => s.toLowerCase().includes(q))
    )
  })
})
</script>

<template>
  <section class="guide-page">
    <header class="guide-hero">
      <div>
        <h2>项目功能文档清单 & 快速使用说明</h2>
        <p class="sub">集中梳理系统内所有已落地模块的能力边界、操作步骤与快速入口，方便内部上手与对外演示。</p>
      </div>
      <div class="stat-pills">
        <span class="pill">已收录 {{ FEATURE_DOCS.length }} 大模块</span>
        <span class="pill pill-b">实时联动导航</span>
      </div>
    </header>

    <div class="filter-bar">
      <div class="cat-tabs">
        <button
          v-for="cat in categories"
          :key="cat"
          class="btn"
          :class="{ 'btn-primary': activeCategory === cat }"
          @click="activeCategory = cat"
        >
          {{ cat }}
        </button>
      </div>
      <input v-model="keyword" class="search-inp" placeholder="搜索功能关键词，如 BOM、权限、微服务、记忆..." />
    </div>

    <div class="doc-grid">
      <article v-for="doc in filteredDocs" :key="doc.key" class="doc-card">
        <div class="doc-head">
          <div>
            <span class="cat-tag">{{ doc.category }}</span>
            <h3>{{ doc.title }}</h3>
          </div>
          <button class="btn btn-primary" @click="emit('navigate', doc.menuKey)">立即体验 →</button>
        </div>
        <p class="doc-sub">{{ doc.subtitle }}</p>

        <div class="doc-cols">
          <div class="col-box">
            <strong>核心能力清单</strong>
            <ul>
              <li v-for="(cap, idx) in doc.capabilities" :key="idx">{{ cap }}</li>
            </ul>
          </div>
          <div class="col-box steps-box">
            <strong>快速上手步骤</strong>
            <ol>
              <li v-for="(st, idx) in doc.steps" :key="idx">{{ st }}</li>
            </ol>
          </div>
        </div>
      </article>
    </div>

    <p v-if="!filteredDocs.length" class="empty">没有匹配的功能文档，请更换关键词重试。</p>
  </section>
</template>

<style scoped>
.guide-page { display: flex; flex-direction: column; gap: 16px; }
.guide-hero { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.guide-hero h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; font-size: 13px; color: var(--muted); }
.stat-pills, .cat-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.pill { padding: 4px 10px; border-radius: 999px; font-size: 12px; background: #f1f5f9; color: #334155; font-weight: 600; }
.pill-b { background: #e0f2fe; color: #0369a1; }
.filter-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.search-inp { min-width: 260px; flex: 1; max-width: 380px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: var(--card); }
.doc-grid { display: flex; flex-direction: column; gap: 14px; }
.doc-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; display: flex; flex-direction: column; gap: 10px; }
.doc-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.doc-head h3 { margin: 4px 0 0; font-size: 16px; }
.cat-tag { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 6px; background: #eff6ff; color: #1d4ed8; font-weight: 600; }
.doc-sub { margin: 0; font-size: 13px; color: var(--muted); }
.doc-cols { display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px; }
@media (max-width: 860px) { .doc-cols { grid-template-columns: 1fr; } }
.col-box { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 13px; }
.steps-box { background: #f0f9ff; border-color: #bae6fd; }
.col-box strong { display: block; margin-bottom: 6px; font-size: 12px; color: #0f172a; }
.col-box ul, .col-box ol { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; color: #334155; line-height: 1.5; }
.empty { text-align: center; color: var(--muted); padding: 24px; }
</style>
