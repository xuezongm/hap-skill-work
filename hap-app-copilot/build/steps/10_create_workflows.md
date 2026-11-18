# Step 10: 单条系统工作流设计、创建、校验与发布 SOP (`10_create_workflows`)

<!-- SOURCE: build-app/workflow-design-sub-agent.yaml -->
<!-- SOURCE: build-app/workflow-build-sub-agent.yaml -->

## 一、 本地宿主输入与参考映射

- **执行方式**：独立 Subagent 按**单条系统工作流**并发执行，在同一子代理上下文内一气呵成完成 **「7 维闭环节点设计 ➔ 真实 ID 与身份映射 ➔ 物理建流与节点注入 ➔ 校验修复与发布」**，消除双阶段 JSON 传话失真与重复读表开销。
- **输入切片**：读取 `.build/task-context/{taskId}.json`：
  - `planSlice`：`workflow`（来自 `hap-plan.json` 的单条系统流定义，含 `name`、`description`、`trigger`、`intentHints`、`requirements`）、`workflowIndex`（全应用系统流职责索引）、`customActionIndex`（全应用动作流职责索引）、`relationLayouts`、`appLanguage`；
  - `contextSlice`：`appId`、`org_id`（用作人员/部门查询的 `orgId`）、`worksheetIdByName`、`roleContext`（`[{ name, id, roleScope }]`）、`viewIdByName`；
  - `worksheetContextSlice`：已建工作表真实 `worksheetId` 及字段 `{ name, id, alias, type, options }`（含选项 `{ key, value, index }`）。
- **必读领域规范**：`references/hap-workflow-design-guide.md`、`references/hap-domain-workflow-spec.md`
- **主要业务工具**：`["find_member", "find_department", "get_current_user", "get_worksheet_field", "get_worksheet_structure", "create_process", "get_workflow_structure", "get_workflow_node", "get_workflow_variables", "update_workflow_node", "update_workflow_variables", "batch_create_process_nodes", "batch_delete_process_nodes", "validate_process", "publish_process", "get_sms_signatures"]`

---

## 二、 核心构建规则与执行步骤

### 1. 基于真实表结构的节点拓扑设计（源自 `workflow-design-sub-agent.yaml`）
1. **只用真实上下文**：严格基于 `worksheetContextSlice` 中真实存在的表名、24 位字段 `id` 与选项 `key` 设计条件、查询、计算和更新，严禁捏造不存在的字段或选项；对照 `workflowIndex` 与 `customActionIndex` 明确本流程边界，避免与按钮动作流重复写数或互相循环触发。
2. **完整因果闭环**：将 `workflow` 的 `description`、`intentHints` 与 `requirements` 全部落实为“触发（更新时间触发必设具体监听字段防死循环）→ 必要关联/单条取数 → 业务计算/审批/分支 → 状态与关联写回/通知”的完整节点链，不得停留在仅取数的半截步骤。
3. **审批块（`approval_block`）双分支闭环硬门禁**：
   - 凡包含 `approval_block` 的审批流程，**严禁只建一个孤立的 `approval_block` 就结束或发布**！
   - 审批前确保单据状态处于“待审批/审核中”（若触发条件本身未限定或前置未置状态，先用 `update_record` 写入对应选项 `key`）；
   - **`approval_block` 之后必须紧接 `branch` 分支节点完整处理两种审批结果**（注意分支路径首节点的 `prevNode` 指向所属 `branch`、`parentNode` 指向对应路径，且条件/更新的数据源引用上游触发或记录节点而非 `branch` 自身）：
     - **通过路径**：调用 `update_record` 将状态更新为“已通过/已生效”（真实选项 `key`）+ 完成必要的下游关联写回/台账生成 + `send_notification` 通知发起人；
     - **驳回路径**：调用 `update_record` 将状态回退为“已驳回/待修改”（真实选项 `key`）+ `send_notification` 通知发起人驳回信息以便修改重提。
4. **人员与通知语义保真**：应用角色使用 `roleContext` 真实 `roleId`（`PersonRef { kind: "role", id }`）；固定姓名/部门调 `find_member`/`find_department`（`orgId` 传 `contextSlice.org_id`，不得传 `appId`，脱敏手机/邮箱不可外发）；“通知我”调 `get_current_user`（勿与运行时 `triggerUser` 混淆）；短信通知调 `get_sms_signatures` 取有效签名。关键接收者无法唯一定位时保留草稿（`status: "draft"`）说明缺口，严禁私自换人或删减必要节点强行发布。

### 2. 物理创建、参数核实与发布流水线（源自 `workflow-build-sub-agent.yaml`）
1. **Lazy MCP Schema 必读与 `appId` 必传铁律**：
   - 按 [宿主适配](../../HOST_ADAPTER.md) 核实参数：若处于 Lazy-loaded MCP 环境（如 `call_mcp_tool`），首次调用 `create_process`、`batch_create_process_nodes`、`update_workflow_node`、`validate_process`、`publish_process` 前**必须先读取对应的 `.json` Schema 文件**确认 `approval_block`、`branch`、`update_record`、`Condition.op` 结构及必填字段；所有应用内流程接口调用时均须显式传入 `"appId": contextSlice.appId`。
2. **字段与选项铁律**：
   - 节点中引用业务 `fieldId` **必须使用 24 位真实 `id`，严禁传 `alias`**；
   - 给单选/多选/下拉字段赋值时，**必须且只能传选项的真实 `key`**，严禁传中文名 `value`！关联取数节点的目标表由来源关联字段自动推导，不传 `worksheetId`；严禁直接更新公式/汇总/他表只读衍生字段。
3. **创建流程外壳**：若 `worksheet_event` / `date_field` 的触发工作表 ID 缺失，先核对工程上下文与线上表列表；仍无法定位时报告依赖缺口，不伪造 ID 或跳过必需流程。定位后调用 `create_process(appId, name, description, publish: false, trigger)`，读取返回的 `processId` 与 **`triggerAlias`**（缺失 `triggerAlias` 时按需调用 `get_workflow_structure` 兜底取 `trigger.nodeAlias`）。
4. **批量注入节点与内部块由内向外发布**：
   - 调用 `batch_create_process_nodes(workflow_id: processId, nodes)` 一次性或分组写入节点（触发记录引用使用 `triggerAlias`）；
   - 若含 `approval_block / sub_process / loop`，单独对其内部 `processId` 完成校验与 `publish_process`，**先内后外**。
5. **校验定点修复与主流程发布**：
   - 调用 `validate_process(workflow_id: processId)`；若有 `issues`，按 `nodeId / path / hint` 用 `update_workflow_node`（`config` 传原生 Object）定点修复，严禁静默删减审批或通知节点凑发布；
   - 校验通过后调用 `publish_process(workflow_id: processId)` 发布上线（超时或结果未知先调 `get_workflow_structure` 查 `published` 版本，严禁盲目重放）。

---

## 三、 本地回执落盘契约

> **顶层 `status` 与 `outputs.status` 严格区分铁律**：
> - 顶层 `"status"` 表示**本搭建任务是否完成落库**（枚举仅 `"succeeded" | "failed"`）；`outputs.status` 表示**线上工作流的发布状态**（`"published" | "draft"`）。
> - 当工作流外壳与完整业务节点链已成功落库，仅因外部固定接收人无法唯一定位、组织缺少短信签名等外部环境客观原因按规范保留草稿（`outputs.status: "draft"`）时，**顶层 `"status"` 必须写 `"succeeded"`** 并在 `issues` 如实列出待人工补齐项，**严禁将合法落库的草稿写成顶层 `"failed"` 阻断搭建闭环**！仅当 `create_process` 建壳失败或核心节点根本未落库时才写 `"failed"`。

执行完成后，写入 `receiptPath`（`.build/receipts/step10-sys-wf-{name}.json`）：

```json
{
  "taskId": "<来自 taskContext.taskId>",
  "runId": "<runId>",
  "executor": { "kind": "subagent", "agentId": "<agentId>" },
  "step": "10",
  "target": { "type": "workflow", "id": "<processId>", "name": "<workflowName>" },
  "status": "succeeded",
  "outputs": {
    "workflowName": "<workflowName>",
    "processId": "<processId>",
    "status": "published",
    "description": "<已发布简述用途；若为 draft/skipped/unknown 说明具体原因>"
  },
  "verification": {
    "passed": true,
    "evidence": ["已完成系统工作流节点设计、创建、validate_process 校验与 publish_process 发布"]
  },
  "issues": []
}
```
