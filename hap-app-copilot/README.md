# HAP App Copilot（明道云应用助手）

基于 HAP（明道云）MCP 工具链的一站式应用全生命周期智能助手 Skill（覆盖设计、搭建、修改、审查与修复）。

## 功能概述

本 Skill 支持三大核心场景：

- **场景 A：修改已有应用 (Modify)** — 对线上已有应用进行精准、安全的增量修改与重构（加字段、改属性、调视图、改规则、改工作流等），通过 MCP 实时查询线上现状，将兼容变化合并为最少写入批次并逐批回读核对。
- **场景 B：从零新建应用 (Plan & Build)** — 从**业务方案设计（Plan）**到**物理搭建（Build）**的全自动流水线。
  1. **Plan 阶段** — 根据用户需求生成结构化的应用设计方案（工作表、字段、关联、视图、工作流等）。
  2. **Build 阶段** — 读取方案，通过 MCP 工具调用 HAP API 自动完成物理搭建。
- **场景 C：搭建合理性审查 (Audit)** — 支持全量审查、定向审查和快速筛查；全量审查输出五维评分，选定问题后可进入 Modify 修复模式。

## 核心亮点与高级能力

除了常规的数据建模与标准流程搭建，本 Skill 深度整合了以下高级能力：

- 🎨 **自定义字段与交互组件（CustomField / 自由字段）** — 具备直接编写并注入 React/JS 前端代码的能力，支持动态签名板、复合交互卡片、外部 SDK 挂载等高级交互组件定制。
- 📄 **Word / Excel 打印模板自动生成** — 能够分析主表与关联明细结构，自动生成符合 HAP 语法规范的 Word/Excel 打印与导出模板（如销售出库单、劳动合同、报价单等）。
- ⚡ **工作表物理索引与大表加速** — 针对高频过滤、排序和检索字段，自动设计并创建底层物理索引，消除百万级单表查询卡顿。
- 🛡️ **外科手术式在线安全修改** — 线上实时基线对齐 + 最小兼容写入合并 + 写后自动回读断言，严格防范破坏存量数据与业务中断。
- 🔍 **90 项指标五维合理性审查** — 覆盖结构健康、业务完整、用户体验、性能容量与安全维护，体检后支持一键闭环修复。

## 目录结构

```text
hap-app-copilot/
├── SKILL.md                  # 单一公开 Skill 入口：公共前置检查 + 场景路由
├── workflows/                # 核心执行工作流
│   ├── plan.md               # 场景 B - Plan 阶段：方案设计工作流
│   ├── build.md              # 场景 B - Build 阶段：物理搭建调度工作流
│   ├── modify.md             # 场景 A：已有应用修改唯一主工作流
│   └── audit.md              # 场景 C：搭建合理性审查工作流
├── modify/                   # Modify 专属规则与实战指南
│   ├── modify_guide.md       # 各类对象的修改规则与高频实战案例（按需查阅）
│   ├── safety-rules.md       # Modify 安全底线、阻断条件与验证证据
│   ├── execution-boundaries.md # 复杂操作的自动、协同、人工与阻断边界
├── references/               # 全生命周期共享的平台规范库
│   ├── spec-worksheets.md    # 工作表、字段类型、行列排版与表单高级设置
│   ├── spec-business-rules.md# 业务规则条件语法与动作规范
│   ├── spec-actions-views.md # 视图类型、过滤条件与自定义动作
│   ├── spec-print-templates.md # Word/Excel 打印模板与适用范围规范
│   ├── spec-pages-charts.md  # 自定义页面 48 栅格与统计图表规范
│   ├── spec-workflows.md     # 工作流节点 Schema 与生命周期
│   ├── spec-roles-permissions.md # 角色权限模型与人工待办标准
│   ├── spec-chatbots.md      # AI 对话助手（Chatbot）配置规范
│   ├── spec-worksheet-indexes.md # 工作表物理索引设计与大表加速规范
│   ├── spec-custom-fields.md # 自定义字段与自由字段规范
│   ├── spec-sample-data.md   # 仿真数据规则
│   ├── resource-sample-images.md # 仿真静态图片资源库
│   ├── guide-design.md       # 通用业务建模与设计哲学
│   ├── guide-workflows.md    # 工作流业务联动与分析法
│   └── spec-app-styles.md    # 应用视觉主题、导航与受控图标库
├── audit/                    # Audit 专属材料
│   ├── audit-checks.md       # 五维审查指标库与评分模型 (CHK-*)
│   └── collection-guide.md   # MCP 证据范围、即时分析、停止条件与按需归档
├── plan/                     # Plan 专属模板与 Schema
│   ├── 1a_plan_overview.md   # 方案概览模板
│   └── 1b_plan_schema.md     # 方案 Schema 定义
├── build/                    # Build 专属材料与原子步骤 SOP
│   ├── CONTEXT.md            # 构建上下文
│   ├── PROGRESS.md           # 进度追踪
│   ├── OUTPUT_CONTRACT.md    # 输出契约
│   └── steps/                # 原子搭建步骤 SOP (1~11)
└── scripts/                  # 确定性自动化脚本库
    ├── resolve_context.py    # 按资产、复杂场景或 Audit 检查项渐进加载最小上下文
    ├── audit_calc.py         # Audit 结果覆盖校验、来源校验与确定性评分 (V2)
    ├── build_runtime.py      # Build 阶段任务调度与校验引擎
    ├── merge_worksheet_context.py # 合并生成 worksheetContext.json
    └── scan_apps.py          # 扫描已有应用资产
```

## 核心设计决策与职责边界

| 文件 | 唯一职责 |
|---|---|
| `SKILL.md` | 判断是否进入 Modify、Build、Audit，处理公共前置检查与路由 |
| `workflows/modify.md` | 修改已有应用的唯一完整人类执行工作流（步骤、门禁、断言与交付） |
| `modify/modify_guide.md` | 制定方案前按对象查阅的关联影响、修改、验证规则与实战案例 |
| `modify/safety-rules.md` | Modify 不可绕过的安全底线、阻断条件与通过证据（MOD-*） |
| `modify/execution-boundaries.md` | 复杂和高风险操作的自动、协同、人工与阻断条件；不重复维护 MCP 工具清单 |
| `references/spec-*.md` | HAP 底层各资产参数结构与物理规范 |
| `scripts/resolve_context.py` | 按目标资产、复杂场景或 Audit 检查项输出最小参考正文包与清单 |

## 使用方式

本 Skill 配合 Antigravity IDE 使用，**零配置开箱即用**：

1. 将本目录放置在 Agent 的 skills 搜索路径下（如 `~/.gemini/config/skills/hap-app-copilot`）
2. 在平台配置好明道云 MCP Server（如 `hap_sandbox_mcp` 或 `hap_meihua_mcp`，需授权全部工具）
3. 在对话中描述业务需求即可自动触发：
   - **新建应用**：“帮我搭建一个图书借阅管理应用”
   - **创建打印模板**：“为销售订单表生成一个精美的打印模板，尽显国际化大厂风格”
   - **注入自定义组件**：“在工单表新增一个 SLA 履约倒计时与超时预警卡片组件”
   - **修改应用**：“给报销单加一个加急支付字段”、“将待初审和待复审状态合并为待审批”
   - **审查应用**：“帮我检查一下这个应用的搭建质量并修复发现的问题”

## 许可证

MIT
