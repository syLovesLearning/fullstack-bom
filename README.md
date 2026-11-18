# 透明智能体全栈项目（FastAPI + Vue 3 + RAG 黄金测试集控制台）

## 1. 启动后端（终端 1）

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
make migrate && make dev
```

## 2. 启动前端（终端 2）

```bash
cd frontend
pnpm install
pnpm dev
```

打开浏览器访问 `http://localhost:5173`，页面会自动完成鉴权并进入**「RAG 黄金测试集」**控制台：
1. 点击**「一键运行测试集」**，系统会自动将示例研发文档写入 PostgreSQL，并逐条运行 `backend/eval/golden_qa.json` 的 6 道测试题，在页面中实时展示 **通过数、Hit Rate@3、MRR、平均耗时** 以及每道题的召回片段。
2. 切换到**「智能体对话 & SSE 轨迹」**，可实时观测 `EventContext` 穿透推送的 `thought`、`tool_start`、`tool_result` 与 `citations` 引用溯源。

## 3. 初始化独立 BOM 库 (`bom_db`) 与基础后台维护

```bash
createdb bom_db
psql "${BOM_PG_DSN:-postgresql://shenyang@localhost:5432/bom_db}" -f backend/scripts/init_bom_db.sql
```

启动前后端后，点击顶部导航 **「BOM 维护」** → **「一键写入示例机柜 BOM」**，即可体验物料 CRUD、防环路父子关系配置与成本向/BOM 向双视图试算。
