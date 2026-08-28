# Step 9: 自动化工作流方案设计 SOP (9_design_workflows)

本文档是 Build 阶段 **Step 9（按类型并发设计系统工作流与自定义动作工作流方案）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [设计 SOP 流水线](#三-设计-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与自愈](#五-⛔-验证断言与自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：子代理按工作流类型并发（`system` 系统流 / `action` 动作流）；
- **任务目标**：根据业务意图线索（`intentHints`）与真实工作表结构（`worksheetContext`），设计出完整、严谨、带节点连线（`nodes`）的工作流方案，写出到临时分片文件供主调度器合并；
- **核心输入契约**：
  - `targetWorkflowType`：`system`（系统工作流）或 `action`（动作工作流）；
  - `worksheetContext`：来自 `worksheetContext.json` 的全表真实结构与字段映射；
  - `viewIdByName`：视图名称与 ID 映射（来自 `hap-context.json`）；
  - `roles`：角色列表（来自 `hap-plan.json` 的 `roles[]`）；
  - `workflows`（系统流列表）或 `customActionWorkflows`（动作流列表，已有 `processId`）。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (业务设计指南)**：
> 📖 [references/guide-workflows.md](../../references/guide-workflows.md)（7 维业务分析法、业务联动套路、审批判定与分支 paths ≥ 2 规则）

---

## 三、 设计 SOP 流水线

1. **逐条工作流运行 7 维分析**：
   - 触发时机 ➔ 主表更新 ➔ 关联表联动（逐表扫描） ➔ 是否审批 ➔ 分支细化 ➔ 通知策略 ➔ 异常处理；
2. **构建完整 nodes 节点方案**：
   - 先安排查询节点（`get_single`/`get_multiple`），再安排更新节点（`update_record`）；
   - 分支节点 paths 数组必须 ≥ 2 条；
   - 动作流若输入中包含 `processId`，在方案中原样透传。

---

## 四、 输出交付物契约 (.build)

> [!CAUTION]
> **禁止直接修改 `hap-plan.json`**，必须将方案与回执输出到对应的标准任务回执文件中：

- **若 `targetWorkflowType == 'system'`**：
  - **文件路径**：`.build/receipts/step9-design-system.json`
  - **内容格式**：
  ```json
  {
    "taskId": "step9-design-system",
    "executor": { "kind": "subagent", "agentId": "{agentId}" },
    "step": "9",
    "target": { "type": "workflow_design", "name": "system" },
    "status": "succeeded",
    "outputs": {
      "workflows": [ ...带有完整 nodes 数组的系统工作流方案... ]
    },
    "verification": {
      "passed": true,
      "evidence": ["每条系统工作流 nodes 数组均非空且包含合法触发器与执行节点"]
    },
    "issues": []
  }
  ```
- **若 `targetWorkflowType == 'action'`**：
  - **文件路径**：`.build/receipts/step9-design-action.json`
  - **内容格式**：
  ```json
  {
    "taskId": "step9-design-action",
    "executor": { "kind": "subagent", "agentId": "{agentId}" },
    "step": "9",
    "target": { "type": "workflow_design", "name": "action" },
    "status": "succeeded",
    "outputs": {
      "customActionWorkflows": [ ...带有完整 nodes 数组的动作工作流方案... ]
    },
    "verification": {
      "passed": true,
      "evidence": ["每条动作工作流 nodes 数组均非空且包含合法执行节点"]
    },
    "issues": []
  }
  ```

---

## 五、 ⛔ 验证断言与自愈

1. **断言 1 (回执与方案生成)**：检查目标对应的 `.build/receipts/step9-design-system.json` 或 `.build/receipts/step9-design-action.json` 是否成功写入且 status 为 succeeded；
2. **断言 2 (nodes 非空且完整)**：检查方案中该类型的**每一条工作流**的 `nodes` 数组均非空且节点数 ≥ 1；
3. **自愈机制**：若某工作流 nodes 为空，重新加载 `references/spec-workflows.md` 补齐节点。
