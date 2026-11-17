# HAP App Copilot（明道云应用全生命周期智能助手）

基于明道云（HAP）MCP 工具链的一站式应用全生命周期智能助手 Skill，完整覆盖**方案设计（Plan）、自动搭建（Build）、存量修订（Modify）与质量审查（Audit）**。

## 功能概述

本 Skill 支持三大核心场景（四阶段闭环）：

- **场景 A：修改已有应用（Modify）** — 面向线上存量应用的 12 大业务域（应用与导航、工作表与字段、视图与自定义动作、业务规则、工作流与审批、角色权限、自定义页面与统计图、AI 对话机器人、公开表单、外部门户、打印模板、记录数据）提供外科手术式增量修订。主 Agent 通过 `scripts/resolve_context.py` 渐进切片加载跨模块影响地图、领域操作手册与底层 Spec，严格执行实时摸底、连带影响分析、二元风险门禁（`low`/`high`）、最小写入与写后回读核验。
- **场景 B：从零新建与断点恢复（Plan & Build）** — 从**业务方案设计（Plan）**到**物理并发搭建（Build）**的全自动流水线：
  1. **Plan 阶段** — 主 Agent 交互式生成并联动修订结构化方案（`hap-plan-overview.md` + `hap-plan.json`），支持多语言锁定与草案局部修订（`APPLY`/`CONSULT`/`CLARIFY`）。
  2. **Build 阶段** — 基于薄调度器 `scripts/build_runtime.py` 管理 DAG 依赖、分片并发派发独立 Subagent 与落盘验收，自动完成 Step 1 ~ Step 11 全套物理资产创建与构建总结。
- **场景 C：搭建合理性审查（Audit）** — 支持全量审查、定向审查与快速筛查；基于 90 项五维指标库（`audit/audit-checks.md`）与确定性评分引擎（`scripts/audit_calc.py`）输出客观诊断报告，并支持选定 Finding 后无缝衔接 Modify 修复。

## 核心亮点与高级能力

- 🧭 **12 域全覆盖存量修订与跨模块联动** — 内置 `modify/impact-map.md` 与 `modify/modify_guide.md`，对删改字段、状态合并、页面图表增量同步（`patch_custom_page_components`）、公开表单（`public_form`）和外部门户（`external_portal`）实现精准联动治理。
- 🛡️ **二元风险门禁与 14 类删除/关闭直通** — 对齐线上安全模型，常规可逆操作与用户点名的 14 类删除/关闭指令高效直通，破坏性变更（删表、删核心字段、删非空记录、改线上主干工作流）强制确认并支持一键备份。
- 📄 **Word / Excel / 系统 / 二维码 / 条形码打印模板** — 支持系统打印、二维码/条码打印，以及本地 Python 生成 `.docx` / `.xlsx`（Base64 / URL）上传绑定视图的全链路闭环。
- 🎨 **自定义字段（CustomField）与 AI 对话机器人（Chatbot）** — 支持自由字段前端组件注入，以及 Chatbot 外壳创建 + 底层 `ai_agent` 节点提示词、模型与工具授权两步闭环配置。
- ⚡ **渐进式上下文切片引擎** — `scripts/resolve_context.py` 支持按资产域、章节标题与构建步骤按需裁剪规范切片，避免单次塞入数千行无关文档。

## 目录结构

```text
hap-app-copilot/
├── SKILL.md                                    # 单一公开入口：环境能力探针校验 + 四路场景路由
├── README.md                                   # 项目说明与架构导览
├── workflows/                                  # 四大核心工作流
│   ├── plan.md                                 # Plan 阶段：交互式方案设计与草案联动修订
│   ├── build.md                                # Build 阶段：薄调度器并发物理搭建与总结
│   ├── modify.md                               # Modify 阶段：12 域渐进加载、风险门禁与回读工作流
│   └── audit.md                                # Audit 阶段：五维只读取证与质量审查工作流
├── plan/                                       # Plan 阶段专属规范
│   ├── 1a_plan_overview.md                     # 面向用户的方案概览模板与多语言规则
│   └── 1b_plan_schema.md                       # hap-plan.json 严格 Schema 与设计约束
├── build/                                      # Build 阶段上下文契约与原子步骤 SOP
│   ├── CONTEXT.md                              # Subagent 最小上下文协议
│   ├── OUTPUT_CONTRACT.md                      # 统一 JSON 结果回执契约
│   ├── PROGRESS.md                             # 用户侧阶段进度播报规范
│   └── steps/                                  # 12 个原子构建步骤 SOP（轻重分离，工作流设计创建二合一）
│       ├── 1_create_app.md                     # 主调度器内联：建应用壳、分组与页面空壳
│       ├── 1b_update_app_desc.md               # 主调度器内联：更新应用简介与 HTML 使用手册
│       ├── 2a_create_worksheets.md
│       ├── 2b_create_relations.md
│       ├── 3_create_actions_views_rules.md
│       ├── 4_create_chatbots.md                # 含 4a 创建外壳 + 4b 配置 ai_agent 并发布
│       ├── 5_create_sample_data.md
│       ├── 6_create_pages.md
│       ├── 7_sort_app_items.md                 # 主调度器内联：各分组内应用项智能排序
│       ├── 8_create_roles.md
│       ├── 10_create_workflows.md              # 单条系统工作流设计 + 创建 + 校验发布一体化
│       └── 11_create_action_workflows.md       # 单个动作工作流设计 + 注入 + 校验发布一体化
├── modify/                                     # Modify 专属治理体系与本地执行步骤
│   ├── impact-map.md                           # 跨模块连带影响地图与读前必查矩阵
│   ├── modify_guide.md                         # 12 大业务域修改手册与本地实操适配（第 1~13 章）
│   ├── safety-rules.md                         # 二元风险模型（low/high）、14 类删除直通与回读纪律
│   ├── execution-boundaries.md                 # 自动闭环、备份协同、人工引导与硬阻断边界
│   └── steps/
│       └── print_template.md                   # Word/Excel 本地制作、HAP 占位符与交付检查
├── audit/                                      # Audit 专属指标与取证规范
│   ├── audit-checks.md                         # 90 项五维质量审查指标库与评分模型 (CHK-*)
│   └── collection-guide.md                     # MCP 只读取证范围、预算上限与停止条件
├── references/                                 # 19 份 HAP 设计指南与领域规范
│   ├── hap-app-design-guide.md                 # 应用建模、导航、门户与架构设计总纲
│   ├── hap-workflow-design-guide.md            # 工作流联动设计与防死循环指南
│   ├── hap-chart-design-guide.md               # 统计图类型选型、xaxes/yaxisList 与配色规范
│   ├── hap-icon-palette.md                     # 受控图标库与主题色板
│   ├── hap-sample-data-spec.md                 # 仿真示例数据与静态图片资源规范
│   ├── hap-domain-app-spec.md                  # 应用基础属性、导航分组与应用项管理规范
│   ├── hap-domain-worksheet-spec.md            # 工作表、字段类型、排版、表单设置与筛选器规范
│   ├── hap-domain-view-spec.md                 # 8 大视图类型、筛选排序与快捷操作规范
│   ├── hap-domain-custom-action-spec.md        # 自定义动作按钮、交互输入与工作流绑定规范
│   ├── hap-domain-business-rule-spec.md        # 业务规则条件语法与前后端校验动作规范
│   ├── hap-domain-workflow-spec.md             # 工作流与审批流程节点 Schema 及发布规范
│   ├── hap-domain-custom-page-spec.md          # 自定义页面 48 栅格布局与增量组件同步规范
│   ├── hap-domain-worksheet-chart-spec.md      # 工作表统计面板图表创建、修改与排序规范
│   ├── hap-domain-role-spec.md                 # 角色权限模型、数据范围与字段级权限规范
│   ├── hap-domain-chatbot-spec.md              # AI 对话机器人与 ai_agent 节点配置规范
│   ├── hap-domain-external-portal-spec.md      # 外部门户状态、注册登录与外部角色分段配置规范
│   ├── hap-domain-worksheet-index-spec.md      # 工作表物理索引与唯一索引性能规范
│   ├── hap-domain-custom-field-spec.md         # 自定义字段（CustomField）前端组件注入规范
│   └── hap-domain-record-data-spec.md          # 业务记录查询、透视统计与受控批量写改规范
└── scripts/                                    # 5 个核心运行时脚本
    ├── resolve_context.py                      # Modify/Build/Audit 渐进上下文切片与章节按需提取器
    ├── build_runtime.py                        # Build DAG 状态机、分片任务编排与输出契约校验器
    ├── merge_worksheet_context.py              # 合并生成全保真 worksheetContext.json（含选项 key）
    ├── audit_calc.py                           # Audit 覆盖率、证据链校验与确定性评分引擎
    └── scan_apps.py                            # 扫描工作区已有应用工程状态
```

## 核心职责边界

| 模块 / 文件 | 唯一职责 |
|---|---|
| `SKILL.md` | 不限服务名的 HAP MCP 识别、`>=170` 全量工具硬门禁、URL 一键直达与五路场景路由 |
| `workflows/plan.md` + `plan/` | 交互式方案设计、语言锁定与草案阶段联动修改（`APPLY`/`CONSULT`/`CLARIFY`/`CREATE`） |
| `workflows/build.md` + `build/` | 轻重分离（1/1b/7 内联 + 重资产独立 Subagent 并发 + 工作流设计创建二合一）物理搭建与总结 |
| `workflows/modify.md` + `modify/` | 存量应用 12 大业务域实时摸底、影响地图联动、二元风险确认、最小写入与回读验证 |
| `workflows/audit.md` + `audit/` | 90 项五维只读取证、预算控制、确定性计分与审查后修复衔接 |
| `references/hap-*.md` | HAP 各领域底层参数结构、约束红线与标准范例 |
| `scripts/resolve_context.py` | 按 `--mode modify/build/audit` 或 `--file ... --section ...` 输出最小必要规范切片 |

## 来源说明

本 Skill 的设计指南、领域规范及部分构建/修订流程参考明道云 `MDAgentService`，并适配本地 Agent 与 HAP MCP 的使用方式。相关文件中的 `SOURCE` 注释用于标识参考来源。

## 许可证

MIT
