-- ============================================================================
-- scripts/init_db.sql
-- 智能体开发框架 PostgreSQL 17 + pgvector 核心建表脚本
-- 覆盖：权限隔离 (users / api_keys) + 情景/语义/轨迹记忆体系
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ----------------------------------------------------------------------------
-- 1. 权限与多端接入层 (Auth & RBAC)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT NOT NULL UNIQUE,
    email           TEXT UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user'
                    CHECK (role IN ('admin', 'user', 'readonly')),
    -- 工具级白名单：AgentLoop 组装 Schema 时按此列表裁剪可见工具
    allowed_tools   TEXT[] NOT NULL DEFAULT ARRAY['rag_search'],
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    key_prefix      TEXT NOT NULL,          -- 明文前缀如 "agk_live_" 方便前端展示
    key_hash        TEXT NOT NULL UNIQUE,   -- SHA-256 哈希，禁止存明文 Key
    scopes          TEXT[] NOT NULL DEFAULT ARRAY['chat:stream', 'sessions:read'],
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys (user_id);

-- ----------------------------------------------------------------------------
-- 2. 情景记忆：会话与消息历史 (Episodic Memory)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_name      TEXT NOT NULL DEFAULT 'default',
    title           TEXT NOT NULL DEFAULT '新对话',
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_updated
    ON sessions (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    -- 冗余 user_id：使 Repo 层所有查询可直接带 WHERE user_id = $1，无需强依赖 JOIN
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    run_id          UUID,
    role            TEXT NOT NULL
                    CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content         TEXT NOT NULL DEFAULT '',
    tool_calls      JSONB,                  -- assistant 发起的工具调用列表
    tool_call_id    TEXT,                   -- role = 'tool' 时回填的关联 ID
    token_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session_seq
    ON messages (session_id, id ASC);
CREATE INDEX IF NOT EXISTS idx_messages_user_created
    ON messages (user_id, created_at DESC);

-- ----------------------------------------------------------------------------
-- 3. 语义记忆：长期偏好与事实向量库 (Semantic Memory · pgvector)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_session  UUID REFERENCES sessions(id) ON DELETE SET NULL,
    memory_type     TEXT NOT NULL DEFAULT 'fact'
                    CHECK (memory_type IN ('fact', 'preference', 'summary')),
    content         TEXT NOT NULL,
    -- 默认适配智谱 embedding-3 (1024 维)；若切换 OpenAI text-embedding-3-small 改为 1536
    embedding       vector(1024),
    importance      SMALLINT NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_user_active
    ON memories (user_id, memory_type)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_memories_embedding_hnsw
    ON memories USING hnsw (embedding vector_cosine_ops);

-- ----------------------------------------------------------------------------
-- 4. 轨迹审计：运行实例与单步快照 (Trace Memory)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'waiting_approval', 'completed', 'failed')),
    model_name      TEXT NOT NULL,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER,
    error_message   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_session
    ON agent_runs (session_id, started_at DESC);

CREATE TABLE IF NOT EXISTS run_steps (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    step_index      INTEGER NOT NULL,
    step_type       TEXT NOT NULL
                    CHECK (step_type IN ('llm_call', 'tool_call', 'approval', 'memory_write')),
    tool_name       TEXT,
    input_payload   JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload  JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_ms     INTEGER,
    status          TEXT NOT NULL DEFAULT 'ok'
                    CHECK (status IN ('ok', 'error', 'rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_run_steps_run_seq
    ON run_steps (run_id, step_index ASC);

-- ----------------------------------------------------------------------------
-- 5. 商业化 RAG 知识库：文档元数据与结构化切片 (Documents & Chunks)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kb_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_path     TEXT NOT NULL,
    title           TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'general',
    content_hash    TEXT NOT NULL,          -- SHA-256 增量去重指纹
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'archived')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, source_path)
);

CREATE INDEX IF NOT EXISTS idx_kb_documents_user_cat
    ON kb_documents (user_id, category)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS kb_chunks (
    id              BIGSERIAL PRIMARY KEY,
    document_id     UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    heading_path    TEXT NOT NULL DEFAULT '',
    content         TEXT NOT NULL,
    embedding       vector(1024),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_seq
    ON kb_chunks (document_id, chunk_index ASC);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_user_id
    ON kb_chunks (user_id);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding_hnsw
    ON kb_chunks USING hnsw (embedding vector_cosine_ops);

-- 增量追加：PostgreSQL 原生全文检索列与 GIN 倒排索引
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS search_tsv TSVECTOR;
CREATE INDEX IF NOT EXISTS idx_kb_chunks_tsv_gin ON kb_chunks USING gin (search_tsv);

-- 增量追加：用户分组与文档分组数据权限
ALTER TABLE users ADD COLUMN IF NOT EXISTS groups TEXT[] NOT NULL DEFAULT ARRAY['public'];
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS allowed_groups TEXT[] NOT NULL DEFAULT ARRAY['private'];
CREATE INDEX IF NOT EXISTS idx_kb_documents_groups_gin ON kb_documents USING gin (allowed_groups);

-- 增量追加：messages 持久化引用快照
ALTER TABLE messages ADD COLUMN IF NOT EXISTS citations JSONB;

-- ----------------------------------------------------------------------------
-- 6. 企业流程引擎：OA 审批与 SRM 招标流程实例表
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow_instances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flow_code       TEXT NOT NULL CHECK (flow_code IN ('oa_approval', 'srm_bidding')),
    title           TEXT NOT NULL,
    form_data       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          TEXT NOT NULL DEFAULT 'submitted'
                    CHECK (status IN ('submitted', 'approved', 'rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_user_flow_created
    ON workflow_instances (user_id, flow_code, created_at DESC);

-- ----------------------------------------------------------------------------
-- 7. 企业物料库存表 & 对话卡片/流程审计增强
-- ----------------------------------------------------------------------------

ALTER TABLE messages ADD COLUMN IF NOT EXISTS action_cards JSONB;

ALTER TABLE workflow_instances ADD COLUMN IF NOT EXISTS approved_by TEXT;
ALTER TABLE workflow_instances ADD COLUMN IF NOT EXISTS action_channel TEXT;
ALTER TABLE workflow_instances ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS inventory_items (
    id              SERIAL PRIMARY KEY,
    sku             TEXT NOT NULL UNIQUE,
    item_name       TEXT NOT NULL,
    category        TEXT NOT NULL,
    spec            TEXT NOT NULL DEFAULT '',
    stock_qty       INTEGER NOT NULL DEFAULT 0,
    safety_stock    INTEGER NOT NULL DEFAULT 10,
    unit            TEXT NOT NULL DEFAULT '台',
    warehouse       TEXT NOT NULL DEFAULT '杭州一号仓',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO inventory_items (sku, item_name, category, spec, stock_qty, safety_stock, unit, warehouse)
VALUES
    ('SRV-R750-01', '机架式GPU服务器', '计算设备', '双路至强 / 4x RTX4090 / 256G', 3, 10, '台', '杭州一号仓'),
    ('SRV-R650-02', '通用应用服务器', '计算设备', '64核 / 128G / 4TB NVMe', 18, 10, '台', '杭州一号仓'),
    ('NET-S5735-01', '千兆核心交换机', '网络设备', '48口全千兆 / 双电源', 4, 8, '台', '杭州二号仓'),
    ('NET-CE6881-02', '万兆接入交换机', '网络设备', '48口万兆SFP+ / 6口40G', 14, 6, '台', '杭州二号仓'),
    ('OPT-10G-SR', '万兆多模光模块', '网络配件', '10G SFP+ 850nm 300m', 120, 50, '个', '杭州二号仓'),
    ('IPC-BOX-2070', '工业视觉工控机', '工控设备', 'i7 / RTX2070 / 无风扇防尘', 2, 5, '台', '临安制造仓'),
    ('SSD-NVME-4T', '企业级NVMe固态硬盘', '存储配件', '3.84TB U.2 PCIe 4.0', 25, 15, '块', '杭州一号仓'),
    ('CBL-CAT6A-305', '六类屏蔽网线', '综合布线', 'Cat6A 305米/箱 低烟无卤', 6, 12, '箱', '临安制造仓')
ON CONFLICT (sku) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 8. 配置化流程定义表 & 外部访客角色 (external_guest)
-- ----------------------------------------------------------------------------

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
    CHECK (role IN ('admin', 'user', 'readonly', 'external_guest'));

ALTER TABLE workflow_instances DROP CONSTRAINT IF EXISTS workflow_instances_flow_code_check;

CREATE TABLE IF NOT EXISTS workflow_definitions (
    flow_code       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    allowed_roles   TEXT[] NOT NULL DEFAULT ARRAY['admin', 'user'],
    fields          JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO workflow_definitions (flow_code, name, description, allowed_roles, fields)
VALUES
(
    'oa_approval',
    'OA 审批流程',
    '内部请假、报销与常规采购申请',
    ARRAY['admin', 'user'],
    '[
      {"key":"flow_type","label":"流程类型","type":"select","required":true,"options":["leave","expense","purchase"],"default":"purchase"},
      {"key":"title","label":"审批标题","type":"text","required":true,"default":"采购研发测试设备"},
      {"key":"amount","label":"涉及金额(元)","type":"number","required":true,"default":5000},
      {"key":"urgency","label":"紧急程度","type":"select","required":true,"options":["normal","urgent"],"default":"normal"},
      {"key":"expected_date","label":"期望日期","type":"date","required":true,"default":"2026-11-25"},
      {"key":"reason","label":"申请事由","type":"text","required":true,"default":"研发测试需要"}
    ]'::jsonb
),
(
    'srm_bidding',
    'SRM 招标流程',
    '大额设备与供应链招投标立项（仅管理员可发起）',
    ARRAY['admin'],
    '[
      {"key":"project_name","label":"招标项目名称","type":"text","required":true,"default":"算力集群采购招标"},
      {"key":"bidding_type","label":"招标方式","type":"select","required":true,"options":["public","invited","inquiry"],"default":"public"},
      {"key":"budget_amount","label":"预算金额(元)","type":"number","required":true,"min_gt":0,"default":500000},
      {"key":"bid_deadline","label":"截标日期","type":"date","required":true,"default":"2026-12-05"},
      {"key":"supplier_qualification","label":"供应商资质要求","type":"text","required":true,"default":"具备原厂授权资质"},
      {"key":"delivery_address","label":"交货地点","type":"text","required":true,"default":"杭州研发中心"}
    ]'::jsonb
),
(
    'visitor_pass',
    '外部访客预约',
    '外部客户/供应商入园拜访预约（外部访客可发起）',
    ARRAY['admin', 'user', 'external_guest'],
    '[
      {"key":"visitor_name","label":"访客姓名","type":"text","required":true,"default":""},
      {"key":"company","label":"所属公司","type":"text","required":true,"default":""},
      {"key":"visit_date","label":"来访日期","type":"date","required":true,"default":"2026-11-20"},
      {"key":"host_person","label":"对接人","type":"text","required":true,"default":"沈工"},
      {"key":"purpose","label":"来访事由","type":"text","required":true,"default":"技术交流"}
    ]'::jsonb
)
ON CONFLICT (flow_code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 9. 后台管理系统：数据库动态菜单配置表 (sys_menus)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sys_menus (
    menu_key        TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    group_name      TEXT NOT NULL,
    icon            TEXT NOT NULL DEFAULT '▣',
    sort_order      INTEGER NOT NULL DEFAULT 10,
    allowed_roles   TEXT[] NOT NULL DEFAULT ARRAY['admin', 'user', 'readonly'],
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO sys_menus (menu_key, title, group_name, icon, sort_order, allowed_roles, is_enabled)
VALUES
    ('overview',   '能力全景概览', '工作台',     '◈', 10, ARRAY['admin', 'user', 'readonly', 'external_guest'], TRUE),
    ('bom',        'BOM 算料维护', '业务中心',   '❖', 20, ARRAY['admin', 'user', 'readonly'], TRUE),
    ('workflow',   'OA/SRM 流程',  '业务中心',   '⚡', 30, ARRAY['admin', 'user', 'external_guest'], TRUE),
    ('chat',       'AI 流程工作台','AI 与记忆',  '✦', 40, ARRAY['admin', 'user', 'readonly', 'external_guest'], TRUE),
    ('mem',        '长期记忆中心', 'AI 与记忆',  '◉', 50, ARRAY['admin', 'user'], TRUE),
    ('kb',         '知识库管理',   '系统管理',   '▤', 60, ARRAY['admin', 'user', 'readonly'], TRUE),
    ('lab',        '命中透视台',   '系统管理',   '◎', 70, ARRAY['admin', 'user', 'readonly'], TRUE),
    ('eval',       '黄金测试集',   '系统管理',   '★', 80, ARRAY['admin', 'user', 'readonly'], TRUE),
    ('api',        '接口测试台',   '系统管理',   '⌘', 90, ARRAY['admin', 'user'], TRUE),
    ('menu_admin', '动态菜单配置', '系统管理',   '⚙', 100, ARRAY['admin'], TRUE)
ON CONFLICT (menu_key) DO NOTHING;
