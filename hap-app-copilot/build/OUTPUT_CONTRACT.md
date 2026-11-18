# HAP Build 输出与统一任务回执契约 (OUTPUT_CONTRACT)

本文档定义构建任务的**原始资料入口**、**上下文摘要**、**统一任务回执规范**与**阶段报告契约**。

---

## 一、 运行时目录与读写隔离

所有构建运行态文件收敛在 `{PROJECT_ROOT}/.hap-copilot/apps/{appName}/.build/` 下（自动受 `.hap-copilot/.gitignore` 保护，不污染宿主代码仓库）：
- `run.json`：运行批次配置（由 `build_runtime.py init` 生成）
- `dispatch-registry.json`：子代理派发登记账本（由 `build_runtime.py dispatched` 维护）
- `task-manifest.json`：当前阶段任务状态摘要（由 `build_runtime.py prepare` 维护）
- `task-context/{taskId}.json`：单任务结构化上下文切片（含 `planSlice`、`contextSlice`、`worksheetContextSlice` 与 `sourceFiles`）
- `task-bundles/{taskId}*.md`：预编译任务执行包（自动内联本步 SOP、`taskContext` 与必读领域规范全文，按 `< 700` 行且 `< 41,000` 字节无损分卷，供 Subagent 首轮一次读齐）
- `receipts/{taskId}.json`：Subagent 独占写入回执
- `artifacts/worksheet-{worksheetId}.json`：Step 3 单表完整字段分片
- `phase-report.json`：阶段门禁报告（由 `build_runtime.py finalize` 生成）

---

## 二、 任务上下文与原始资料 (`Task Context Schema`)

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
  "hostAdapter": "/abs/path/HOST_ADAPTER.md",
  "sourceFiles": {
    "plan": "/abs/app/hap-plan.json",
    "context": "/abs/app/hap-context.json",
    "worksheetContext": "/abs/app/worksheetContext.json",
    "receipts": "/abs/app/.build/receipts",
    "artifacts": "/abs/app/.build/artifacts"
  },
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

`allowedTools` 的含义见 [宿主适配](../HOST_ADAPTER.md)：列出该原子步骤的业务写入白名单，执行者不得越权调用其他步骤的写入工具，异常排查时可辅以只读查询工具。

`bundleFiles` 指向 `.build/task-bundles/{taskId}*.md` 预编译分卷（内联 `stepFile`、`taskContext` 及必读 `references` 正文，单卷 `< 700` 行且 `< 41,000` 字节），Subagent 首轮必须完整读齐。工作表任务的 `planSlice.worksheet` 保留本表完整设计；`sourceFiles` 仅在异常恢复或核对跨表补充细节时按需读取。

失败任务再次准备时，`readyTasks` 中标记 `resume: true`，已有失败回执通过 `previousReceipt` 传入；容量等待任务默认保留在 `readyTasks`。归属、格式或成功证据缺失的异常回执单独列入 `blockedTasks`（`taskId`、`receiptPath`、`reason`），主调度器核实线上状态后可补齐合法回执或执行 `reset-task` 归档损坏回执并恢复派发。`prepare.canAdvance` 表示当前阶段所有阻塞型任务（`isBackground: true` 的后台任务 `Step 5` 除外）均已有合法成功回执，全局状态仍须经 `finalize` 校验后由 `advance` 推进。

`finalize` 成功生成报告即正常退出；`canAdvance: false` 表示阶段尚未完成，`nextAction: "prepare"` 提示继续修复未完成任务。`advance` 未推进时返回 `advanced: false` 与下一步指引，具体调度见 [Build 工作流](../workflows/build.md)。

## 三、 统一 Subagent 任务回执规范 (`Unified Task Receipt Schema`)

所有并发 Subagent 任务完成后，必须将符合以下结构的 JSON 写入 `receiptPath`。`runId` 必填且须与当前运行一致，`executor.kind` 为 `"subagent"`（或主调度器在线上返工修复并核验通过后通过 `resolve-task` 归并生成的 `"reconciled"`）且 `executor.agentId` 非空。

- **完建优先判定准则（对象落库即 `succeeded`）**：每个子任务仅验收自身步骤职责内的物理对象是否成功创建并取得真实 ID（工作流因外部人员缺失按规保存为 `outputs.status: "draft"` 同样属于合法完成）。平台原生机制的近似表达（如角色 `recordDataScope` 按拥有者判定、不支持配置关联扩展权限）或需人工补充的细节一律记录在 `issues` 数组中供终态汇总说明，**严禁超前验收下游未执行阶段，也严禁将已成功落库的对象标为 `"failed"` 阻断后续流水线**；同时不得擅自更改规划的对象/字段类型以免破坏下游依赖。
- **异常与返工归并**：仅当核心接口调用失败且未能取得目标对象真实 ID 时才标为 `"failed"`；返工修复完成后必须用 `resolve-task` 同步回收失败回执并推进 `finalize` / `advance`。

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

表中为无冲突时沿用的编号格式。发生名称规范化冲突时，运行时按原始对象身份添加稳定后缀；执行者只复制 `prepare` 返回的 `taskId`、`taskContext`、`receiptPath`，不得按表手拼路径。已有歧义旧产物时先核对，不覆盖或重放。

| 步骤 | 处理粒度与执行方式 | 标准 `taskId` 格式 | 状态/回执落盘位置 |
| :--- | :--- | :--- | :--- |
| **Step 1 + 1b** | 应用、分组、页面空壳与使用手册（主调度器内联） | _(内联执行)_ | 写入 `hap-context.json` (`progress="app_created"`) |
| **Step 2a** | 单表创建与基础字段（Subagent 并发） | `step2a-ws-{worksheetName}` | `.build/receipts/step2a-ws-{worksheetName}.json` |
| **Step 2b** | 按关联组回填关联与衍生字段（Subagent 按组并发，每组 ≤5 表） | `step2b-rel-group-{N}` | `.build/receipts/step2b-rel-group-{N}.json` |
| **Step 3** | 单表结构采集+动作+视图+规则（Subagent 并发） | `step3-view-act-{worksheetName}` | `.build/receipts/step3-view-act-{worksheetName}.json` |
| **Step 4a** | AI 智能助手实体创建（Subagent） | `step4-chatbot` | `.build/receipts/step4-chatbot.json` |
| **Step 4b** | 单助手 `ai_agent` 节点配置发布（Subagent 并发） | `step4b-chatbot-config-{botName}` | `.build/receipts/step4b-chatbot-config-{botName}.json` |
| **Step 5** | 拓扑感知示例数据（后台 Subagent） | `step5-sample-data` | `.build/receipts/step5-sample-data.json` |
| **Step 6** | 单自定义页面组装与校正（Subagent 并发） | `step6-page-{pageName}` | `.build/receipts/step6-page-{pageName}.json` |
| **Step 7** | 分组内应用项智能排序（主调度器内联） | _(内联执行)_ | 写入 `hap-context.json` (`itemsSorted=true`) |
| **Step 8** | 单角色创建与精细权限（Subagent 并发） | `step8-role-{roleName}` | `.build/receipts/step8-role-{roleName}.json` |
| **Step 10** | 单条系统工作流设计+创建+发布（Subagent 并发） | `step10-sys-wf-{workflowName}` | `.build/receipts/step10-sys-wf-{workflowName}.json` |
| **Step 11** | 单个动作工作流设计+注入+发布（Subagent 并发） | `step11-act-wf-{ws}_{actionName}` | `.build/receipts/step11-act-wf-{ws}_{actionName}.json` |
