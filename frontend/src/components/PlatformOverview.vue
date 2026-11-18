<script setup lang="ts">
const emit = defineEmits<{
  navigate: [tab: 'overview' | 'bom' | 'chat' | 'workflow' | 'mem' | 'lab' | 'kb' | 'eval' | 'api']
}>()

const aiDimensions = [
  {
    badge: '核心亮点 · 3D 工业 BOM',
    title: 'Three.js 参数化装配 + 工程算料与余料阈值',
    pain: '传统痛点：ERP 只管静态清单，非标算料靠手算 Excel，余料报废与空间干涉全凭经验。',
    solution: '全栈方案：独立 bom_db 递归算价（200 节点 < 5ms）+ AST 安全公式/AI 口述编译 + Box3 碰撞检测 + 跨库查库存与带图报价单打印。',
    tab: 'bom' as const,
    cta: '1 分钟体验 3D BOM 工作台 →',
  },
  {
    badge: '维度一 · 交互革命',
    title: '对话式流程发起与卡片直办',
    pain: '传统痛点：员工要翻十几个表单菜单、记不清报销或招标必填规范。',
    solution: 'AI 方案：发一段话即可由 Skill 引导补全字段、Pydantic 强校验落库，并在气泡内直接「一键审批」或弹窗看详情。',
    tab: 'workflow' as const,
    cta: '体验 OA / SRM 流程',
  },
  {
    badge: '维度二 · 业务联动',
    title: '库存感知与采购决策闭环',
    pain: '传统痛点：查完 ERP 库存发现缺货，还要手动切去 OA/SRM 重新填采购单。',
    solution: 'AI 方案：模糊检索物料库存并自动识别安全库存缺口，触发红色预警卡片，一键直达采购发起。',
    tab: 'chat' as const,
    cta: '去对话查库存',
  },
  {
    badge: '维度三 · 权限与可信',
    title: '部门分组隔离与低分拒答护栏',
    pain: '传统痛点：文档全员混查泄密，大模型查不到资料时容易靠幻觉胡编。',
    solution: 'AI 方案：按用户所属分组隔离知识库（含外部访客角色），Rerank 低于阈值自动拒答，每条回答可点开原文抽屉。',
    tab: 'lab' as const,
    cta: '打开命中透视台',
  },
  {
    badge: '维度四 · 记忆与审计',
    title: '个人长期记忆与 Trace 时间旅行',
    pain: '传统痛点：AI 越聊越忘、记错偏好无法修改，出问题只能猜黑盒。',
    solution: 'AI 方案：个人记忆与对话双向同步、支持人工纠偏删除；每条回复均可回放完整推理步数、工具入参出参与耗时。',
    tab: 'mem' as const,
    cta: '查看个人记忆系统',
  },
]

const prominentTodos = [
  {
    priority: 'P0 · 高频亮点',
    title: '高危操作人工确认 (Human-in-the-Loop)',
    desc: '大额 SRM 招标（如 > 5 万）或批量删记忆前，通过 pre_tool 钩子暂停循环并向前端推送确认弹窗，人工放行后才真正执行。',
  },
  {
    priority: 'P0 · 成本审计',
    title: '企业审计与 Token 成本统计大盘',
    desc: '聚合 agent_runs 与 run_steps 数据，可视化展示各部门/各模型 Token 消耗、平均响应耗时、工具成功率与异常追踪。',
  },
  {
    priority: 'P1 · 系统集成',
    title: 'API Key 网关与企业 SSO 打通',
    desc: '补齐 api_keys 签发/吊销与 X-API-Key 鉴权，并支持对接企微/钉钉组织架构自动同步用户分组。',
  },
  {
    priority: 'P1 · 检索进阶',
    title: '真中文分词 (jieba) + 多级会签状态机',
    desc: '替换双字滑窗并用 Postgres setweight 提升标题权重；把一级审批扩展为按金额触发的部门+财务多级会签。',
  },
]

const quickEntries = [
  { label: '黄金测试集评测', tab: 'eval' as const },
  { label: '知识库批量 / ZIP 上传', tab: 'kb' as const },
  { label: '接口自动化测试台', tab: 'api' as const },
]
</script>

<template>
  <section class="overview">
    <!-- 顶部核心价值定位（面向业务与面试展示） -->
    <header class="hero">
      <div class="hero-left">
        <span class="badge badge-blue">AI-Native Engineering · 3 天协作交付全栈与 3D 工业原型</span>
        <h1>用 AI 快速造出公司需要的工具，把“廉价工具的积累”变成核心资产</h1>
        <p class="sub">
          你现在看到的整套系统（3D 参数化 BOM 算料、AST 公式引擎、跨库库存、OA/SRM 审批、RAG 知识库与长期记忆），只是借助 AI 耗时 3 天完成的结果。随着 AI 能力不断进化，低成本定制工具的持续沉淀将成为企业的巨大财富——而我可以帮你加速这一过程。
        </p>
        <div class="hero-actions">
          <button class="btn btn-primary" @click="emit('navigate', 'bom')">体验 3D BOM 工作台</button>
          <button class="btn" @click="emit('navigate', 'chat')">进入 AI 对话实战</button>
          <button class="btn" @click="emit('navigate', 'workflow')">体验 OA / SRM 流程中心</button>
          <button
            v-for="q in quickEntries"
            :key="q.tab"
            class="btn ghost"
            @click="emit('navigate', q.tab)"
          >
            {{ q.label }}
          </button>
        </div>
      </div>
    </header>

    <!-- 核心板块一：流程的 AI 多维度展开 -->
    <div class="section">
      <div class="sec-head">
        <h2>一、业务流程的 AI 多维度展开（已落地闭环）</h2>
        <span class="sec-tip">每项能力均可点击右下角直接进入实操演示</span>
      </div>
      <div class="dim-grid">
        <div v-for="d in aiDimensions" :key="d.title" class="dim-card">
          <span class="badge badge-ok">{{ d.badge }}</span>
          <h3>{{ d.title }}</h3>
          <p class="pain">{{ d.pain }}</p>
          <p class="sol">{{ d.solution }}</p>
          <button class="btn btn-primary go-btn" @click="emit('navigate', d.tab)">{{ d.cta }} →</button>
        </div>
      </div>
    </div>

    <!-- 核心板块二：显眼位置的后续演进 TODO -->
    <div class="todo-banner">
      <div class="sec-head">
        <h2>二、后续企业级演进规划 (Roadmap &amp; TODO)</h2>
        <span class="sec-tip">面向真实生产环境与高并发治理的下一阶段目标</span>
      </div>
      <div class="todo-grid">
        <div v-for="t in prominentTodos" :key="t.title" class="todo-card">
          <span class="badge badge-blue">{{ t.priority }}</span>
          <h3>{{ t.title }}</h3>
          <p>{{ t.desc }}</p>
        </div>
      </div>
    </div>

    <!-- 底部弱化展示技术底座（放在其次） -->
    <footer class="tech-foot">
      <strong>底层技术栈参考：</strong>
      <span>Vue 3.5 + TypeScript + Vite (Fetch ReadableStream SSE) · Python 3.12 + FastAPI + Pydantic v2 · PostgreSQL 17 (pgvector + GIN) + Redis</span>
    </footer>
  </section>
</template>

<style scoped>
.overview { display: flex; flex-direction: column; gap: 22px; }
.hero {
  background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
  border: 1px solid #bfdbfe; border-radius: 14px; padding: 24px 28px;
}
.hero h1 { margin: 10px 0 8px; font-size: 24px; }
.sub { margin: 0 0 16px; color: #374151; font-size: 14px; max-width: 780px; line-height: 1.6; }
.hero-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.ghost { background: rgba(255, 255, 255, 0.8); }

.sec-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.sec-head h2 { margin: 0; font-size: 17px; }
.sec-tip { font-size: 12px; color: var(--muted); }

.dim-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.dim-card {
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 18px; display: flex; flex-direction: column; gap: 8px;
}
.dim-card h3 { margin: 4px 0 0; font-size: 16px; }
.pain { margin: 0; font-size: 12px; color: var(--muted); line-height: 1.5; }
.sol { margin: 0; font-size: 13px; color: var(--text); line-height: 1.55; flex: 1; }
.go-btn { align-self: flex-start; margin-top: 6px; }

.todo-banner {
  background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 14px; padding: 20px 24px;
}
.todo-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
.todo-card {
  background: var(--card); border: 1px solid var(--border); border-left: 4px solid var(--primary);
  border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 6px;
}
.todo-card h3 { margin: 2px 0 0; font-size: 14px; }
.todo-card p { margin: 0; font-size: 12px; color: var(--muted); line-height: 1.5; }

.tech-foot {
  font-size: 12px; color: var(--muted); text-align: center; padding: 8px 0; border-top: 1px solid var(--border);
}
</style>
