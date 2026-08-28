# Step 3: 视图、动作与业务规则一体化 SOP (3_create_actions_views_rules)

本文档是 Build 阶段 **Step 3（单表一体化：结构采集 + 自定义动作 + 视图配置 + 业务规则）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [单表执行 SOP 流水线（严格四步闭环）](#三-单表执行-sop-流水线严格四步闭环)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与防死循环铁律](#五-⛔-验证断言与防死循环铁律)

---

## 一、 执行定位与输入契约

- **执行方式**：按工作表并发派发原子 Subagent（任务 ID: `step3-view-act-{targetWorksheet}`）；
- **任务目标**：针对指定的单张工作表闭环完成：
  1. **结构采集**：调用 1 次 `get_worksheet_structure` 获取本表最新字段（包含 Step 2b 二次回填自动生成的反向关联字段与真实物理 `controlId`），并写入结构分片；
  2. **业务规则**：配置本表的业务规则（显隐、只读、必填、错误拦截）；
  3. **自定义动作**：创建本表的自定义动作并捕获 `actionId`；
  4. **个性化视图**：创建本表的个性化视图（表格、看板、画廊等），使用真实字段配置过滤、排序与显示列；
  5. **双产物落盘**：写入结构分片文件与标准任务回执。
- **核心输入契约**：
  - 读取最小任务上下文：`.build/task-context/step3-view-act-{targetWorksheet}.json`（包含 `appId`、`worksheetId`、`worksheetName`、`businessRules`、`views`、`customActions`）。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary References (平台规格 SSOT)**：
> 1. 📖 [references/spec-actions-views.md](../../references/spec-actions-views.md)（视图类型规范与自定义动作参数配置指南）
> 2. 📖 [references/spec-business-rules.md](../../references/spec-business-rules.md)（业务规则条件语法与动作配置规范）
>
> **准许调用工具清单 (Tool Whitelist)**：
> `["get_worksheet_structure", "create_business_rule", "create_custom_actions", "create_view"]`

---

## 三、 单表执行 SOP 流水线（严格四步闭环）

每个 Subagent 接收单一目标工作表，按顺序执行以下步骤：

### 1. 采集本表最新结构与分片落盘（严格调用 1 次）
1. **调用工具**：调用 `get_worksheet_structure` 拉取本表最新字段元数据：
   ```json
   {
     "appId": "<appId>",
     "worksheet_id": "<worksheetId>"
   }
   ```
2. **提取最新字段列表**：
   - 提取本表所有字段的 `name`、`controlId` (或 `id`)、`alias`、`type`、`options`，**包含 Step 2b 跨表关联回填在本表自动生成的反向关联字段与 TabTable 明细**；
3. **写入分片文件**：将拉取到的最新结构写入 `.build/artifacts/worksheet-{worksheetId}.json`（供后续阶段汇聚合并）。
> ⚠️ **铁律**：`get_worksheet_structure` **本表严格只允许调用 1 次**！一旦收到数据立即进入下一步，严禁任何形式的重复调用或跨表查询！

---

### 2. 配置业务规则 (Business Rules)
若切片上下文中包含 `businessRules` 规划，利用第一步获取的真实字段，调用 `create_business_rule`：
- **交互规则 (`ruleType: "interaction"`)**：显隐、部分只读、必填、赋值，或**全表只读 (`actionType: "readonlyAllFields"`，免传 `fields`，用户仍可删除记录)**；`conditions` 必须用 `group` 结构；
- **校验规则 (`ruleType: "validation"`)**：提交前防呆校验拦截，配置 `validateOnServerSave: true` 与 `errorAction: "blockSubmit"`；
- **锁定规则 (`ruleType: "lock"`)**：单据终态归档封存（**同时锁死编辑与删除记录**，前台显示锁头提示），`conditions` 必须直接传单个 `condition` 对象（仅限单选/多选/勾选字段），附带 `lock: { "message": "..." }`；
```json
{
  "appId": "<appId>",
  "worksheet_id": "<worksheetId>",
  "name": "已归档单据锁定",
  "ruleType": "lock",
  "conditions": { "type": "condition", "fieldId": "<statusControlId>", "operator": "eq", "value": "已归档" },
  "lock": { "message": "单据已归档，系统已自动锁定，禁止修改与删除" }
}
```

---

### 3. 创建自定义动作 (Custom Actions)
若切片上下文中包含自定义动作规划，调用 `create_custom_actions`：
```json
{
  "appId": "<appId>",
  "worksheetId": "<worksheetId>",
  "customActions": [ ...动作列表... ]
}
```
获取返回的 `actionIdByName`（动作名 → actionId 映射）并记录，供下一步视图关联使用。

---

### 4. 创建个性化视图 (Views)
> [!TIP]
> **视图一次性创建原则**：
> 由于建表时已配置 `createDefaultView: false`，工作表初始无多余默认视图。
> 直接遍历切片中的 `views` 列表，按预设顺序依次调用 `create_view` 一次性创建即可。
> 严禁调用 `delete_view`、`update_view` 或 `sort_views`。

1. **若 `views` 数组非空**：根据视图类型（表格、看板、画廊等）与第一步获取的字段信息，调用 `create_view`；
2. **若 `views` 数组为空（如子表）**：调用 `create_view` 创建一个默认表格视图（`[{ "name": "全部记录", "viewType": 0 }]`），确保底层基础视图可用；
3. 记录每个视图的 `viewIdByName`。

---

### 5. 写入标准任务回执
将执行结果写入回执文件：
- **文件路径**：`.build/receipts/step3-view-act-{targetWorksheet}.json`

---

## 四、 输出交付物契约 (.build)

### 1. 结构分片文件
- **路径**：`.build/artifacts/worksheet-{worksheetId}.json`
- **内容**：`get_worksheet_structure` 返回的完整工作表结构对象。

### 2. 标准任务回执
- **路径**：`.build/receipts/step3-view-act-{targetWorksheet}.json`
- **格式**：
```json
{
  "taskId": "step3-view-act-{targetWorksheet}",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "3",
  "target": { "type": "worksheet", "id": "{worksheetId}", "name": "{targetWorksheet}" },
  "status": "succeeded",
  "outputs": {
    "worksheetId": "{worksheetId}",
    "worksheetName": "{targetWorksheet}",
    "businessRulesConfigured": true,
    "viewIdByName": {
      "{targetWorksheet}/全部记录": "view_123",
      "{targetWorksheet}/待处理": "view_456"
    },
    "actionIdByName": {
      "审核通过": "act_789"
    }
  },
  "verification": {
    "passed": true,
    "evidence": [
      "成功调用 get_worksheet_structure 并保存 worksheet 结构分片",
      "成功调用 create_business_rule 创建业务规则",
      "成功调用 create_custom_actions 创建自定义动作",
      "成功调用 create_view 创建个性化视图并捕获 viewId"
    ]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与防死循环铁律

1. **断言 1 (单次回读铁律)**：`get_worksheet_structure` 仅在第 1 步调用 **恰好 1 次**，严禁重复调用；
2. **断言 2 (视图与动作创建成功)**：创建的视图与动作必须记录对应的 `viewIdByName` 与 `actionIdByName`；
3. **断言 3 (双产物落地)**：必须同时产出 `.build/artifacts/worksheet-{worksheetId}.json` 分片与 `.build/receipts/step3-view-act-{targetWorksheet}.json` 回执；
4. **终结规则**：写入回执后，任务即告圆满结束，**绝对禁止再次发起任何工具调用**！
