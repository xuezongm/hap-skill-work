# HAP Build 输出与统一任务回执契约 (OUTPUT_CONTRACT)

本文档定义 HAP App Builder 报告驱动型薄控制面架构下的**单写入者原则 (Single-Writer Principle)**、**最小任务上下文切片 (Task Context Slicing)**、**统一任务回执规范 (Unified Task Receipt)** 与 **阶段报告契约**。

---

## 一、 运行时目录职责与权限矩阵

构建流水线所有状态收敛在 `{PROJECT_ROOT}/apps/{appName}/.build/` 目录下：

```text
.build/
├── run.json               # 运行策略与配置 (由 build_runtime init 初始化)
├── task-manifest.json     # 任务清单与状态 (由 build_runtime prepare 维护)
├── task-context/          # 任务最小切片上下文 (Subagent 专属输入)
│   └── {taskId}.json
├── receipts/              # 独占回执目录 (由各 Subagent 写入)
│   └── {taskId}.json
├── artifacts/             # 大型产物目录 (如 worksheet 结构分片)
└── phase-report.json      # 阶段权威报告 (由 build_runtime finalize 生成)
```

### 1. 读写权限隔离矩阵
- **Subagent 权限**：
  - **只读**：自己的任务切片 `.build/task-context/{taskId}.json` 与指定步骤指南、平台规格；
  - **独占写**：属于自己的回执 `.build/receipts/{taskId}.json` 与产物 `.build/artifacts/`；
  - **🚫 严禁修改**：`hap-context.json`、`hap-plan.json`、`progress` 或其他任务的文件。
- **主调度器权限**：
  - **纯控制面**：只调用 `build_runtime.py` 指令集与 Subagent 派发工具；
  - **🚫 严禁操作**：禁止调用任何业务写入 MCP 工具，禁止手工合并 ID 字典。
- **`build_runtime.py` 独占写入**：
  - 独占更新 `hap-context.json`、`hap-plan.json` 与推进 `progress`。

---

## 二、 最小任务上下文切片规范 (Task Context Schema)

由 `build_runtime.py prepare` 自动生成至 `.build/task-context/{taskId}.json`：

```json
{
  "taskId": "step3-view-act-订单",
  "taskName": "[Step 3] 单表全要素配置 - 订单",
  "runId": "build-20260821-001",
  "step": "3",
  "target": { "type": "worksheet", "id": "ws_order_123", "name": "订单" },
  "mcpServer": "hap_sandbox_mcp",
  "stepFile": "/absolute/path/build/steps/3_create_actions_views_rules.md",
  "references": [
    "/absolute/path/references/spec-actions-views.md"
  ],
  "receiptPath": "/absolute/path/.build/receipts/step3-view-act-订单.json",
  "planSlice": {
    "worksheetName": "订单",
    "businessRules": [ ...当前表的业务规则... ],
    "views": [ ...当前表的规划视图... ],
    "customActions": [ ...当前表的规划动作... ]
  },
  "contextSlice": {
    "appId": "app_xxxxxx",
    "worksheetId": "ws_order_123",
    "worksheetIdByName": { "订单": "ws_order_123" }
  }
}
```

---

## 三、 统一 Subagent 任务回执规范 (Unified Task Receipt Schema)

> [!IMPORTANT]
> **所有 Step 1～11 的 Subagent 任务，必须在执行完成且回读验证通过后，将标准回执写入 `{PROJECT_ROOT}/apps/{appName}/.build/receipts/{taskId}.json`。**

```json
{
  "taskId": "step4-view-act-订单",
  "executor": {
    "kind": "subagent",
    "agentId": "5fabe315-subagent-001"
  },
  "step": "4",
  "target": {
    "type": "worksheet",
    "id": "674046935a63abb6377d23a1",
    "name": "订单"
  },
  "status": "succeeded",
  "attempt": 1,
  "remoteChanges": [
    { "action": "create_view", "name": "待处理订单", "id": "view_123" },
    { "action": "create_custom_action", "name": "发货", "id": "act_456" }
  ],
  "outputs": {
    "viewIdByName": { "订单/待处理订单": "view_123" },
    "actionIdByName": { "发货": "act_456" }
  },
  "verification": {
    "passed": true,
    "evidence": [
      "调用 get_view_structure 确认待处理订单视图已生效",
      "调用 get_custom_action_list 确认发货按钮存在"
    ]
  },
  "issues": []
}
```

---

## 四、 阶段权威报告规范 (Phase Report Schema)

由 `build_runtime.py finalize` 自动生成至 `.build/phase-report.json`（主调度器唯一读取的业务结论）：

```json
{
  "schemaVersion": "1.0",
  "runId": "build-20260821-001",
  "phase": "fields_refreshed",
  "progressBefore": "fields_refreshed",
  "taskSummary": {
    "expected": 15,
    "succeeded": 15,
    "failed": 0,
    "running": 0,
    "pendingCapacity": 0,
    "retryPending": 0
  },
  "execution": {
    "mode": "subagent_required",
    "subagentExecutionVerified": true,
    "inlineExecutionDetected": false
  },
  "outputs": {
    "viewsCreated": 24,
    "actionsCreated": 6,
    "chatbotsCreated": 1,
    "sampleDataCreated": true
  },
  "validation": {
    "passed": true,
    "errors": [],
    "warnings": []
  },
  "nextProgress": "page_shells_created",
  "canAdvance": true
}
```

---

## 五、 全步骤 TaskId 命名规范速查表

| 步骤 | 处理对象 | 标准 TaskId 格式 | 存放路径 |
| :--- | :--- | :--- | :--- |
| **Step 1** | 应用外壳与分组 | _(调度器内联初始化)_ | 写入 `hap-context.json` (progress=`app_created`) |
| **Step 1b** | 应用描述与手册 | `step1b-app-desc` | `.build/receipts/step1b-app-desc.json` |
| **Step 2a** | 单表创建与基础字段 | `step2a-ws-{worksheetName}` | `.build/receipts/step2a-ws-{worksheetName}.json` |
| **Step 2b** | 跨表关联与衍生字段 | `step2b-rel-{worksheetName}` | `.build/receipts/step2b-rel-{worksheetName}.json` |
| **Step 3** | 单表全要素综合配置一体化<br>(结构采集+规则+动作+视图) | `step3-view-act-{worksheetName}` | `.build/receipts/step3-view-act-{worksheetName}.json`<br>`.build/artifacts/worksheet-{worksheetId}.json` |
| **Step 4** | AI 智能助手 | `step4-chatbot` | `.build/receipts/step4-chatbot.json` |
| **Step 5** | 示例数据填报 | `step5-sample-data` | `.build/receipts/step5-sample-data.json` |
| **Step 6** | 自定义页面组件 | `step6-page-{pageName}` | `.build/receipts/step6-page-{pageName}.json` |
| **Step 7** | 应用项智能排序 | `step7-sort-items` | `.build/receipts/step7-sort-items.json` |
| **Step 8** | 角色创建与权限 | `step8-role-{roleName}` | `.build/receipts/step8-role-{roleName}.json` |
| **Step 9** | 系统流/动作流设计 | `step9-design-system`<br>`step9-design-action` | `.build/receipts/step9-design-system.json`<br>`.build/receipts/step9-design-action.json` |
| **Step 10** | 系统工作流发布 | `step10-sys-wf-{workflowName}` | `.build/receipts/step10-sys-wf-{workflowName}.json` |
| **Step 11** | 动作工作流发布 | `step11-act-wf-{actionName}` | `.build/receipts/step11-act-wf-{actionName}.json` |
