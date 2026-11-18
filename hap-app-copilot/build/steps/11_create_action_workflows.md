# Step 11: 单个自定义动作工作流设计、注入与发布 SOP (`11_create_action_workflows`)

<!-- SOURCE: build-app/custom-action-design-sub-agent.yaml -->
<!-- SOURCE: build-app/custom-action-workflow-sub-agent.yaml -->

## 一、 本地宿主输入与参考映射

- **执行方式**：独立 Subagent 按**单个自定义动作**并发执行，在同一子代理上下文内一气呵成完成 **「读取预建触发节点与数据源核对 ➔ 7 维闭环节点设计 ➔ 物理节点注入 ➔ 校验修复与发布」**。动作空壳流程已由 Step 3 `create_custom_actions` 自动预建，本步**严禁调用 `create_process`**。
- **输入切片**：读取 `.build/task-context/{taskId}.json`：
  - `planSlice`：`actionWorkflow`（该按钮动作完整规划定义，含所属 `worksheet`、动作 `name`、`type`、`runWorkflowAfterSubmit`、`description`、`intentHints`、`requirements`）、`workflowIndex`、`customActionIndex`、`relationLayouts`、`appLanguage`；
  - `contextSlice`：`appId`、`org_id`、`processId`（Step 3 按 `worksheet::action` 精确捕获的预建 `workflowId`）、`worksheetIdByName`、`roleContext`、`viewIdByName`；
  - `worksheetContextSlice`：已建工作表真实 `worksheetId` 及字段 `{ name, id, alias, type, options }`（含选项 `{ key, value, index }`）。
- **必读领域规范**：`references/hap-workflow-design-guide.md`、`references/hap-domain-workflow-spec.md`
- **主要业务工具**：`["get_custom_action_list", "find_member", "find_department", "get_current_user", "get_worksheet_field", "get_worksheet_structure", "get_workflow_structure", "get_workflow_node", "get_workflow_variables", "update_workflow_node", "update_workflow_variables", "batch_create_process_nodes", "batch_delete_process_nodes", "validate_process", "publish_process", "get_sms_signatures"]`

---

## 二、 核心构建规则与执行步骤

### 1. 触发节点物理 `nodeId` 读取与数据源设计规则（核心铁律！）
1. **核实预建 `processId`（支持线上动作列表自愈补齐）**：检查 `contextSlice.processId`（按 `worksheet::action` 精确绑定所属表动作，严禁跨表混用同名按钮）；若为空，立即调用 `get_custom_action_list(appId, worksheet_id: <所属表真实worksheetId>)` 查找同名按钮动作，直接读取其返回的 `workflowId` 作为 `processId` 继续执行，仅当前置按钮动作本身在线上不存在时才向主调度器报告依赖缺口。
2. **首步读取物理 `nodeId`（严禁使用别名）**：
   - 自定义动作预建流程的触发节点**没有可用触发别名**！**绝对禁止**使用 `{ "nodeAlias": "trigger" }`（否则必触发 `StartNodeControlsIsNull` 错误）；
   - **第一步必须调用 `get_workflow_structure(workflow_id: processId)`**，提取触发节点的真实**物理 `nodeId`** 及真实数据源模式（单条 `single` / 多条批量 `multiple` / 表单提交后触发 `runWorkflowAfterSubmit`），后续所有节点引用触发记录一律使用 `{ "nodeId": "<真实触发nodeId>" }`，公式/模板占位符使用 `$<真实触发nodeId>-<24位真实fieldId>$`。
3. **基于真实结构与数据源语义完成节点设计（源自 `custom-action-design-sub-agent.yaml`）**：
   - 严格基于 `worksheetContextSlice` 真实存在的表、24 位字段 `id`（禁传 `alias`）与选项真实 `key`（禁传中文 `value`）设计节点；
   - 将动作的 `description`、`intentHints` 与 `requirements` 落实为完整闭环（例如状态变更、时间戳/处理人回写、关联单据生成或审批/通知）；多条批量数据源（`multiple`）注意批量处理语义，表单提交后触发基于提交后的当前记录字段设计。
   - **审批动作（含 `approval_block`，如「提交审批」）双分支闭环硬门禁**：
     1. **进入审批前**：先通过 `update_record` 将当前单据状态置为“待审批 / 审核中”（真实选项 `key`）；
     2. **审批后双分支必配**：`approval_block` 后**必须紧接 `branch` 分支节点**（路径首节点 `prevNode` 指向 `branch`、`parentNode` 指向对应路径，数据字段引用物理触发 `nodeId` 而非 `branch`），完整覆盖：
        - **通过路径**：`update_record` 将状态置为“已通过 / 已生效”（真实选项 `key`）+ 必要业务联动回写 + `send_notification` 通知申请人；
        - **驳回路径**：`update_record` 将状态回退为“已驳回 / 草稿”（真实选项 `key`）+ `send_notification` 通知申请人修改重提；
     3. **严禁只建孤立的 `approval_block` 漏写通过/驳回状态回写分支就发布上线！**

### 2. 参数核实、节点注入与校验上线（源自 `custom-action-workflow-sub-agent.yaml`）
1. **Lazy MCP Schema 必读与 `appId` 必传铁律**：若处于 Lazy-loaded MCP 环境（如 `call_mcp_tool`），首次调用 `get_workflow_structure`、`batch_create_process_nodes`、`update_workflow_node`、`validate_process`、`publish_process` 前**必须先读取对应的 `.json` Schema 文件**（遵循 [宿主适配](../../HOST_ADAPTER.md)）确认 `approval_block`、`branch`、`update_record`、`Condition.op` 结构，且所有应用内流程接口均须显式传入 `"appId": contextSlice.appId`。
2. **组织身份解析**：需要固定人员、部门、当前请求用户或短信签名时，使用 `contextSlice.org_id` 调用 `find_member` / `find_department` / `get_current_user` / `get_sms_signatures` 解析真实身份；关键接收者缺失则保留 `draft` 如实说明。
3. **批量创建节点**：调用 `batch_create_process_nodes(workflow_id: processId, nodes)` 注入完整节点链（流程内各 `nodeAlias` 保持唯一，不直接写只读衍生字段）。
4. **内部块先内后外发布与主流程校验**：
   - 含 `approval_block / sub_process / loop` 时，先对内部 `processId` 完成校验与 `publish_process`；
   - 对主流程调用 `validate_process(workflow_id: processId)`，若有 `issues` 则按 `nodeId / path / hint` 用 `update_workflow_node`（`config` 为原生 Object）定点修复，严禁私自删减核心业务节点凑发布；
   - 校验通过后调用 `publish_process(workflow_id: processId)` 发布上线（超时未知先查 `published` 状态，严禁盲目重放）。

---

## 三、 本地回执落盘契约

> **顶层 `status` 与 `outputs.status` 严格区分铁律**：
> - 顶层 `"status"` 表示**本搭建任务是否完成节点注入落库**（枚举仅 `"succeeded" | "failed"`）；`outputs.status` 表示**线上动作流的发布状态**（`"published" | "draft"`）。
> - 当动作工作流节点链已成功写入线上流程，仅因固定接收人缺失、无可用短信签名等外部环境原因按规范保留草稿（`outputs.status: "draft"`）时，**顶层 `"status"` 必须写 `"succeeded"`** 并在 `issues` 如实记录待补齐项，**严禁将合法保留的草稿写成顶层 `"failed"`**！仅当预建 `processId` 不存在或节点完全未能落库时才写 `"failed"`。

执行完成后，写入 `receiptPath`（`.build/receipts/step11-act-wf-{ws}_{name}.json`）：

```json
{
  "taskId": "<来自 taskContext.taskId>",
  "runId": "<runId>",
  "executor": { "kind": "subagent", "agentId": "<agentId>" },
  "step": "11",
  "target": { "type": "workflow", "id": "<processId>", "name": "<worksheet>/<actionName>" },
  "status": "succeeded",
  "outputs": {
    "worksheetName": "<worksheet>",
    "actionName": "<actionName>",
    "processId": "<processId>",
    "status": "published",
    "description": "<已发布简述用途；若为 draft/skipped/unknown 说明具体原因>"
  },
  "verification": {
    "passed": true,
    "evidence": ["已获取触发节点物理 nodeId，完成动作工作流节点设计、注入与 publish_process 发布"]
  },
  "issues": []
}
```
