# frontend/CLAUDE.md — 前端记忆规范 (Vue 3 + TypeScript)

> 先读顶层 `../CLAUDE.md` 与 `../docs/API_SPEC.md`。

## 1. 模块职责边界

- `src/api/client.ts`：所有 REST 请求唯一收口（`fetch` + Bearer JWT）。
- `src/composables/useAgentStream.ts`：唯一 SSE 流式消费器（`fetch + ReadableStream`）。
- `src/components/*.vue`：纯 UI 展示与局部视图状态。
- `src/App.vue`：鉴权初始化（`devLogin` + `createSession`）与顶层 Tab 切换。

## 2. 前端开发铁律

1. **禁止组件裸写请求**：`.vue` 文件严禁直接调用 `fetch()`，必须从 `src/api/client.ts` 或 `src/composables/` 引入。
2. **严格 TypeScript**：统一使用 `<script setup lang="ts">`，接口类型必须与 `docs/API_SPEC.md` 保持一致。
3. **代理路径约定**：所有请求使用相对路径 `/api/v1/...`（由 `vite.config.ts` 代理至 `http://127.0.0.1:8000`）。
4. **测试集可视化**：`EvalDashboard.vue` 必须保持 `eval/golden_qa.json` 测试用例在页面中可直接查看与一键运行。
5. **透视台组件**：`RetrievalLab.vue` 展示分词、向量召回、GIN 全文召回与 Rerank 阈值拦截的四段流水线。
6. **共享记忆状态**：`composables/useMemories.ts` 同步维护 `MemoryManager.vue` 与 `ChatWorkspace.vue` 的长期记忆列表。
