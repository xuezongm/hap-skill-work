# Step 3: 单表结构刷新、自定义动作、视图与业务规则一体化 SOP (`3_create_actions_views_rules`)

<!-- SOURCE: build-app/view-build-sub-agent.yaml -->
<!-- SOURCE: build-app/business-rule-build-sub-agent.yaml -->

## 一、 本地宿主输入与参考映射

- **执行方式**：独立 Subagent 按表并发执行（正常复用一次 `get_worksheet_structure` 结果完成动作、视图、业务规则与字段分片落盘；截断、状态变化或排查需要时按需补读）。
- **输入切片**：读取 `.build/task-context/{taskId}.json`：
  - `planSlice`：`worksheetName`、`views`（紧凑字符串数组）、`customActions`（本表动作数组）、`businessRules`（对应 `businessRulesNotes`）、`requirements`、`appLanguage`；
  - `contextSlice`：`appId`、`worksheetId`（24 位 hex）、`worksheetIdByName`、`artifactPath`（`.build/artifacts/worksheet-{worksheetId}.json`）。
- **必读领域规范**：`references/hap-domain-view-spec.md`、`references/hap-domain-custom-action-spec.md`、`references/hap-domain-business-rule-spec.md`
- **主要业务工具**：`["get_worksheet_structure", "get_custom_action_list", "create_custom_actions", "create_view", "get_view_structure", "update_view", "get_business_rule_list", "create_business_rule"]`

---

## 二、 核心构建规则与执行步骤

- **输出语言锁定**：视图名、动作文案、规则名称与校验提示消息必须严格使用 `appLanguage` 指定语言。
- **完建优先与契约保真**：遵循 [宿主适配](../../HOST_ADAPTER.md) 先核实 `create_custom_actions`、`create_view`、`create_business_rule` 实时 Schema；中断续跑时先核查线上已建动作/视图/规则防重。只要字段分片已落盘、规划动作与至少 1 个可用视图已落库，即便个别复杂业务规则修正后仍受限于平台参数边界，也只跳过该单条规则并记入 `issues`，顶层回执仍标记 `status: "succeeded"`，严禁因单条辅助规则失败阻断整表及后续阶段。

### Step 0：拉取关联落定后的最新完整字段并落盘分片（集中采集供后续步骤复用）
1. `worksheetId` 缺失时，从同批回执、完整上下文或线上工作表定位真实 ID；前置工作未完成则向主调度器报告具体依赖，按宿主适配继续恢复。
2. 优先调用 1 次 `get_worksheet_structure(appId, worksheet_id: worksheetId, responseFormat: "dsl", ai_description: "Worksheet: <worksheetName>")`（此时所有表与双向关联均已落定，直接获取无损结构化 JSON，包含对端 `:bi` 反向关联字段、精确 `options[].key`、`dataSource` 与关联/他表/汇总元数据；超大表发生截断时按分页/分块补齐）。
3. **24 位 Hex 字段 ID 清洗与完整保留铁律**：提取每个字段的 `{ name, id, alias, type, options?, dataSource?, relationField?, sourceField? }` 时，**必须剥离 ID 后的任何附加标注**（如将 `6a22a6c0912a77961c8e09ab(isTitle)` 清洗为纯净 24 位 hex 字符串 `6a22a6c0912a77961c8e09ab`），并原样保留单多选/下拉的 `{ key, value, index }` 与关联目标表 `dataSource`（24 位 hex 或 `"selfRelation"`）。
4. 将清洗后的单表结构对象 `{ "worksheetId": "<worksheetId>", "worksheetName": "<worksheetName>", "alias": "<本表alias>", "fields": [...] }` 写入 `contextSlice.artifactPath`（`.build/artifacts/worksheet-{worksheetId}.json`），供 `merge_worksheet_context.py` 归并生成阶段 3/4 上下文。

### Part A：自定义动作与视图创建（源自 `view-build-sub-agent.yaml`）
1. **先建自定义动作（若有）**：
   - 若为中断续跑，先调用 `get_custom_action_list(appId, worksheet_id: worksheetId)` 核查已存在动作并直接复用其 `id` 与 `workflowId`，仅补建缺失项；
   - 若 `customActions` 非空，按 `references/hap-domain-custom-action-spec.md` 及各动作的 `requirements`、`runWorkflowAfterSubmit`、`recordScope` 组装参数，调用 1 次 `create_custom_actions(appId, worksheet_id: worksheetId, actions)`；
   - 记录返回的动作真实 `id` 与原样回传的关联 `workflowId`（回执中写入 `processId` 字段，无流程时为空串），供下一步视图挂载 `detailActions / quickActions / batchActions` 及阶段 4 动作工作流使用。
2. **再建工作表视图（单表严禁无视图，保持规划视图类型保真）**：
   - 若 `views` 非空：将大驼峰类型转为 API 小驼峰（`Table→table`、`Kanban→kanban`、`Calendar→calendar`、`Gallery→gallery`、`Hierarchy→hierarchy`、`Gantt→gantt` 等），查阅 `create_view` 实时 Schema 匹配本表真实分组/日期/层级字段构建规划视图（仅当本表确实不存在任何可承载该高级视图类型的真实字段时，才回退为 `table` 并在 `issues` 注明），按 `references/hap-domain-view-spec.md` 将本表缺失视图**合并为一次 `create_view(appId, worksheet_id: worksheetId, views)` 批量提交**；
   - 若 `views` 为空（常见于明细子表）：**必须创建 1 个兜底表格视图** `[{ "name": "全部记录", "type": "table" }]`（英文环境用 `"All"`），确保后续示例数据与查询 API 正常可用；
   - **防重与修正**：若 Step 0 返回结果中已存在同名同类型视图则直接纳入回执，严禁重复调用 `create_view`；若个别属性需微调，按真实 `view_id` 调用 `update_view` 原地修正（注意禁止调用 `delete_view` 删除唯一视图）。

### Part B：表单业务规则创建（源自 `business-rule-build-sub-agent.yaml`）
1. 合并 `businessRules`（`businessRulesNotes`）与 `requirements` 中属于表单业务规则的条目；若无规则要求则直接跳过本部分（中断续跑时先调 `get_business_rule_list` 跳过已建同名规则）。
2. 对每条自然语言规则描述：
   - **理解业务意图扩展全字段范围**：`businessRulesNotes` 通常采用“意图 + 举例”描述（如“草稿态隐藏审核时间、打款流水号等后续字段”），必须对照 Step 0 拿到的**本表完整真实字段列表**覆盖全部同类后续字段，而非只处理举例中的一两个字段；
   - 遵循 `references/hap-domain-business-rule-spec.md` 与 `create_business_rule` 实时 Schema 推导 `ruleType`（交互/校验/锁定/样式），构造合法无冲突的 `conditions` 与动作配置块，逐条调用 `create_business_rule`（单条失败按 [宿主适配](../../HOST_ADAPTER.md) 定点修正重试 1 次；仍受限时跳过该条并记入 `issues`，绝不中断其余规则或将整表回执标为失败）。

---

## 三、 本地回执落盘契约

确认 `.build/artifacts/worksheet-{worksheetId}.json` 已写入后，将视图、动作（含 `processId`）及规则计数写入 `receiptPath`（`.build/receipts/step3-view-act-{name}.json`）：

```json
{
  "taskId": "<来自 taskContext.taskId>",
  "runId": "<来自 taskContext.runId>",
  "executor": { "kind": "subagent", "agentId": "<当前子代理标识>" },
  "step": "3",
  "target": { "type": "worksheet", "id": "<worksheetId>", "name": "<worksheetName>" },
  "status": "succeeded",
  "outputs": {
    "worksheetId": "<worksheetId>",
    "worksheetName": "<worksheetName>",
    "viewIdByName": { "<worksheetName>/<视图名>": "<24位真实viewId>" },
    "views": [{ "name": "<视图名>", "id": "<viewId>", "type": "table" }],
    "actionIdByName": { "<worksheetName>/<动作名>": "<动作id>" },
    "actions": [{ "name": "<动作名>", "id": "<动作id>", "processId": "<关联workflowId或空串>" }],
    "rulesCreated": 2
  },
  "verification": {
    "passed": true,
    "evidence": [
      "已拉取最新字段并写入 artifacts 分片文件",
      "已完成自定义动作、视图与表单业务规则创建"
    ]
  },
  "issues": []
}
```
