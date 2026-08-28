# Step 2a: 创建工作表与基础字段排版 SOP (2a_create_worksheets)

本文档是 Build 阶段 **Step 2a（按表并发创建工作表与基础字段）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [单表执行 SOP 流水线](#三-单表执行-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与错误自愈](#五-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：子代理按表并发；
- **任务目标**：根据 `hap-plan.json` 创建 1 张工作表，并一次性注入该表的 **基础字段（非关联/非公式）、Divider 业务分段、12 列栅格排版及表单高级体验设置**（支持在有遗漏时通过 `update_worksheet` 进行二次补充）；
- **准许调用工具清单 (Tool Whitelist)**：`["create_worksheet", "update_worksheet"]`；
- **核心输入契约**：
  - `hap-plan.json`：目标表的名称、描述、字段列表（`fields`）、表单设置（`formSettings`）；
  - `hap-context.json`：`appId`、`appSectionIdByName`。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-worksheets.md](../../references/spec-worksheets.md)（工作表创建、字段类型、两遍建表、默认值、排版与表单高级设置）
> 📖 [references/spec-custom-fields.md](../../references/spec-custom-fields.md)（自定义代码组件字段契约与 React 代码生成规范）

---

## 三、 单表执行 SOP 流水线（两遍建表三步法）

### 1. 字段类型与排版三步法 (Two-pass Parallel)

#### Step A — 统一排所有需建表单字段（先过滤 :reverse 与 SubTable 父级关联）
- **反向承接端（:reverse）不参与排版与创建**：Plan fields 中的 `:reverse` 字段是由对端 `:bi` 自动在详情页 Tab 标签页带出的反向表格，**不属于主表单网格字段（不占表单 rowIndex/span）**，在 Step A 开始前直接忽略过滤掉，**严禁记入 relationLayout**；
- **子表端指向主表的父级关联不参与排版与创建**：若当前表为明细子表（`worksheetType: "subTable"` 或包含 `parentWorksheet`），主表在声明 `SubTable:当前子表` 时已自动在子表生成父级关联，子表 fields 中声明的指向主表的 `Relation:主表` 字段直接过滤掉，**严禁记入 relationLayout**；
- 将剩余的**全部真实表单字段**（基础字段 + 自关联 + 跨表关联 `:bi`/`:uni` + SubTable 等）**一起**按正常网格规则分配 `rowIndex` 和 `span`（span=3/6/12，每行 span 和 ≤ 12）。

#### Step B — 删跨表关联和衍生计算字段、保行号不变
从 Step A 的完整 fields 列表中**剔除所有需后置在 Step 2b 补建的字段**：
1. 跨表关联字段（包含 `Relation:目标表`）、SubTable 字段；
2. Lookup 字段和 Rollup 字段；
3. **跨表 Concatenate**：若 `Concatenate` 表达式引用了任何跨表 Relation 关联字段；
4. **跨表/衍生 Formula**：若 `Formula` 表达式引用了任何 Lookup 他表字段或 Rollup 汇总字段；
- 其余字段（基础业务 + 自关联 `selfRelation` + 仅引用本表基础字段的 Formula/Concatenate）的 `rowIndex`/`span` **原封不动**保留，不紧缩行号间隙。

> [!CAUTION]
> **自关联判定唯一标准**：只有 Plan 紧凑格式中原文写为 `(selfRelation)` 的字段才是自关联。所有 `(Relation:xxx)` 格式的跨表关联必须 100% 剔除并留待 Step 2b 补建，严禁使用自关联规避。

#### Step C — 记录 relationLayout
把 Step B 移除的每个待创建字段及其预留的 `rowIndex`/`span` 记入任务回执的 `outputs.relationLayout` 数组中（**再次确认已彻底剔除 `:reverse` 字段和 SubTable 子表端关联**）。

### 2. 调用 MCP 建表 (create_worksheet)
> [!IMPORTANT]
> **子表类型导航隐藏铁律 (`displayType: 2`)**：
> - 若当前表为明细子表（Plan 中 `worksheetType: "subTable"` 或包含 `parentWorksheet`），**必须传入 `"displayType": 2`（全部隐藏）**，使其仅作为嵌入子表控件展示，不在左侧导航栏暴露；
> - 普通业务表/主表/字典表保持默认显示（`displayType: 1` 或不传）。

调用 `create_worksheet`（**必须传入 `"createDefaultView": false`**，跳过平台自动生成默认全部视图，由后续步骤按规划顺序一次性建好）：
```json
{
  "appId": "<appId>",
  "sectionId": "<sectionId>",
  "name": "工作表名称",
  "alias": "biz_xxx",
  "icon": "12_2_book",
  "createDefaultView": false,
  "displayType": 2,
  "fields": [ ...转化后的基础字段与Divider数组... ]
}
```
获取返回的 `worksheetId` 及控件列表。

### 3. 二次补充字段（按需 update_worksheet）
若建表后发现某些基础字段配置有遗漏，可调用 `update_worksheet` 进行增量补充：
```json
{
  "appId": "<appId>",
  "worksheetId": "<worksheetId>",
  "fields": [ ...遗漏需要追加的基础字段数组... ]
}
```
若 Plan 中包含表单设置或表内包含附件封面图，调用 `update_worksheet_settings`：
```json
{
  "worksheetId": "<worksheetId>",
  "settings": {
    "form": { "title": "提交业务单据", "cover": { "controlId": "...", "height": 300 } },
    "submission": { "afterSubmit": "openCreatedRecord" }
  }
}
```

---

## 四、 输出交付物契约 (.build)

执行成功后，将本表的 ID、关联待办与标准回执写入独立任务回执文件：
- **文件路径**：`.build/receipts/step2a-ws-{targetWorksheet}.json`
- **内容格式**：
```json
{
  "taskId": "step2a-ws-{targetWorksheet}",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "2a",
  "target": { "type": "worksheet", "name": "{targetWorksheet}" },
  "status": "succeeded",
  "outputs": {
    "worksheetId": "ws_xxxxxx",
    "worksheetName": "客户",
    "relationLayout": [ ...待 Pass 2 处理的关联字段... ]
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 create_worksheet 成功获取物理 worksheetId: ws_xxxxxx"]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与错误自愈

1. **断言 1 (建表成功)**：`create_worksheet` 返回成功且捕获合法物理 `worksheetId`（24 位 Hex 字符串）；
2. **断言 2 (回执通知)**：将包含 `worksheetId`、`worksheetName` 与 `relationLayout` 的标准回执写入 `.build/receipts/step2a-ws-{targetWorksheet}.json`；
3. **自愈机制**：若创建报错提示 alias 重复，追加随机后缀安全重试；若网络超时，先查询确认是否已建成功。
