<script setup lang="ts">
import { ref } from 'vue'
import { debugRagPipeline, type DebugSearchResponse } from '../api/client'

const props = defineProps<{ token: string }>()

const query = ref('pgvector 向量检索与 GIN 索引如何配合？')
const category = ref('')
const minScore = ref(0.2)
const loading = ref(false)
const result = ref<DebugSearchResponse | null>(null)
const errMsg = ref('')

async function runDebug() {
  if (!query.value.trim()) return
  loading.value = true
  errMsg.value = ''
  try {
    result.value = await debugRagPipeline(props.token, query.value.trim(), category.value, minScore.value)
  } catch (err) {
    errMsg.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function highlightParts(text: string, tokens: string[]): { text: string; hit: boolean }[] {
  const kws = tokens.filter((t) => t.length >= 2).slice(0, 10)
  if (!kws.length) return [{ text, hit: false }]
  const escaped = kws.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const re = new RegExp(`(${escaped.join('|')})`, 'gi')
  return text.split(re).map((part) => ({
    text: part,
    hit: kws.some((k) => k.toLowerCase() === part.toLowerCase()),
  }))
}
</script>

<template>
  <section class="lab-panel">
    <header class="panel-head">
      <div>
        <h2>检索命中透视台 (四段流水线可视化)</h2>
        <p class="sub">输入任意问题，透明查看分词、pgvector 向量召回、Postgres GIN 全文召回与 Rerank 阈值拦截情况。</p>
      </div>
    </header>

    <div class="controls-card">
      <div class="row">
        <input
          v-model="query"
          class="q-input"
          placeholder="输入测试问题..."
          @keyup.enter="runDebug"
        />
        <input v-model="category" class="cat-input" placeholder="分类过滤（可空）" />
        <button class="btn btn-primary" :disabled="loading" @click="runDebug">
          {{ loading ? '检索中...' : '运行透视检索' }}
        </button>
      </div>
      <div class="slider-row">
        <label>Rerank 拒答阈值 (min_score)：<strong>{{ minScore.toFixed(2) }}</strong></label>
        <input v-model.number="minScore" type="range" min="0" max="0.95" step="0.05" />
      </div>
    </div>

    <p v-if="errMsg" class="err-tip">{{ errMsg }}</p>

    <template v-if="result">
      <div class="summary-bar">
        <span :class="['badge', result.rejected ? 'badge-err' : 'badge-ok']">
          {{ result.rejected ? '触发低分拒答 (无达标依据)' : '命中达标' }}
        </span>
        <span class="meta">耗时：{{ result.latency_ms }} ms</span>
        <span class="meta">分词：</span>
        <span v-for="t in result.tokens" :key="t" class="tok">{{ t }}</span>
      </div>

      <div class="cols-3">
        <div class="stage-card">
          <h3>1. pgvector 向量召回 ({{ result.vec_hits.length }})</h3>
          <div v-for="(h, i) in result.vec_hits" :key="h.id" class="hit-item">
            <div class="hit-top">
              <span class="badge badge-blue">#{{ i + 1 }}</span>
              <strong>{{ h.title }}</strong>
              <span class="score">{{ h.score }}</span>
            </div>
            <div class="hpath">{{ h.heading_path }}</div>
            <p class="prev">{{ h.preview }}</p>
          </div>
          <p v-if="!result.vec_hits.length" class="empty">无向量命中</p>
        </div>

        <div class="stage-card">
          <h3>2. Postgres GIN 全文召回 ({{ result.fts_hits.length }})</h3>
          <div v-for="(h, i) in result.fts_hits" :key="h.id" class="hit-item">
            <div class="hit-top">
              <span class="badge badge-blue">#{{ i + 1 }}</span>
              <strong>{{ h.title }}</strong>
              <span class="score">{{ h.score }}</span>
            </div>
            <div class="hpath">{{ h.heading_path }}</div>
            <p class="prev">{{ h.preview }}</p>
          </div>
          <p v-if="!result.fts_hits.length" class="empty">无全文关键词命中</p>
        </div>

        <div class="stage-card">
          <h3>3. RRF + Rerank 最终精排 ({{ result.reranked_hits.length }})</h3>
          <div
            v-for="h in result.reranked_hits"
            :key="h.id"
            class="hit-item"
            :class="{ dimmed: !h.passed }"
          >
            <div class="hit-top">
              <span :class="['badge', h.passed ? 'badge-ok' : 'badge-err']">
                #{{ h.rank }} {{ h.passed ? '达标' : '已拦截' }}
              </span>
              <strong>{{ h.title }}</strong>
              <span class="score">{{ h.score }}</span>
            </div>
            <div class="hpath">{{ h.source_path }} · {{ h.heading_path }}</div>
            <p class="prev">
              <template v-for="(p, idx) in highlightParts(h.snippet, result.tokens)" :key="idx">
                <mark v-if="p.hit">{{ p.text }}</mark>
                <span v-else>{{ p.text }}</span>
              </template>
            </p>
          </div>
          <p v-if="!result.reranked_hits.length" class="empty">无融合结果</p>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.lab-panel { display: flex; flex-direction: column; gap: 16px; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.controls-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
.q-input { flex: 1; min-width: 240px; padding: 9px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }
.cat-input { width: 150px; padding: 9px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
.slider-row { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--muted); }
.summary-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 13px; }
.meta { color: var(--muted); }
.tok { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-family: monospace; }
.cols-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
@media (max-width: 960px) { .cols-3 { grid-template-columns: 1fr; } }
.stage-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.stage-card h3 { margin: 0; font-size: 14px; color: var(--muted); border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.hit-item { border: 1px solid var(--border); border-radius: 8px; padding: 10px; font-size: 12px; }
.hit-item.dimmed { opacity: 0.55; background: #f9fafb; }
.hit-top { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.score { margin-left: auto; font-family: monospace; color: var(--primary); font-weight: 600; }
.hpath { color: var(--muted); font-size: 11px; margin-bottom: 4px; }
.prev { margin: 0; color: #374151; line-height: 1.5; white-space: pre-wrap; }
mark { background: #fef08a; padding: 0 2px; border-radius: 2px; }
.empty { color: var(--muted); font-size: 13px; margin: 0; }
.err-tip { margin: 0; color: var(--err); font-size: 13px; }
</style>
