# 全局 Code Review 报告

> **评审日期**：2026-11-18
> **评审范围**：全仓（backend/src 全部、frontend/src 核心链路、backend/tests、docs 契约）
> **代码基线**：commit `5891ff8`（feat(bom-ui): 报价参数化 + 快照对比 + BOM API 模块拆分）+ 工作区未提交的 BOM 拖拽改动
> **性质**：本文档为修复任务清单，每项含「问题 / 位置 / 影响 / 修复要求 / 验收标准」，可直接按序派工。

---

## 〇、总体评价

架构分层纪律良好，符合 CLAUDE.md 铁律：无 ORM、无 LangChain、SQL 全部携带 `user_id` 隔离、公式求值走 AST 白名单、ZIP 解包有防穿越保护、PBKDF2 + 常数时间比较正确。`EventContext`（ContextVar + asyncio.Queue）穿透 SSE 的设计干净。

**主要风险集中在三处**：前端 Markdown XSS、鉴权接口可自助提权、若干"静默失效"参数。以下按严重程度分级，P0 建议当日修复。

---

## 一、P0 — 安全问题（当日必修）

### P0-1 Markdown 渲染存在存储型 XSS

- **位置**：
  - `frontend/src/utils/markdown.ts`（marked 渲染无净化）
  - `frontend/src/components/ChatWorkspace.vue:205`、`frontend/src/components/FloatingCopilot.vue:107,125`（`v-html` 直注）
- **问题**：marked v5+ 已移除 sanitize 能力，`renderMarkdown()` 的输出经 `v-html` 直接注入 DOM。LLM 输出、RAG 召回片段、知识库文档、用户消息中的 `<script>`、`<img onerror=...>`、`javascript:` 链接均会被原样执行。
- **影响升级路径**：知识库文档按 `allowed_groups` 分组共享（`doc_repo.py`），**一条恶意文档即可打到全部同组用户**，是最现实的攻击面。
- **修复要求**：
  1. `npm i dompurify`（及 `@types/dompurify`）；
  2. `renderMarkdown()` 内部对 `marked.parse()` 结果执行 `DOMPurify.sanitize()` 后再返回；
  3. 允许 `class` 属性以保留 hljs 高亮样式。
- **验收标准**：在对话中发送含 `<img src=x onerror=alert(1)>` 与 `<script>alert(1)</script>` 的消息，页面不弹窗、元素被清除为无害文本；hljs 代码块高亮仍正常。

### P0-2 匿名用户可自助注册 admin 角色

- **位置**：
  - `backend/src/schemas/models.py:53`（`RegisterRequest.role` 的 Literal 含 `"admin"`）
  - `backend/src/api/auth.py:40-50`（`/register` 未做角色校验）
  - `frontend/src/App.vue:161`（注册弹窗提供 admin 选项）
- **问题**：任何未认证调用方可直接 `POST /api/v1/auth/register` 注册 `role=admin`，获取管理员全部工具与分组权限。
- **修复要求**：
  1. `RegisterRequest.role` 的 Literal 收敛为 `["user", "readonly", "external_guest"]`；
  2. `/register` 路由对传入 role 做服务端二次校验，含 `admin` 一律 403；
  3. 前端注册下拉同步移除 admin 选项。
- **验收标准**：`POST /register {"role":"admin",...}` 返回 403/422；注册为 user/readonly 正常。

### P0-3 停用用户仍可登录（`is_active` 未校验）

- **位置**：`backend/src/repositories/user_repo.py:86-94`（`verify_login`）
- **问题**：查询取出了 `is_active` 字段但从未检查，被软停用账号密码登录照常通过并签发 token。
- **修复要求**：`verify_login` 增加对 `is_active` 的判断，停用用户返回 None（对前端表现为 401）。
- **验收标准**：手工将某用户 `is_active` 置 FALSE 后，该账号登录返回 401。

---

## 二、P1 — 功能失效 bug（本周内修复）

### P1-1 dev-login 无环境门禁 + JWT secret 无启动检查

- **位置**：
  - `backend/src/api/auth.py:29-37`（`/dev-login` 无需密码，且 `get_or_create_dev_user` 每次调用覆盖目标用户名的 role/allowed_tools/groups）
  - `backend/src/config.py:11`（`jwt_secret` 默认 `dev-secret-change-in-production`，无启动校验）
- **问题**：一旦部署到非本机环境，任何人不带凭证即可换取任意角色 token，等于无鉴权；默认 secret 若上线可被伪造任意用户 token。
- **修复要求**：
  1. `Settings` 增加 `env: str = "dev"` 字段（`.env` 可覆盖）；
  2. `/dev-login` 在 `settings.env != "dev"` 时返回 404 或 403；
  3. 应用启动（lifespan 入口）校验：`env` 为生产值且 `jwt_secret` 仍为默认值时直接抛异常拒绝启动。
- **验收标准**：`ENV=prod` 启动后 `/dev-login` 不可用；默认 secret 下生产启动被拦截并给出明确报错。

### P1-2 Chat 调试参数 `top_k` / `min_score` 静默失效

- **位置**：
  - `backend/src/api/chat.py`（`chat_stream` 从未读取 `body.top_k` / `body.min_score`）
  - `backend/src/services/tool_setup.py:18-20`（`RagSearchArgs` 固定默认值）
  - `frontend/src/components/ChatWorkspace.vue:276-277`（UI 可调，实际无效果）
- **问题**：前端调试面板调整 RAG 召回数量与最低分数后随请求发送，但后端完全忽略；`rag_search` 工具始终使用 schema 默认值。参数静默失效对调试 RAG 拒答阈值是误导性的。
- **修复要求**：将 `body.top_k`、`body.min_score` 通过 `build_tool_registry(...)` 透传为 `rag_search` 工具的默认值（如给 `register_rag_tool` 增加默认参数注入），LLM 未显式传参时使用请求级默认。
- **验收标准**：UI 将 `min_score` 调到 0.9 后对话，`rag_search` 命中结果明显收敛/触发拒答；`top_k=1` 时 citations 只有一条。

### P1-3 工作流审批人逻辑颠倒（只能本人审批自己）

- **位置**：`backend/src/repositories/workflow_repo.py:130-140`（`update_status_idempotent` 的 WHERE 含 `user_id = %s`，即提交人）
- **问题**：approve/reject 操作被限定为**流程发起人本人**，审批语义完全颠倒；他人（含 admin）无法审批，本人可以自审自批。
- **修复要求**：
  1. 审批操作与 owner 解耦：admin 角色可审批任意实例；非 admin 只能审批自己所在分组/角色有权的流程（当前可先简化为「仅 admin 可审批，且不得审批自己发起的实例」）；
  2. `approved_by` 记录实际审批人；
  3. 同步更新 `docs/API_SPEC.md`（契约先行铁律）与前端 `WorkflowCenter.vue` 的操作按钮可见性（owner 看不到审批按钮）。
- **验收标准**：user A 发起流程，A 自己无法审批（409/403）；admin B 审批成功且 `approved_by` 为 B；重复审批返回 409 幂等提示。

### P1-4 Embedding 调用失败静默降级，会污染向量空间

- **位置**：`backend/src/services/embedding_service.py:29-39`（`embed_texts` 的 `except Exception` 分支）
- **问题**：线上 embedding API 失败时静默 fallback 到本地 hash 向量。若部分文档以真实向量入库、部分以 hash 向量入库，两者不在同一向量空间，**向量检索结果退化为噪声且无任何日志**。
- **修复要求**：
  1. `embed_texts` / `rerank` 的异常分支至少 `logger.exception` 记录；
  2. 入库路径（`ingest_document` → `embed_texts`）失败应抛出错误终止入库，不允许混合向量空间写库；查询路径可保留降级但必须带 warning 事件（`emit_event`）。
- **验收标准**：断网/错 key 时入库接口返回明确失败；日志可见异常栈；查询路径降级时前端 trace 中可见 warning。

---

## 三、P2 — 设计与正确性隐患（排期修复）

### P2-1 BOM 环检测与写入非原子（TOCTOU）

- **位置**：`backend/src/services/bom_service.py:45-48`（add_edge）、`:50-55`（add_edges_batch）、`:63-74`（move_edge）
- **问题**：`_assert_acyclic` 读全量边后释放连接，随后才写库。并发的挂载/移动可绕过环检测制造环路。
- **修复要求**：将「拉全量边 + 环检测 + get_or_create_header + 写入」包进单事务（psycopg `conn.transaction()`），或至少在写入 SQL 上加防御（如 header 维度的触发器/约束）。当前 demo 规模可接受，但需在代码注释中标注已知竞态。

### P2-2 `get_or_create_header` 冲突目标与复活语义脆弱

- **位置**：`backend/src/repositories/bom_repo.py:83-94`
- **问题**：`ON CONFLICT (item_id, version)` 不含 `user_id`；`DO UPDATE SET status='ACTIVE'` 会无条件复活任意已存在 header。当前 item 是用户级 UUID 故实际安全，但语义依赖隐式前提。
- **修复要求**：加注释说明 item_id 用户级唯一的前提；或将冲突目标改为 `(item_id, version)` 且 UPDATE 增加 `WHERE bom_headers.user_id = EXCLUDED.user_id`。

### P2-3 "流式"回答为伪流式，逐字符事件开销大

- **位置**：`backend/src/core/agent_loop.py:46-51`
- **问题**：final answer 在 LLM 完整返回后逐字符 `emit_event("token")`，长回答产生数千次 `queue.put`/SSE 帧；且用户需等待完整生成后才开始看到输出。
- **修复要求**：短期改为按句/按块（如 20~40 字符）切片发送；中期可评估 LLM 侧 `stream=True` 透传真实 token 流。

### P2-4 会话历史缓存与 DB 返回条数不一致

- **位置**：`backend/src/services/memory_service.py:54-66`
- **问题**：DB 路径取 12 条，缓存只序列化最近 8 条（`history[-8:]`），命中缓存时上下文变 8 条，未命中时 12 条，随缓存状态漂移。
- **修复要求**：缓存与返回使用同一窗口（统一 8 或 12），并在注释说明窗口大小依据。

### P2-5 RAG 缓存键未包含 `min_score`，低分命中永久丢失

- **位置**：`backend/src/services/rag_service.py:108-115, 155-156`
- **问题**：缓存键仅含 user/groups/category/query，首次以 `min_score=0.2` 过滤后的结果被缓存；后续传 `min_score=0.0` 的调用命中缓存后只能拿到已过滤集合。
- **修复要求**：缓存键加入 `min_score`；或缓存未过滤的 top_n 结果、读取后按请求阈值过滤（后者更省缓存空间）。

### P2-6 `safe_eval_formula` 吞异常，公式错误静默按 0 计价

- **位置**：`backend/src/services/bom_formula.py:24-31`；调用方 `bom_costing.py:38, 55`
- **问题**：BOM 成本试算中公式写错（语法错、引用了不存在的变量）会静默按 fallback（0.0）计价。报价场景"算错成 0"比报错危险得多。
- **修复要求**：试算主路径（costing）对「非空公式求值失败」至少记录日志并在树节点输出 `formula_error` 字段；前端已有 `/formula/check` 实时校验兜底，可保持不变。

### P2-7 半成品（装配体）边上的附加费/余料策略被忽略

- **位置**：`backend/src/services/bom_costing.py:30-61`（`_walk` 中仅叶子节点应用 `extra_cost_expr` / 余料策略）
- **问题**：挂在半成品边上的 `extra_cost_expr`、`remnant_policy` 等配置静默丢失。
- **修复要求**：若为刻意设计，在 `BomEdgeCreate` 的 schema 描述与前端规则弹窗中明确"仅对成本叶子生效"；若非刻意，补齐装配体节点的附加费与余料核算。

### P2-8 `RegisteredTool.requires_approval` 为假能力

- **位置**：`backend/src/core/tool_registry.py:17`（字段定义）；`backend/src/core/agent_loop.py:56-77`（执行路径未检查）
- **问题**：字段注册了但 AgentLoop 从不消费，形同虚设。
- **修复要求**：二选一：在 AgentLoop 执行前检查并 emit `approval_required` 事件（配合前端确认流），或删除该字段避免误导。

### P2-9 `/api/v1/tools` 工具发现列表与实际可用工具不一致

- **位置**：`backend/src/api/tools.py:32`
- **问题**：构建 registry 时未传 `workflow_repo` / `inventory_repo`，workflow/inventory 类工具永远不会出现在工具列表，与 chat 实际可用工具不符。
- **修复要求**：`list_available_tools` 注入 `get_workflow_repo` / `get_inventory_repo` 依赖，与 `chat_stream` 的 registry 构建保持一致。

---

## 四、P3 — 打磨项（顺手修复）

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| P3-1 | `backend/src/config.py:8-9` | DSN 默认值硬编码 `shenyang` 用户名 | 默认留空，连接失败时给出明确报错 |
| P3-2 | `backend/src/repositories/menu_repo.py:54,67` | `ensure_initialized` 每次菜单请求都跑 DDL+COUNT | 挪到 lifespan 一次性执行（参照 `bom_repo.ensure_v3_schema` 的 `_migrated` 标志） |
| P3-3 | `frontend/src/components/BomTreeEditor.vue:66-73` | `exportCsv` 无 CSV 转义，名称含逗号/引号错列 | 对每个字段做 `"..."` 包裹与引号转义 |
| P3-4 | `backend/src/repositories/session_repo.py:87-95` | `append_message` 两条语句未包事务 | 包 `conn.transaction()` |
| P3-5 | `backend/src/core/event_context.py:13` | `ContextVar(default=[])` 可变默认值 | 改为 `default=None` + get 时兜底 `[]` |
| P3-6 | `backend/src/services/bom_costing.py:91-93` | 库存模糊兜底 `name[:4]` 可能匹配错误物料 | 命中兜底行时在结果标注 `matched_by="fuzzy"`，前端可见 |
| P3-7 | `frontend/src/App.vue:90` | 挂载即自动 `devLogin("shenyang","admin")` | 随 P1-1 环境门禁收口：非 dev 环境进入登录页 |
| P3-8 | `backend/src/services/bm25.py`（`bm25_rank`） | 生产检索走 Postgres tsvector，Python BM25 仅测试在用 | 在模块 docstring 标注"仅用于测试/对照"，避免误用 |
| P3-9 | `backend/src/api/chat.py` | `ChatRequest` 修复 P1-2 后确认无其他未消费字段 | 修 P1-2 时顺带核对 |

---

## 五、做得好的部分（保持）

- `bom_service._assert_acyclic`：多源 DFS 环检测，注释清晰；`test_bom_drag.py` 对"单事务 / 零写入 / 只改挂载点"三条契约的验证到位
- `bom_repo.get_or_create_header` 用 INSERT ON CONFLICT 消除并发建 header 竞态（bom_repo.py:84 注释明确动机）
- `chunker.py` 代码块保护、标题面包屑保留
- `/bom/formula/check` 前端实时公式校验闭环
- workflow 审批幂等（`status='submitted'` 条件更新）
- `file_parser.py` ZIP 安全解包：路径穿越过滤、大小/数量上限、`__MACOSX` 清理，且有专项测试
- `user_repo` PBKDF2(100k) + `hmac.compare_digest`
- 测试全部离线化（FakeRepo），不依赖真实 DB 即可验证关键链路

---

## 六、修复顺序与派工建议

| 批次 | 内容 | 预估工作量 |
|------|------|-----------|
| **第 1 批（当日）** | P0-1 DOMPurify、P0-2 注册去 admin、P0-3 is_active | 0.5 天 |
| **第 2 批（本周）** | P1-1 dev-login 门禁、P1-2 chat 参数接通、P1-3 审批人逻辑、P1-4 embedding 日志 | 1~1.5 天 |
| **第 3 批（排期）** | P2-1 ~ P2-9 | 2~3 天 |
| **第 4 批（顺手）** | P3-1 ~ P3-9 | 0.5 天 |

**全局要求（对修复人）**：

1. 遵守 `CLAUDE.md` 铁律：涉及 REST/SSE 契约变更（P1-2、P1-3、P2-7、P2-8）**先改 `docs/API_SPEC.md` 再动代码**；
2. 每项修复附对应测试（沿用现有 FakeRepo 离线风格）；
3. 完成后执行 `python3 scripts/gen_code_index.py` 刷新代码地图；
4. 提交信息按现有惯例（`fix(scope): 描述`），每批一个 commit。
