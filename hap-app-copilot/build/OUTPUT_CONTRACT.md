# HAP Build 输出与统一任务回执契约 (OUTPUT_CONTRACT)

本文档定义薄控制面架构下的**单写入者原则**、**最小任务上下文切片**、**统一任务回执规范**与**阶段报告契约**。

---

## 一、 运行时目录与读写隔离

所有构建运行态文件收敛在 `{PROJECT_ROOT}/.hap-copilot/apps/{appName}/.build/` 下（自动受 `.hap-copilot/.gitignore` 保护，不污染宿主代码仓库）：
- `run.json`：运行批次配置（由 `build_runtime.py init` 生成）
- `dispatch-registry.json`：子代理派发登记账本（由 `build_runtime.py dispatched` 维护）
- `task-manifest.json`：当前阶段任务状态摘要（由 `build_runtime.py prepare` 维护）
- `task-context/{taskId}.json`：Subagent 只读专属输入切片
- `task-bundles/{taskId}*.md`：由 `prepare` 自动预编译的「SOP + 必读领域规范全文 + 任务切片」一体包（按 `<= 41KB / <= 700 行` 自动分卷，供 Subagent 首轮零截断一次读全，物理杜绝漏读规范）
- `receipts/{taskId}.json`：Subagent 独占写入回执
- `artifacts/worksheet-{worksheetId}.json`：Step 3 单表完整字段分片
- `phase-report.json`：阶段门禁报告（由 `build_runtime.py finalize` 生成）

---

## 二、 最小任务上下文切片规范 (`Task Context Schema`)

由 `scripts/build_runtime.py prepare` 自动生成至 `.build/task-context/{taskId}.json`：

```json
{
  "taskId": "step3-view-act-订单",
  "taskName": "[Step 3] 单表全要素配置 - 订单",
  "runId": "build-20261116-001",
  "step": "3",
  "target": { "type": "worksheet", "id": "ws_order_123", "name": "订单" },
  "mcpServer": "hap_meihua_mcp",
  "stepFile": "/abs/path/build/steps/3_create_actions_views_rules.md",
  "references": [
    "/abs/path/references/hap-domain-view-spec.md",
    "/abs/path/references/hap-domain-custom-action-spec.md",
    "/abs/path/references/hap-domain-business-rule-spec.md"
  ],
  "allowedTools": [
    "get_worksheet_structure",
    "create_custom_actions",
    "create_view",
    "get_view_structure",
    "update_view",
    "create_business_rule"
  ],
  "receiptPath": "/abs/path/.build/receipts/step3-view-act-订单.json",
  "planSlice": {},
  "contextSlice": {},
  "worksheetContextSlice": {}
}
```

---

## 三、 统一 Subagent 任务回执规范 (`Unified Task Receipt Schema`)

所有并发 Subagent 任务完成后，必须将符合以下结构的 JSON 写入 `receiptPath`：

```json
{
  "taskId": "step3-view-act-订单",
  "runId": "build-20261116-001",
  "executor": {
    "kind": "subagent",
    "agentId": "subagent-conv-id"
  },
  "step": "3",
  "target": { "type": "worksheet", "id": "ws_order_123", "name": "订单" },
  "status": "succeeded",
  "outputs": {},
  "verification": {
    "passed": true,
    "evidence": ["具体工具执行成功或回读核验依据"]
  },
  "issues": []
}
```

---

## 四、 全步骤执行与 `TaskId` 速查表

| 步骤 | 处理粒度与执行方式 | 标准 `taskId` 格式 | 状态/回执落盘位置 |
| :--- | :--- | :--- | :--- |
| **Step 1 + 1b** | 应用、分组、页面空壳与使用手册（主调度器内联） | _(内联执行)_ | 写入 `hap-context.json` (`progress="app_created"`) |
| **Step 2a** | 单表创建与基础字段（Subagent 并发） | `step2a-ws-{worksheetName}` | `.build/receipts/step2a-ws-{worksheetName}.json` |
| **Step 2b** | 单表关联与衍生回填（Subagent 并发） | `step2b-rel-{worksheetName}` | `.build/receipts/step2b-rel-{worksheetName}.json` |
| **Step 3** | 单表结构采集+动作+视图+规则（Subagent 并发） | `step3-view-act-{worksheetName}` | `.build/receipts/step3-view-act-{worksheetName}.json` |
| **Step 4a** | AI 智能助手实体创建（Subagent） | `step4-chatbot` | `.build/receipts/step4-chatbot.json` |
| **Step 4b** | 单助手 `ai_agent` 节点配置发布（Subagent 并发） | `step4b-chatbot-config-{botName}` | `.build/receipts/step4b-chatbot-config-{botName}.json` |
| **Step 5** | 拓扑感知示例数据（后台 Subagent） | `step5-sample-data` | `.build/receipts/step5-sample-data.json` |
| **Step 6** | 单自定义页面组装与校正（Subagent 并发） | `step6-page-{pageName}` | `.build/receipts/step6-page-{pageName}.json` |
| **Step 7** | 分组内应用项智能排序（主调度器内联） | _(内联执行)_ | 写入 `hap-context.json` (`itemsSorted=true`) |
| **Step 8** | 单角色创建与精细权限（Subagent 并发） | `step8-role-{roleName}` | `.build/receipts/step8-role-{roleName}.json` |
| **Step 10** | 单条系统工作流设计+创建+发布（Subagent 并发） | `step10-sys-wf-{workflowName}` | `.build/receipts/step10-sys-wf-{workflowName}.json` |
| **Step 11** | 单个动作工作流设计+注入+发布（Subagent 并发） | `step11-act-wf-{ws}_{actionName}` | `.build/receipts/step11-act-wf-{ws}_{actionName}.json` |
