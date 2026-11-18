"""BOM 库 V3 增量迁移：独立成模块，由 BomRepo 单例在生命周期内调用一次。"""

from psycopg_pool import AsyncConnectionPool

V3_DDL = """
    ALTER TABLE bom_edges ADD COLUMN IF NOT EXISTS extra_cost_expr TEXT NOT NULL DEFAULT '';
    ALTER TABLE bom_edges ADD COLUMN IF NOT EXISTS remnant_policy VARCHAR(24) NOT NULL DEFAULT 'CONTINUOUS';
    ALTER TABLE bom_edges ADD COLUMN IF NOT EXISTS unit_pack_size NUMERIC(12, 4) NOT NULL DEFAULT 1;
    ALTER TABLE bom_edges ADD COLUMN IF NOT EXISTS min_remnant NUMERIC(12, 4) NOT NULL DEFAULT 0;
    ALTER TABLE bom_edges ADD COLUMN IF NOT EXISTS loss_rate NUMERIC(6, 4) NOT NULL DEFAULT 0;
    CREATE TABLE IF NOT EXISTS quote_snapshots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        quote_no VARCHAR(64) NOT NULL,
        root_item_id UUID NOT NULL REFERENCES bom_items(id),
        root_name VARCHAR(128) NOT NULL,
        params_3d_json JSONB NOT NULL,
        result_json JSONB NOT NULL,
        direct_cost NUMERIC(12, 2) NOT NULL,
        final_price NUMERIC(12, 2) NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
"""


async def run_v3_migration(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(V3_DDL)
