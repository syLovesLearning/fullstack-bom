# CODE_INDEX.md — Auto-Generated Structural Map (Agent-Readable)

> Do NOT edit manually. Run `python3 scripts/gen_code_index.py` after file/symbol changes.

## Backend (`backend/src/`)

| File | Exports | Internal Deps | Summary |
| :--- | :--- | :--- | :--- |
| `backend/src/api/auth.py` | dev_login, register, login, get_me | src.api.deps, src.config, src.repositories.user_repo, src.schemas.models | 鉴权接口：支持开发一键切换账号、正式注册与密码登录。 |
| `backend/src/api/bom.py` | list_bom_items, upsert_bom_item, delete_bom_item, list_bom_edges, create_bom_edge, create_bom_edges_batch, update_bom_edge, move_bom_edge, delete_bom_edge, clone_bom_edges, seed_bom_data, get_bom_rollup_tree, save_bom_quote, list_bom_quotes, check_bom_stock | src.api.deps, src.schemas.models, src.services.bom_service | BOM 维护、余料试算、报价快照与跨库库存齐套 REST 接口。 |
| `backend/src/api/bom_formula.py` | check_formula, draft_formula_expr, download_template, parse_uploaded_sheet, batch_check_formula | src.api.deps, src.schemas.bom_formula, src.schemas.models, src.services.bom_formula, src.services.bom_formula_ai, src.services.bom_formula_sheet, src.services.llm_service | 公式 AI 录入接口：口述编译、模板下载、测试数据解析、批量校验。 |
| `backend/src/api/chat.py` | chat_stream | src.api.deps, src.config, src.core.agent_loop, src.core.event_context, src.core.hooks, src.repositories.inventory_repo, src.repositories.session_repo, src.repositories.trace_repo, src.repositories.workflow_repo, src.schemas.models, src.services.bom_service, src.services.llm_service, src.services.memory_service, src.services.rag_service, src.services.tool_setup, src.services.workflow_skills | 核心流式对话接口（SSE）：支持调试参数、引用持久化与全链路 Trace 记录。 |
| `backend/src/api/deps.py` | create_access_token, get_user_repo, get_session_repo, get_memory_repo, get_trace_repo, get_doc_repo, get_workflow_repo, get_inventory_repo, get_memory_service, get_llm_service, get_rag_service, get_current_auth, get_bom_repo, get_bom_service, get_menu_repo, get_menu_service | src.config, src.core.event_context, src.repositories.bom_repo, src.repositories.doc_repo, src.repositories.inventory_repo, src.repositories.memory_repo, src.repositories.menu_repo, src.repositories.session_repo, src.repositories.trace_repo, src.repositories.user_repo, src.repositories.workflow_repo, src.schemas.models, src.services.bom_service, src.services.embedding_service, src.services.llm_service, src.services.memory_service, src.services.menu_service, src.services.rag_service | FastAPI 依赖注入装配与 JWT 鉴权（解析 AuthContext 并写入 ContextVar）。 |
| `backend/src/api/docs.py` | DocIngestRequest, DocSearchRequest, DocDebugSearchRequest, ingest_document, upload_documents, list_documents, delete_document, debug_rag_search, debug_rag_pipeline | src.api.deps, src.repositories.doc_repo, src.schemas.models, src.services.file_parser, src.services.rag_service | 知识库文档管理、分组权限上传与 RAG 透视接口。 |
| `backend/src/api/eval.py` | EvalRunRequest, get_eval_service, list_eval_cases, seed_eval_docs, run_eval_suite | src.api.deps, src.schemas.models, src.services.eval_service, src.services.rag_service | 测试集接口：供前端页面直接展示黄金测试集并一键运行评测。 |
| `backend/src/api/memories.py` | list_memories, create_memory, delete_memory | src.api.deps, src.repositories.memory_repo, src.schemas.models | 长期记忆管理 REST 接口：支持前端可视化查看、新增与人工纠偏删除。 |
| `backend/src/api/menus.py` | get_my_menus, get_all_menus, update_menu_config | src.api.deps, src.schemas.models, src.services.menu_service | 动态菜单 REST 接口：支持按角色拉取左侧菜单与管理员在线配置。 |
| `backend/src/api/sessions.py` | create_session, list_sessions, rename_session, delete_session, list_messages | src.api.deps, src.repositories.session_repo, src.schemas.models | 会话管理 REST 接口（严格按 user_id 隔离，支持重命名与删除）。 |
| `backend/src/api/tools.py` | list_available_tools, get_run_trace | src.api.deps, src.repositories.inventory_repo, src.repositories.trace_repo, src.repositories.workflow_repo, src.schemas.models, src.services.bom_service, src.services.memory_service, src.services.rag_service, src.services.tool_setup | 能力发现与轨迹审计接口（按用户权限裁剪工具列表）。 |
| `backend/src/api/workflows.py` | WorkflowSubmitRequest, WorkflowStatusUpdate, WorkflowDefinitionUpsert, list_workflow_skills, upsert_workflow_definition, submit_workflow, list_workflows, update_workflow_status | src.api.deps, src.repositories.workflow_repo, src.schemas.models, src.services.workflow_skills | 配置化企业流程中心 REST 接口（按角色过滤可用流程 + 动态新建流程类型 + 分页台账）。 |
| `backend/src/config.py` | Settings | - | 全局配置：使用 find_dotenv 向上查找 .env，杜绝硬编码 .parent 层级。 |
| `backend/src/core/agent_loop.py` | LLMCallable, AgentLoop | src.core.event_context, src.core.hooks, src.core.tool_registry, src.schemas.models | 透明可观测的智能体调度循环（Agent Kernel 核心）。 |
| `backend/src/core/event_context.py` | set_event_queue, emit_event, close_event_stream, set_auth_context, get_auth_context, set_recent_history, get_recent_history | src.schemas.models | 跨层上下文穿透通道：EventQueue（SSE）、AuthContext（权限）与 RecentHistory（指代改写）。 |
| `backend/src/core/hooks.py` | AgentHooks, make_noop_hooks, build_trace_payload | src.schemas.models | 智能体生命周期钩子（对标 Vue 生命周期 / 中间件），用于轨迹审计与高危拦截。 |
| `backend/src/core/tool_registry.py` | RegisteredTool, ToolRegistry | - | 声明式工具注册表：基于 Pydantic Schema 自动生成描述并校验入参。 |
| `backend/src/infra/http_client.py` | create_http_client, close_http_client | - | 全局复用的异步 HTTPX 客户端（用于大模型与外部 API 调用）。 |
| `backend/src/infra/postgres.py` | create_pg_pool, close_pg_pool | - | PostgreSQL 异步连接池生命周期管理（psycopg3）。 |
| `backend/src/infra/redis.py` | create_redis_client, close_redis_client | - | Redis 异步连接池管理（本地未启动 Redis 时允许降级运行）。 |
| `backend/src/main.py` | lifespan, health | src.api, src.config, src.infra.http_client, src.infra.postgres, src.infra.redis, src.repositories.bom_repo | FastAPI 应用入口：通过 lifespan 统一托管 Postgres / Redis / HTTPX 连接池。 |
| `backend/src/repositories/bom_quote_repo.py` | insert_quote_snapshot, list_quote_snapshots | - | 报价快照持久化：BomRepo 委托到此模块，避免仓库文件超出行数上限。 |
| `backend/src/repositories/bom_repo.py` | BomRepo | src.repositories.bom_quote_repo, src.repositories.bom_schema | BOM 仓库：独立库 bom_db 读写与自动增量列迁移（强制 user_id 隔离）。 |
| `backend/src/repositories/bom_schema.py` | run_v3_migration | - | BOM 库 V3 增量迁移：独立成模块，由 BomRepo 单例在生命周期内调用一次。 |
| `backend/src/repositories/doc_repo.py` | DocRepo | - | 商业化 RAG 文档与切片仓库（事务原子更新 + 分组数据权限 + GIN 全文检索）。 |
| `backend/src/repositories/inventory_repo.py` | InventoryRepo | - | 企业物料库存仓库（支持模糊名称检索与安全库存预警判定）。 |
| `backend/src/repositories/memory_repo.py` | MemoryRepo | - | 语义记忆仓库：memories 表读写（强制 user_id 隔离）。 |
| `backend/src/repositories/menu_repo.py` | MenuRepo | - | 动态菜单仓库：sys_menus 表读写与自动建表/种子兜底。 |
| `backend/src/repositories/session_repo.py` | SessionRepo | - | 情景记忆仓库：sessions 与 messages 持久化（含引用快照与重命名/删除）。 |
| `backend/src/repositories/trace_repo.py` | TraceRepo | - | 轨迹审计仓库：记录每次智能体运行的步骤、耗时与 Token（强制 user_id 隔离）。 |
| `backend/src/repositories/user_repo.py` | UserRepo | - | 用户与权限数据仓库（支持角色、分组数据权限与 PBKDF2 密码校验）。 |
| `backend/src/repositories/workflow_repo.py` | WorkflowRepo | - | 企业流程定义与实例数据仓库（配置化流程 + 分页台账 + 幂等审批）。 |
| `backend/src/schemas/bom_formula.py` | BomFormulaDraftRequest, BomFormulaSheetRow, BomFormulaBatchCheckRequest | - | 公式 AI 录入相关请求模型：口述编译、测试数据行、批量校验。 |
| `backend/src/schemas/models.py` | AuthContext, ToolCall, ChatMessage, AgentState, SSEEvent, DevLoginRequest, RegisterRequest, LoginRequest, SessionCreate, SessionUpdate, ChatRequest, MemoryCreate, BomItemCreate, BomEdgeCreate, BomEdgeUpdate, BomEdgeMove, BomEdgeBatchCreate, BomCloneRequest, QuoteSaveRequest, StockCheckRequest, BomFormulaCheckRequest, SysMenuUpdate | - | 跨层共享 Pydantic v2 契约模型（对标前端 TypeScript Interface）。 |
| `backend/src/services/bm25.py` | tokenize, bm25_rank, rrf_fuse | - | 中英混排 BM25 检索与 RRF 倒数排名融合算法。 |
| `backend/src/services/bom_costing.py` | BomCostingService, quote_snapshot_to_json | src.repositories.bom_repo, src.services.bom_formula | BOM 成本试算服务：多级递归算价、余料阈值核算、报价快照与跨库库存齐套核查。 |
| `backend/src/services/bom_formula.py` | dist3d, iif, safe_eval_formula, eval_formula_with_error, verify_rows, calc_remnant_qty | - | 安全 AST 表达式求值器与余料阈值核算：支持 iif() 条件、dist3d() 与整料余料报废计算。 |
| `backend/src/services/bom_formula_ai.py` | base_env, draft_formula | src.config, src.schemas.models, src.services.bom_formula, src.services.llm_service | 口述逻辑 → BOM 公式：LLM 编译为受限 DSL，回环自修复并输出样例求值。 |
| `backend/src/services/bom_formula_sheet.py` | build_template, parse_sheet | - | 测试数据模板生成与上传解析：openpyxl 显式读写 xlsx，另兼容 csv。 |
| `backend/src/services/bom_seed.py` | - | - | BOM 演示种子数据：示例机柜多级 BOM（物料清单与父子关系定义）。 |
| `backend/src/services/bom_service.py` | BomService | src.repositories.bom_repo, src.services.bom_costing, src.services.bom_seed | BOM 业务编排门面：物料/结构 CRUD 与批量写入，成本试算委托 BomCostingService。 |
| `backend/src/services/bom_tools.py` | BomQuoteArgs, BomStockArgs, register_bom_tools | src.core.event_context, src.core.tool_registry, src.services.bom_service | BOM 能力的智能体工具注册：成本试算报价与跨库库存齐套核查（挂载进 ToolRegistry）。 |
| `backend/src/services/chunker.py` | TextChunk, chunk_markdown | - | Markdown 结构感知切片器：保留标题面包屑并保护代码块不被截断。 |
| `backend/src/services/embedding_service.py` | EmbeddingService | src.config | 向量化与精排服务：支持 429/5xx 指数退避重试与本地 Mock 向量降级。 |
| `backend/src/services/eval_service.py` | EvalService | src.services.rag_service | RAG 自动化评测服务：加载黄金测试集并计算 Hit Rate@3、MRR 与关键词命中率。 |
| `backend/src/services/file_parser.py` | parse_uploaded_file, expand_uploaded_archive | - | 文件解析与安全解包服务：支持 .md / .txt / .pdf 及 .zip 批量安全解压。 |
| `backend/src/services/llm_service.py` | LLMService | src.config, src.schemas.models | 大模型适配器（类 Axios 封装）：支持对话、工具调用、多轮指代改写及本地 Mock 模式。 |
| `backend/src/services/memory_service.py` | MemoryService | src.core.event_context, src.repositories.memory_repo, src.repositories.session_repo, src.schemas.models | 四级记忆编排服务：协调 Redis 短期缓冲与 Postgres 情景/语义记忆。 |
| `backend/src/services/menu_service.py` | MenuService | src.repositories.menu_repo | 动态菜单编排服务：按角色返回可见菜单树并保护系统配置入口不被锁死。 |
| `backend/src/services/rag_service.py` | RagService | src.core.event_context, src.repositories.doc_repo, src.services.bm25, src.services.chunker, src.services.embedding_service, src.services.llm_service | 商业化 RAG 业务服务：分组数据权限 + 指代改写 + 混合检索 + 低分拒答护栏。 |
| `backend/src/services/tool_setup.py` | RagSearchArgs, MemorySaveArgs, WorkflowSubmitArgs, WorkflowQueryArgs, InventoryQueryArgs, build_tool_registry | src.core.event_context, src.core.tool_registry, src.repositories.inventory_repo, src.repositories.workflow_repo, src.services.bom_service, src.services.bom_tools, src.services.memory_service, src.services.rag_service, src.services.workflow_skills | 将 Services 能力（RAG、记忆、配置化流程、近期流程查询、库存检索、BOM 试算）注册为 Tool。 |
| `backend/src/services/workflow_skills.py` | validate_dynamic_workflow, build_workflow_skill_prompt | - | 配置化流程动态校验器与智能体 Skill 提示词生成器。 |

## Frontend (`frontend/src/`)

| File | Exports / Component |
| :--- | :--- |
| `frontend/src/App.vue` | App |
| `frontend/src/api/bomClient.ts` | listBomItems, upsertBomItem, deleteBomItem, listBomEdges, createBomEdge, batchAddBomEdges, moveBomEdge, deleteBomEdge, seedBomDemo, fetchBomRollupTree, updateBomEdge, cloneBomStructure, saveBomQuote, listBomQuotes, checkBomStock, checkBomFormula |
| `frontend/src/api/bomFormulaClient.ts` | FormulaSample, FormulaDraft, SheetRow, ParsedSheet, BatchRowResult, BatchCheck, draftBomFormula, batchCheckBomFormula, parseBomFormulaSheet, downloadBomFormulaTemplate |
| `frontend/src/api/bomTypes.ts` | BomItem, BomEdge, BomEdgeRule, BomNode, BomRollupResponse, makeDefaultRule, QuoteSnapshotItem, StockCheckItem, FormulaCheckResult |
| `frontend/src/api/client.ts` | UserInfo, EvalCase, EvalHit, EvalCaseResult, EvalRunResponse, DocItem, BatchUploadResponse, DebugStageHit, DebugRerankHit, DebugSearchResponse, SessionItem, ActionCardItem, MessageItem, MemoryItem, request, devLogin, loginUser, registerUser, listSessions, createSession, listSessionMessages, listMemories, createMemory, deleteMemory, fetchEvalCases, seedEvalDocs, runEvalSuite, listDocs, deleteDoc, uploadDocs, debugRagPipeline, ChatDebugOptions, RunStepItem, RunTraceResponse, renameSession, deleteSession, getRunTrace, WorkflowItem, WorkflowListResponse, listWorkflows, submitWorkflow, updateWorkflowStatus, WorkflowFieldDef, WorkflowDefinition, fetchWorkflowSkills, upsertWorkflowDefinition, SysMenuItem, fetchVisibleMenus, fetchAllMenus, updateSysMenu |
| `frontend/src/components/ApiTester.vue` | ApiTester |
| `frontend/src/components/BomAssembler.vue` | BomAssembler |
| `frontend/src/components/BomEdgeModal.vue` | BomEdgeModal |
| `frontend/src/components/BomFormulaStudio.vue` | BomFormulaStudio |
| `frontend/src/components/BomFormulaTestTable.vue` | BomFormulaTestTable |
| `frontend/src/components/BomInspector.vue` | BomInspector |
| `frontend/src/components/BomItemPanel.vue` | BomItemPanel |
| `frontend/src/components/BomManager.vue` | BomManager |
| `frontend/src/components/BomNodeCard.vue` | BomNodeCard |
| `frontend/src/components/BomPalette.vue` | BomPalette |
| `frontend/src/components/BomTreeEditor.vue` | BomTreeEditor |
| `frontend/src/components/ChatWorkspace.vue` | ChatWorkspace |
| `frontend/src/components/EvalDashboard.vue` | EvalDashboard |
| `frontend/src/components/FloatingCopilot.vue` | FloatingCopilot |
| `frontend/src/components/KnowledgeBase.vue` | KnowledgeBase |
| `frontend/src/components/MemoryManager.vue` | MemoryManager |
| `frontend/src/components/MenuManager.vue` | MenuManager |
| `frontend/src/components/PlatformOverview.vue` | PlatformOverview |
| `frontend/src/components/RetrievalLab.vue` | RetrievalLab |
| `frontend/src/components/WorkflowCenter.vue` | WorkflowCenter |
| `frontend/src/composables/useAgentStream.ts` | TraceLog, useAgentStream |
| `frontend/src/composables/useBom.ts` | useBom |
| `frontend/src/composables/useBomDrag.ts` | MAX_DEPTH, NodeMeta, TreeIndex, DropVerdict, UndoEntry, nodeKey, buildTreeIndex, useBomDrag |
| `frontend/src/composables/useBomFormulaStudio.ts` | useBomFormulaStudio |
| `frontend/src/composables/useMemories.ts` | useMemories |
| `frontend/src/main.ts` | - |
| `frontend/src/utils/bomCsv.ts` | exportBomCsv |
| `frontend/src/utils/markdown.ts` | renderMarkdown |
