-- 独立 BOM 数据库 (bom_db) V3 建表脚本（含余料阈值、特殊附加成本与报价快照）
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS bom_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    sku_code    VARCHAR(64) NOT NULL,
    name        VARCHAR(128) NOT NULL,
    category    VARCHAR(32) NOT NULL,
    sub_type    VARCHAR(32) NOT NULL,
    unit        VARCHAR(16) NOT NULL DEFAULT '个',
    base_price  NUMERIC(12, 2) NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, sku_code)
);

CREATE TABLE IF NOT EXISTS bom_headers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    item_id     UUID NOT NULL REFERENCES bom_items(id) ON DELETE CASCADE,
    version     VARCHAR(16) NOT NULL DEFAULT 'V1.0',
    status      VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(item_id, version)
);

CREATE TABLE IF NOT EXISTS bom_edges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    bom_header_id   UUID NOT NULL REFERENCES bom_headers(id) ON DELETE CASCADE,
    child_item_id   UUID NOT NULL REFERENCES bom_items(id),
    qty_mode        VARCHAR(16) NOT NULL DEFAULT 'FIXED',
    base_qty        NUMERIC(12, 4) NOT NULL DEFAULT 1,
    formula_expr    TEXT NOT NULL DEFAULT '',
    extra_cost_expr TEXT NOT NULL DEFAULT '',
    remnant_policy  VARCHAR(24) NOT NULL DEFAULT 'CONTINUOUS',
    unit_pack_size  NUMERIC(12, 4) NOT NULL DEFAULT 1,
    min_remnant     NUMERIC(12, 4) NOT NULL DEFAULT 0,
    loss_rate       NUMERIC(6, 4) NOT NULL DEFAULT 0,
    float_factor    NUMERIC(6, 4) NOT NULL DEFAULT 1.0000,
    bom_group       VARCHAR(32) NOT NULL DEFAULT '材料',
    cost_group      VARCHAR(32) NOT NULL DEFAULT '基材',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quote_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    quote_no        VARCHAR(64) NOT NULL,
    root_item_id    UUID NOT NULL REFERENCES bom_items(id),
    root_name       VARCHAR(128) NOT NULL,
    params_3d_json  JSONB NOT NULL,
    result_json     JSONB NOT NULL,
    direct_cost     NUMERIC(12, 2) NOT NULL,
    final_price     NUMERIC(12, 2) NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bom_items_user ON bom_items(user_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_bom_edges_header ON bom_edges(bom_header_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_quote_user ON quote_snapshots(user_id, created_at DESC);
