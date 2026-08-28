# Step 10: 部署系统自动化工作流 SOP (10_create_workflows)

本文档是 Build 阶段 **Step 10（按工作流并发创建并发布系统工作流）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [单工作流执行 SOP 流水线](#三-单工作流执行-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与错误自愈](#五-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：子代理按系统工作流并发；
- **任务目标**：根据 `hap-plan.json` 中 Step 9 设计好的系统工作流方案，创建工作流实体、批量注入节点连线、校验并正式发布启用；
- **核心输入契约**：
  - `hap-plan.json`：当前系统工作流的设计方案（`workflows.system`）；
  - `worksheetContext.json`：相关工作表的真实字段结构与 controlId 映射；
  - `hap-context.json`：`appId`。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-workflows.md](../../references/spec-workflows.md)（系统工作流创建、触发器、节点 Schema 与发布时序）

---

## 三、 单工作流执行 SOP 流水线

### 1. 创建工作流实体与获取触发节点
调用 `create_process` 创建空白系统工作流（`description` 必填）：
```json
{
  "appId": "<appId>",
  "name": "新订单自动扣减库存并通知",
  "description": "当订单状态变更为已支付时，自动扣减关联商品库存并推送发货提醒",
  "type": 1
}
```
- 直接从 `create_process` 返回值提取 `triggerAlias` / `nodeId` 作为后续所有节点引用触发记录的标识。

### 2. 批量注入业务节点 (batch_create_process_nodes)
按照 `references/spec-workflows.md` 规范，调用 `batch_create_process_nodes` 注入节点：
- 子流程（`sub_process`）和审批块（`approval_block`）按规范走两阶段创建（先建空壳获取内部 `processId`，再向内部注入节点）；
- 给选项字段赋值必须使用选项真实 `key`。

### 3. 校验并发布启用 (validate & publish)
- ⚠️ **含子流程/审批块时必须先发布内部 processId，最后发布主流程**（防 `NodeAppIsNull` 致命错误）；
- 调用 `publish_process` 将工作流置为正式发布状态。

---

## 四、 输出交付物契约 (.build)

执行成功后，将发布结果与标准回执写入独立任务回执文件：
- **文件路径**：`.build/receipts/step10-sys-wf-{workflowName}.json`
- **内容格式**：
```json
{
  "taskId": "step10-sys-wf-{workflowName}",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "10",
  "target": { "type": "workflow", "name": "{workflowName}" },
  "status": "succeeded",
  "outputs": {
    "workflowName": "{workflowName}",
    "processId": "proc_sys_123",
    "published": true
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 publish_process 成功校验并发布工作流 proc_sys_123"]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与错误自愈

1. **断言 1 (发布成功)**：`publish_process` 返回成功（或已成功发布）；
2. **断言 2 (回执通知)**：将包含 `workflowName`、`processId` 与 `published: true` 的标准回执写入 `.build/receipts/step10-sys-wf-{workflowName}.json`；
3. **自愈机制**：若 `validate_process` 报错提示连线异常，根据返回的错误节点 ID 自动修正 nextNodeId 并重试。
