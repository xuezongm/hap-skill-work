# Step 11: 部署动作工作流 SOP (11_create_action_workflows)

本文档是 Build 阶段 **Step 11（按动作工作流并发注入节点并发布）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [单工作流执行 SOP 流水线](#三-单工作流执行-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与错误自愈](#五-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：子代理按动作工作流并发；
- **任务目标**：针对 Step 3 创建自定义动作时已自动生成的工作流实体外壳（已持有 `processId`），注入审批块、数据更新等节点并正式发布启用；
- **核心输入契约**：
  - `hap-plan.json`：动作工作流设计方案（`workflows.actions`）；
  - `worksheetContext.json`：相关工作表的真实字段结构与 controlId 映射；
  - `hap-context.json`：Step 3 产物中各动作绑定的 `processId`。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-workflows.md](../../references/spec-workflows.md)（动作工作流注入、nodeId 引用、审批块与发布时序）

---

## 三、 单工作流执行 SOP 流水线

1. **提取 processId**：
   - 直接从任务切片上下文获取当前动作工作流的 `processId`；
2. **批量注入业务节点 (batch_create_process_nodes)**：
   - 按照 `references/spec-workflows.md` 规范，调用 `batch_create_process_nodes` 注入审批流、状态回写与通知节点；
   - 子流程/审批块走两步创建；
3. **校验并发布启用 (validate & publish)**：
   - ⚠️ **含子流程/审批块时先发布内部 processId，最后发布主流程**；
   - 调用 `publish_process` 将动作流置为正式启用状态。

---

## 四、 输出交付物契约 (.build)

执行成功后，将发布结果与标准回执写入独立任务回执文件：
- **文件路径**：`.build/receipts/step11-act-wf-{actionName}.json`
- **内容格式**：
```json
{
  "taskId": "step11-act-wf-{actionName}",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "11",
  "target": { "type": "workflow", "name": "{actionName}" },
  "status": "succeeded",
  "outputs": {
    "actionName": "{actionName}",
    "processId": "proc_act_456",
    "published": true
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 publish_process 成功校验并发布动作工作流 proc_act_456"]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与错误自愈

1. **断言 1 (发布成功)**：`publish_process` 返回成功（或已成功发布）；
2. **断言 2 (回执通知)**：将包含 `actionName`、`processId` 与 `published: true` 的标准回执写入 `.build/receipts/step11-act-wf-{actionName}.json`；
3. **自愈机制**：若 `validate_process` 报错，定位错误分支重新组装重试。
