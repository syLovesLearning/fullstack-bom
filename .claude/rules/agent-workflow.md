# Agent 开发工作流规范

1. **索引定位**：先读 `CLAUDE.md` 与 `docs/CODE_INDEX.md` 锁定目标文件，减少全仓扫源码。
2. **大需求导图（可选）**：仅在跨模块大需求或架构重构时，按需运行 `python3 scripts/translate_requirement.py` 生成 `.xmind`；日常小需求直接开发，不强制产导图。
3. **契约先行**：涉及接口或 SSE 变更时，先更新 `docs/API_SPEC.md`。
4. **编码与门禁**：保持单文件 < 200 行；改完跑 `cd backend && make verify && make test` 与 `cd frontend && pnpm build`。
5. **刷新记忆**：运行 `python3 scripts/gen_code_index.py` 更新代码地图（如本地 Postgres 运行中，可执行 `python3 scripts/sync_repo_memory.py`）。
