# API_SPEC.md — REST & SSE 接口契约（唯一真相源）

所有接口统一前缀 `/api/v1`。除 `/health` 与 `/auth/dev-login` 外，均需携带 `Authorization: Bearer <jwt>`。

## 1. 鉴权与会话

- `POST /auth/dev-login` -> `{username, role}` -> `{access_token, token_type, user}`
- `GET /auth/me` -> `AuthContext`
- `POST /sessions` -> `{agent_name, title}` -> `{id, user_id, ...}`
- `GET /sessions` -> `Session[]`
- `GET /sessions/{session_id}/messages` -> `Message[]`

## 2. 流式对话 (SSE)

- `POST /sessions/{session_id}/chat/stream` -> `{message}` -> `text/event-stream`
- **SSE 事件协议**：
  - `event: thought` -> `{"step": int, "status": "reasoning"}`
  - `event: tool_start` -> `{"tool": str, "args": dict}`
  - `event: citations` -> `{"items": [{index, title, source_path, heading_path, score, snippet}]}`
  - `event: tool_result` -> `{"tool": str, "duration_ms": int, "preview": str}`
  - `event: token` -> `{"text": str}`
  - `event: done` -> `{"run_id": uuid, "total_tokens": int, "latency_ms": int}`
  - `event: error` -> `{"message": str}`

## 3. 记忆、知识库、工具与评测

- `GET|POST /memories`, `DELETE /memories/{memory_id}`
- `POST /docs/ingest` -> `{title, source_path, category, content}` -> `{document_id, status, chunks}`
- `GET /docs`, `DELETE /docs/{doc_id}`, `POST /docs/search` -> `{query, category, top_k}`
- `GET /tools`（按 `AuthContext.allowed_tools` 裁剪）, `GET /runs/{run_id}/trace`
- **智能体 BOM 工具**（admin/user 角色默认可用，readonly/external_guest 不可见）：
  - `bom_quote`：按 `{root_keyword, h, w, d, t, margin_rate, tax_rate}` 试算 BOM 成本与报价，SSE 推 `action_cards`（`kind: "bom_quote"`，含 `direct_cost/final_price/cost_summary`）
  - `bom_stock_check`：按 3D 参数核查物料齐套状态，缺料时 SSE 推 `action_cards`（`kind: "inventory_alert"`，`safety_stock` 语义为需求量）
- `GET /eval/cases` -> `EvalCase[]`（读取 `eval/golden_qa.json`）
- `POST /eval/seed` -> 初始化示例文档到 Postgres
- `POST /eval/run` -> `{seed_if_empty, top_k}` -> `{summary: {total, passed, hit_rate_at_3, mrr, avg_latency_ms}, results}`
- `POST /docs/upload` -> `multipart/form-data` (`files[]`, `category`) -> 批量入库（支持 `.md/.txt/.pdf/.zip`）
- `POST /docs/search-debug` -> `{query, category, top_k, min_score}` -> `{tokens, rejected, latency_ms, vec_hits, fts_hits, reranked_hits}`
- `POST /auth/register` -> `{username, password, role, groups}` -> `{access_token, user}`
- `POST /auth/login` -> `{username, password}` -> `{access_token, user}`
- `kb_documents.allowed_groups` 与 `users.groups` 通过 PostgreSQL `&&` 数组重叠过滤文档可见性。

## 4. 基础 BOM 维护 (独立库 `bom_db`)

- `GET /bom/items` -> `BomItem[]`（按 `AuthContext.user_id` 行级隔离）
- `POST /bom/items` -> `BomItemCreate` -> `BomItem`（支持同 `sku_code` 幂等更新）
- `DELETE /bom/items/{item_id}` -> `{deleted: bool}`（软删除 `is_active = FALSE`）
- `GET /bom/edges/{parent_id}` -> `BomEdge[]`（查询指定成品/半成品下的直属子件）
- `POST /bom/edges/{parent_id}` -> `BomEdgeCreate` -> `BomEdge`（含 DAG 环路检测防死循环）
- `DELETE /bom/edges/{edge_id}` -> `{deleted: bool}`
- `POST /bom/seed` -> `{seeded_items: int, seeded_edges: int}`（一键初始化示例机柜多级 BOM）
- `GET /bom/tree/{root_id}` -> `{root: BomTreeNode, cost_summary: dict, bom_summary: dict}`（递归展开多级树并输出成本向/BOM向双视图试算）
- `PATCH /bom/edges/{edge_id}` -> `BomEdgeUpdate` -> `BomEdge`（行内编辑用量、3D公式、人工浮动与归类）
- `POST /bom/clone` -> `{source_parent_id, target_parent_id}` -> `{cloned_count: int}`（一键克隆 BOM 结构，单事务批量写入）
- `POST /bom/formula/check` -> `{expr, env}` -> `{ok: bool, value: float|null, error: str}`（公式试算校验，前端编辑实时反馈）
- `GET /bom/tree/{root_id}?h=2200&w=800&d=600&t=2.0` -> 支持传入 3D 沙盒参数实时求值 `FORMULA_3D`

## 5. 数据库动态菜单配置 (`rag_db.sys_menus`)

- `GET /menus` -> `SysMenuItem[]`（按当前 `AuthContext.role` 与 `is_enabled = TRUE` 过滤并按 `sort_order` 排序）
- `GET /menus/all` -> `SysMenuItem[]`（管理员查看全部菜单配置项）
- `PUT /menus/{menu_key}` -> `SysMenuUpdate` -> `SysMenuItem`（动态修改菜单标题、分组、排序、角色白名单与启停状态）

- `POST /bom/quotes` -> `{root_id, params_3d, margin_rate, tax_rate, note}` -> `QuoteSnapshot`（冻结当前 BOM 试算结果与余料损耗）
- `GET /bom/quotes` -> `QuoteSnapshot[]`（查看历史报价快照）
- `POST /bom/stock-check` -> `{root_id, h, w, d, t}` -> `StockCheckItem[]`（跨库查询 `rag_db.inventory_items` 核对材料齐套状态）
