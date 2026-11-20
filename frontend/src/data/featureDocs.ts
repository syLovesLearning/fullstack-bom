export interface FeatureDocItem {
  key: string
  menuKey: string
  category: '业务中心' | 'AI 与记忆' | '系统管理' | '基础底座'
  title: string
  subtitle: string
  capabilities: string[]
  steps: string[]
  tips?: string
}

export const FEATURE_DOCS: FeatureDocItem[] = [
  {
    key: 'bom',
    menuKey: 'bom',
    category: '业务中心',
    title: '3D 参数化 BOM 算料与余料套裁',
    subtitle: '以“定制金属工作台”和“四层重型货架”为例，实时联动 3D 模型、公式引擎与含税报价。',
    capabilities: [
      'Three.js 实时 3D 装配体渲染：支持爆炸视图、视角预设、点击零件高亮与尺寸碰撞预警',
      '安全公式 AST 引擎：支持 H/W/D/T 变量、iif() 条件分支与 dist3d() 空间计算',
      '三种余料套裁策略：连续折算 / 整包装向上取整 / 阈值废料 + 2D 钢板套裁 SVG 预览',
      '全链路维护：Where-Used 反查、跨产品批量替换零件、按分类一键调价与打印报价单',
    ],
    steps: [
      '在顶部选择产品（如 PROD-DESK-01 定制金属工作台）',
      '拖动 H/W/D/T 参数滑块，观察右侧 3D 模型尺寸变化与材料用量重算',
      '点击「生成报价单」或切换到底部标签查看「余料套裁 SVG」与「公式实验室」',
    ],
  },
  {
    key: 'chat',
    menuKey: 'chat',
    category: 'AI 与记忆',
    title: 'AI 流程工作台 & 悬浮副驾',
    subtitle: '全屏工作台与右下角悬浮窗共享同一会话状态，透明展示每一步推理轨迹与工具调用。',
    capabilities: [
      '透明推理轨迹：实时流式推送 thought / tool_start / tool_result / token / error 事件',
      '多轮上下文记忆：自动携带最近 12 条对话并挂载用户长期记忆，支持连续补全表单字段',
      '交互式业务卡片：对话内直接生成 BOM 报价卡片、库存预警卡片与可审批流程卡片',
      '中文输入法防误发：组字确认回车不会提前发送消息，支持随时中止流式生成',
    ],
    steps: [
      '点击右下角「AI 助手」或进入左侧「AI 流程工作台」',
      '直接提问业务问题，例如“按 H=2200 W=1000 试算工作台报价”或“我想加一个新计算工具”',
      '展开推理气泡可查看底层参数与耗时，点击卡片按钮可一键审批或跳转对应页面',
    ],
  },
  {
    key: 'workflow',
    menuKey: 'workflow',
    category: '业务中心',
    title: 'OA / SRM 流程中心 & 对话需求立项',
    subtitle: '配置化动态表单引擎，打通“对话提需求 → 审批通过 → 外部微服务/本地挂载上线”。',
    capabilities: [
      '配置化流程定义：管理员可在页面动态新增流程类型、字段校验规则与角色可见范围',
      '对话式需求立项：AI 先调用 analyze_tool_demand 生成需求清单，用户确认后提交 tool_demand 流程',
      '统一审批台账：支持分页筛选、详情抽屉、防自审自批校验与聊天卡片联动审批',
      '交付与微服务挂载：审批通过后可填写研发回复并一键将外部微服务 URL 挂入左侧菜单',
    ],
    steps: [
      '用顶部「预览角色」切到研发工程师（user），在聊天框提出新工具需求并确认清单',
      '切回管理员（admin）进入「OA/SRM 流程」审批通过该单据',
      '点击「交付/挂载」，填入研发回复与外部地址（或本地编码）后保存，左侧菜单立即刷新',
    ],
  },
  {
    key: 'role_admin',
    menuKey: 'role_admin',
    category: '系统管理',
    title: '角色与 AI 能力权限管理',
    subtitle: '控制每个角色允许在 AI 聊天框中调用的具体接口，保存后无需重新登录实时生效。',
    capabilities: [
      '动态接口目录：直接读取系统注册的全部 Tool 清单与参数说明，支持勾选授权',
      '自定义角色扩展：除内置 4 类角色外，可新建如 sales_rep 等自定义角色',
      '双层权限兜底：不仅对大模型隐藏无权工具，在工具执行层也会拦截越权调用',
      '联动透视与预览：展示角色关联的菜单/流程，并在 dev 模式支持顶部下拉一键切换体验',
    ],
    steps: [
      '进入「角色与能力」，选择需要调整的角色或点击「+ 新建角色」',
      '勾选或取消该角色允许在聊天框调用的接口（如取消 bom_save_quote），点击保存',
      '在顶部「预览角色」切换到该角色，打开聊天框即可验证工具权限已实时裁剪',
    ],
  },
  {
    key: 'menu_admin',
    menuKey: 'menu_admin',
    category: '系统管理',
    title: '数据库动态菜单配置',
    subtitle: '基于 PostgreSQL sys_menus 表实时编排左侧导航栏的名称、分组、排序与外部微应用。',
    capabilities: [
      '实时热更新：修改菜单名称、图标、排序或角色可见性后，左侧导航栏无需重启立即同步',
      '防锁死保护：系统核心管理菜单强制保留 admin 访问权与启用状态',
      '外部微前端容器：支持配置 external_url，将独立部署的其他项目页面直接嵌入工作区',
    ],
    steps: [
      '进入「动态菜单配置」，调整任意菜单的分组、排序权重或允许访问的角色',
      '点击「保存」，观察左侧导航栏实时重排与显隐变化',
    ],
  },
  {
    key: 'mem',
    menuKey: 'mem',
    category: 'AI 与记忆',
    title: '四级长期记忆中心',
    subtitle: '协调 Redis 短期会话缓冲与 PostgreSQL 长期事实/偏好记忆，让智能体越用越懂你。',
    capabilities: [
      '对话自动写入：在聊天中说“记住我的偏好…”，AI 会调用 memory_save 持久化入库',
      '手动管理台账：支持查看、新增与删除 fact / preference / summary 三类记忆',
      '每次对话自动注入：系统自动检索用户最新长期记忆拼接到智能体上下文',
    ],
    steps: [
      '在「长期记忆中心」手动添加一条业务偏好，或在聊天框让 AI 记住报价毛利要求',
      '发起新对话测试，AI 会自动遵循已保存的记忆偏好作答',
    ],
  },
  {
    key: 'kb',
    menuKey: 'kb',
    category: '系统管理',
    title: '混合检索知识库 / 命中透视 / 黄金评测',
    subtitle: 'BM25 关键词 + pgvector 向量语义双路召回，配合 RRF 融合与自动化评测看板。',
    capabilities: [
      '知识库管理（kb）：支持文档上传、切片入库与分组权限隔离（public / engineering / finance）',
      '命中透视台（lab）：可视化对比 BM25、向量召回与 RRF 融合后的得分明细',
      '黄金测试集（eval）：一键播种测试文档并运行 Recall@K / 拒绝率自动化回归评测',
    ],
    steps: [
      '在「知识库管理」上传研发文档或使用默认测试集',
      '在「命中透视台」输入问题观察召回片段与分数，或在「黄金测试集」运行一键评测',
    ],
  },
  {
    key: 'api',
    menuKey: 'api',
    category: '基础底座',
    title: '接口测试台 & 双模式鉴权门禁',
    subtitle: '内置 REST/SSE 调试台，兼顾本地免密极速开发与公网发布个人密钥防护。',
    capabilities: [
      '接口测试台（api）：直接在线调试核心后端接口与流式响应',
      'ENV=dev 免密直进：make dev 启动时自动以管理员进入，顶部可一键切换预览角色',
      'ENV=prod 密钥门禁：发布模式下自动锁定全局界面，需输入个人访问密钥解锁',
    ],
    steps: [
      '开发调试直接执行 make dev 即可免密进入全部功能',
      '需要对外演示或部署时将 ENV 设为 prod，通过个人访问密钥验证后进入系统',
    ],
  },
]
