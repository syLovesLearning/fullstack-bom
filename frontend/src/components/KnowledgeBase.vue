<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { deleteDoc, listDocs, uploadDocs, type BatchUploadResponse, type DocItem } from '../api/client'

const props = defineProps<{ token: string }>()

const docs = ref<DocItem[]>([])
const category = ref('general')
const allowedGroups = ref('public')
const selectedFiles = ref<File[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const batchResult = ref<BatchUploadResponse | null>(null)
const errMsg = ref('')

async function refresh() {
  docs.value = await listDocs(props.token)
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  selectedFiles.value = Array.from(target.files ?? [])
}

async function handleUpload() {
  if (!selectedFiles.value.length) return
  uploading.value = true
  batchResult.value = null
  errMsg.value = ''
  try {
    batchResult.value = await uploadDocs(
      props.token,
      selectedFiles.value,
      category.value.trim() || 'general',
      allowedGroups.value.trim() || 'private',
    )
    selectedFiles.value = []
    if (fileInput.value) fileInput.value.value = ''
    await refresh()
  } catch (err) {
    errMsg.value = err instanceof Error ? err.message : String(err)
  } finally {
    uploading.value = false
  }
}

async function handleDelete(docId: string) {
  await deleteDoc(props.token, docId)
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <section class="kb-panel">
    <header class="panel-head">
      <div>
        <h2>知识库文档管理 (支持多选、ZIP 与分组数据权限)</h2>
        <p class="sub">可见分组可填 private（仅自己）、public（全员）或 engineering / finance（逗号分隔）。</p>
      </div>
      <div class="upload-bar">
        <input ref="fileInput" type="file" multiple accept=".md,.txt,.pdf,.zip" @change="onFileChange" />
        <input v-model="category" class="cat-input" placeholder="分类如 arch" />
        <input v-model="allowedGroups" class="cat-input" placeholder="可见分组如 public,engineering" />
        <button class="btn btn-primary" :disabled="!selectedFiles.length || uploading" @click="handleUpload">
          {{ uploading ? '批量入库中...' : `上传并入库${selectedFiles.length ? ` (${selectedFiles.length})` : ''}` }}
        </button>
      </div>
    </header>

    <div v-if="batchResult" class="batch-box">
      <strong>批量入库结果：</strong>
      共 {{ batchResult.total }} 个 ·
      <span class="badge badge-ok">成功 {{ batchResult.indexed }}</span>
      <span class="badge badge-muted">跳过 {{ batchResult.skipped }}</span>
      <span v-if="batchResult.failed" class="badge badge-err">失败 {{ batchResult.failed }}</span>
    </div>
    <p v-if="errMsg" class="err-tip">{{ errMsg }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>标题</th>
            <th>来源路径</th>
            <th>分类</th>
            <th>可见分组</th>
            <th>切片数</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in docs" :key="d.id">
            <td><strong>{{ d.title }}</strong></td>
            <td><code>{{ d.source_path }}</code></td>
            <td><span class="badge badge-blue">{{ d.category }}</span></td>
            <td>
              <span v-for="g in d.allowed_groups" :key="g" class="badge badge-muted grp">{{ g }}</span>
            </td>
            <td>{{ d.chunk_count }}</td>
            <td><button class="btn" @click="handleDelete(d.id)">删除</button></td>
          </tr>
          <tr v-if="!docs.length">
            <td colspan="6" class="empty">当前账号所属分组下暂无可见文档。</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.kb-panel { display: flex; flex-direction: column; gap: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.panel-head h2 { margin: 0 0 4px; font-size: 18px; }
.sub { margin: 0; color: var(--muted); font-size: 13px; }
.upload-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.cat-input { width: 150px; padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
.batch-box { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 13px; }
.err-tip { margin: 0; color: var(--err); font-size: 13px; }
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 11px 12px; border-bottom: 1px solid var(--border); }
th { background: #f9fafb; color: var(--muted); font-weight: 600; }
.grp { margin-right: 4px; }
.empty { text-align: center; color: var(--muted); padding: 24px; }
</style>
