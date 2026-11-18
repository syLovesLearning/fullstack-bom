# API_SPEC.md — REST & SSE 接口契约（唯一真相源）

所有接口统一前缀 `/api/v1`。除 `/health` 与 `/auth/dev-login` 外，均需携带 `Authorization: Bearer <jwt>`。

## 1. 鉴权与会话

- `GET /auth/mode` -> `{env, require_passcode}`（dev 免密直入，prod 强制密钥解锁）
- `POST /auth/passcode-login` -> `{passcode}` -> `{access_token, token_type, user}`（简历访客密钥登录，生产可用）
- `POST /auth/dev-login` -> `{username, role}` -> `{access_token, token_type, user}`（**仅 `ENV=dev` 可用**；非 dev 环境返回 403）
- `GET /auth/me` -> `AuthContext`
- `POST /auth/register` -> `{username, password, role, groups}` -> `{access_token, user}`（**role 白名单：`user`/`readonly`/`external_guest`**；传 `admin` 返回 422/403，管理员只能由库内提权）
- `POST /auth/login` -> `{username, password}` -> `{access_token, user}`（校验密码与 `is_active`，停用账号返回 401）
- `POST /sessions` -> `{agent_name, title}` -> `{id, user_id, ...}`
- `GET /sessions` -> `Session[]`
- `GET /sessions/{session_id}/messages` -> `Message[]`

## 2. 流式对话 (SSE)

- `POST /sessions/{session_id}/chat/stream` -> `{message, max_steps?, top_k?, min_score?, enable_rag?}` -> `text/event-stream`
  - `top_k`（默认 3）与 `min_score`（默认 0.2）为**请求级 rag_search 默认参数**：LLM 未显式传参时按此值检索，前端调试面板实时生效
  - `enable_rag=false` 时从本次请求的 `allowed_tools` 中剔除 `rag_search`
- **SSE 事件协议**：
  - `event: thought` -> `{"step": int, "status": "reasoning"}`
  - `event: tool_start` -> `{"tool": str, "args": dict}`
  - `event: citations` -> `{"items": [{index, title, source_path, heading_path, score, snippet}]}`
  - `event: tool_result` -> `{"tool": str, "duration_ms": int, "preview": str}`
  - `event: token` -> `{"text": str}`（按 ~24 字符分块推送）
  - `event: done` -> `{"run_id": uuid, "total_tokens": int, "latency_ms": int}`
  - `event: error` -> `{"message": str}`

## 3. 记忆、知识库、工具与评测

- `GET|POST /memories`, `DELETE /memories/{memory_id}`
- `POST /docs/ingest` -> `{title, source_path, category, content}` -> `{document_id, status, chunks}`
- `GET /docs`, `DELETE /docs/{doc_id}`, `POST /docs/search` -> `{query, category, top_k}`
- `GET /tools`（按 `AuthContext.allowed_tools` 裁剪；registry 构建与 chat 一致，含 workflow/inventory/BOM 工具）, `GET /runs/{run_id}/trace`
- **智能体 BOM 工具**（admin/user 角色默认可用，readonly/external_guest 不可见）：
  - `bom_quote`：按 `{root_keyword, h, w, d, t, margin_rate, tax_rate}` 试算 BOM 成本与报价，SSE 推 `action_cards`（`kind: "bom_quote"`，含 `direct_cost/final_price/cost_summary`）
  - `bom_stock_check`：按 3D 参数核查物料齐套状态，缺料时 SSE 推 `action_cards`（`kind: "inventory_alert"`，`safety_stock` 语义为需求量）
- `GET /eval/cases` -> `EvalCase[]`（读取 `eval/golden_qa.json`）
- `POST /eval/seed` -> 初始化示例文档到 Postgres
- `POST /eval/run` -> `{seed_if_empty, top_k}` -> `{summary: {total, passed, hit_rate_at_3, mrr, avg_latency_ms}, results}`
- `POST /docs/upload` -> `multipart/form-data` (`files[]`, `category`) -> 批量入库（支持 `.md/.txt/.pdf/.zip`；embedding 失败时该文档入库报错，不降级写入）
- `POST /docs/search-debug` -> `{query, category, top_k, min_score}` -> `{tokens, rejected, latency_ms, vec_hits, fts_hits, reranked_hits}`
- `kb_documents.allowed_groups` 与 `users.groups` 通过 PostgreSQL `&&` 数组重叠过滤文档可见性。

## 3.5 配置化企业流程（Workflows）

- `GET /workflows/skills` -> `WorkflowDefinition[]`（按当前角色过滤可发起的流程）
- `POST /workflows/definitions` -> `WorkflowDefinitionUpsert`（仅 admin；动态配置新流程类型）
- `POST /workflows` -> `{flow_code, form_data}` -> `WorkflowInstance`（按定义字段动态校验后入库）
- `GET /workflows?flow_code=&page=&page_size=&scope=mine|all` -> `{items, total, page, page_size}`
  - `scope=mine`（默认）：仅本人发起的台账；`scope=all`：**仅 admin**，全量台账（含 `owner_name`），用于审批视图
- `PATCH /workflows/{instance_id}/status` -> `{status: approved|rejected, channel}` -> `WorkflowInstance`
  - **审批规则**：仅 `admin` 角色可审批；**不得审批自己发起的实例**（403）；已审批实例重复操作返回 409；`approved_by` 记录实际审批人

## 4. 基础 BOM 维护 (独立库 `bom_db`)

- `GET /bom/items` -> `BomItem[]`（按 `AuthContext.user_id` 行级隔离）
- `POST /bom/items` -> `BomItemCreate` -> `BomItem`（支持同 `sku_code` 幂等更新）
- `DELETE /bom/items/{item_id}` -> `{deleted: bool}`（软删除 `is_active = FALSE`）
- `GET /bom/edges/{parent_id}` -> `BomEdge[]`（查询指定成品/半成品下的直属子件）
- `POST /bom/edges/{parent_id}` -> `BomEdgeCreate` -> `BomEdge`（含 DAG 环路检测防死循环）
- `POST /bom/edges/{parent_id}/batch` -> `{rows: BomEdgeCreate[]}` -> `{created_count: int}`（**拖拽多选落地**：一次环检测 + 单事务 executemany，最多 50 行）
- `PATCH /bom/edges/{edge_id}/move` -> `{parent_id}` -> `{edge_id, parent_id, child_id}`（**拖拽换父级**：边连同公式/余料/附加费整体迁移，仅改 `bom_header_id`；含环检测，同父级视为无效操作报 400）
- `DELETE /bom/edges/{edge_id}` -> `{deleted: bool}`
- `POST /bom/seed` -> `{seeded_items: int, seeded_edges: int}`（一键初始化示例机柜多级 BOM）
- `GET /bom/tree/{root_id}` -> `{root: BomTreeNode, cost_summary: dict, bom_summary: dict}`（递归展开多级树并输出成本向/BOM向双视图试算）
- `PATCH /bom/edges/{edge_id}` -> `BomEdgeUpdate` -> `BomEdge`（行内编辑用量、3D公式、人工浮动与归类）
- `POST /bom/clone` -> `{source_parent_id, target_parent_id}` -> `{cloned_count: int}`（一键克隆 BOM 结构，单事务批量写入）
- `POST /bom/formula/check` -> `{expr, env}` -> `{ok: bool, value: float|null, error: str}`（公式试算校验，前端编辑实时反馈）
- `POST /bom/formula/draft` -> `{intent, target: "qty"|"extra", env?, base_qty?, qty?}` -> `{ok, expr, explain, steps[], assumptions[], samples[{env,value,error}], error, tokens}`（**AI 录入第 1 步**：口述逻辑 → 受限 DSL 公式，模型输出经 AST 白名单求值校验，失败自动带上错误重试一轮；未配置 LLM_API_KEY 时 `ok=false` 并给出提示）
- `GET /bom/formula/template?target=qty|extra&expr=` -> `xlsx` 二进制（**第 2 步**：下载测试数据模板，主表含 3 行预置尺寸、`预期结果` 选填，次表写入变量/函数/判定口径说明）
- `POST /bom/formula/parse-sheet`（multipart `file`，.xlsx/.xlsm/.csv，≤2MB）-> `{rows[{index, env{H,W,D,T,base_qty,qty}, expected, note}], warnings[], skipped}`（**第 2 步**：上传填写后的文件，表头按中英别名映射，最多 500 行）
- `POST /bom/formula/batch-check` -> `{expr, rows[]}` -> `{total, passed, failed, errors, no_expect, all_ok, summary{min,max,avg}, rows[{expected, actual, diff, status: pass|fail|no_expect|error}]}`（**第 3 步**：批量核对，`预期结果` 留空只回显不判定；`all_ok` 需同时满足「至少 1 行填了预期值」+「失败=0」+「异常=0」，全行留空不算通过）
- `GET /bom/tree/{root_id}?h=2200&w=800&d=600&t=2.0` -> 支持传入 3D 沙盒参数实时求值 `FORMULA_3D`
- `POST /bom/quotes` -> `{root_id, params_3d, margin_rate, tax_rate, note}` -> `QuoteSnapshot`（冻结当前 BOM 试算结果与余料损耗）
- `GET /bom/quotes` -> `QuoteSnapshot[]`（查看历史报价快照）
- `POST /bom/stock-check` -> `{root_id, h, w, d, t}` -> `StockCheckItem[]`（跨库查询 `rag_db.inventory_items` 核对材料齐套状态）

## 5. 数据库动态菜单配置 (`rag_db.sys_menus`)

- `GET /menus` -> `SysMenuItem[]`（按当前 `AuthContext.role` 与 `is_enabled = TRUE` 过滤并按 `sort_order` 排序）
- `GET /menus/all` -> `SysMenuItem[]`（管理员查看全部菜单配置项）
- `PUT /menus/{menu_key}` -> `SysMenuUpdate` -> `SysMenuItem`（动态修改菜单标题、分组、排序、角色白名单与启停状态）

- `GET /bom/items/{item_id}/where-used` -> `WhereUsedItem[]`（物料反查：列出所有引用该物料的父级 BOM）
- `POST /bom/items/replace` -> `{old_item_id, new_item_id}` -> `{replaced_count: int}`（跨 BOM 批量替料，含环路校验）
- `POST /bom/items/batch-price` -> `{category, pct_delta}` -> `{updated_count: int}`（按大类批量调价百分比）
