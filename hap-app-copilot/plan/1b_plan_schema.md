# HAP 应用规划 Schema 规格指南 (1b_plan_schema)

> 同源基准：`skills/hap-app-plan-builder-spec`

本文档定义 `hap-plan.json` 的机器结构、紧凑字符串语法、`requirements` 补充要求通道与闭环硬约束。

---

## 一、 顶层 JSON 骨架与对象补充要求 (`requirements`)

```json
{
  "org_id": "来自前置检查确定的组织 ID",
  "appName": "应用名称（2~8字，严禁带系统/管理/平台/软件/后台等后缀）",
  "language": "zh-CN",
  "appIcon": "sys_ 前缀受控图标 fileName，如 sys_dashboard",
  "appColor": "官方 9 色板 HEX，如 #2196F3",
  "navLayout": "group | tree | top | card",
  "navColor": "appColor | white | gray | black",
  "enableExternalPortal": false,
  "requirements": ["可选：仅放应用级导航/设置/手册补充要求"],
  "navGroups": ["业务总览", "核心业务", "基础档案"],
  "worksheets": [],
  "customPages": [],
  "customActions": [],
  "workflows": [],
  "roles": [],
  "aiAssistants": []
}
```

### 1. 顶层属性约束
- **`org_id`**：固定下划线键名 `org_id`（严禁写为 `orgId`）。
- **`language`**：与当前会话锁定的语言代码一致（如 `"zh-CN"`、`"en"`、`"ja"`），下游构建子代理据此统一所有用户可见文本语言。
- **`appIcon` / `appColor`**：从 `references/hap-icon-palette.md` 精确选取带 `sys_` 前缀的合法 `fileName` 与 9 色板 HEX 色值；`navLayout` 与 `navColor` 选型遵循 `references/hap-domain-app-spec.md`。
- **`enableExternalPortal`**：规划了外部门户角色（`roleScope: "externalPortal"`）时必须设为 `true`。
- **`navGroups`**：完整覆盖 `worksheets`、`customPages`、`aiAssistants` 中用到的全部 `groupName`（逐字精确一致，严禁简写），决定分组创建与展示顺序。

### 2. 对象级 `requirements?: string[]` 补充要求通道
应用顶层、`worksheets[]`、`customPages[]`、`roles[]`、`aiAssistants[]`、`workflows[]` 以及 `customActions[].actions[]` 均可携带可选的 `requirements: string[]` 数组：
- 用于结构化传递紧凑字符串无法表达的用户定制细节（如顶层 `["采用顶部导航"]`，页面 `["四张指标卡均不显示图标"]`）；
- 原有字段（如 `businessRulesNotes`、`intentHints`）能表达的内容直接写原字段，不在 `requirements` 重复；
- 按实际作用对象精准归属，严禁将具体表、页面或流程的要求笼统堆在顶层 `app.requirements`，无补充要求时省略该键。

---

## 二、 `worksheets`（工作表数组）

每个元素结构：`{ "name", "groupName", "description", "worksheetType"?, "parentWorksheet"?, "icon", "color", "fields", "views", "businessRulesNotes"?, "consistencyNotes", "requirements"? }`

- **`name`（去“表”后缀规范）**：使用纯粹业务实体名词（如 `客户`、`采购订单`、`中奖名单`），自动剔除口语中的“表/工作表”后缀（仅 `资产负债表`、`利润表`、`课程表` 等专有名词或用户显式强调保留时例外）。
- **`worksheetType` 与主子表双向闭环硬约束**：普通表为 `"normal"`（默认），明细子表为 `"subTable"` 且必填 `parentWorksheet`（主表名称）。**凡声明 `worksheetType: "subTable"` 的子表，其主表 `fields` 中必须 100% 包含对应的 `"子表名(SubTable:子工作表名)"` 字段，严禁出现孤立子表！**
- **`icon`**：从 `references/hap-icon-palette.md` 选取带 `sys_` 前缀的合法图标，同组内避免雷同。
- **`businessRulesNotes`**：字符串数组，用“意图 + 举例”的自然语言描述显隐、只读、赋值、校验或终态锁定规则（除纯字典表外按需必配）。
- **`consistencyNotes`（必填）**：简述本表选项字段如何支撑视图筛选、业务规则、动作条件与工作流流转。

### 1. `fields` 紧凑字符串语法
系统默认字段（创建时间/创建人/最近修改时间/修改人）严禁写入 `fields`。专属业务语义必须使用 `PhoneNumber`、`Email`、`Currency`、`Collaborator`、`Department`、`Region`、`Location`、`AutoNumber`、`Signature`、`Barcode`，严禁降级为 `Text`/`Number`。
1. **选项字段**：`"状态(SingleSelect:待处理/进行中/已完成)"`（支持 `SingleSelect` / `MultipleSelect` / `Dropdown`，选项以 `/` 分隔）。
2. **跨表关联三态单边声明铁律**：`"字段名(Relation:目标表名:single|multiple:uni|bi|reverse)"`：
   - `:uni`（单向引用）：本表建选择框，目标表不生反向字段（用于选字典、仓库、商品主数据）；
   - `:bi`（双向主创建端）：仅由单边主动发起（`bidirectional: true`），服务端自动在对端生成反向 Tab 表格；
   - `:reverse`（双向反向承接端）：对端已声明 `:bi` 时，本表如需透视标记 `:reverse`，建表引擎自动跳过 API 调用，**严禁双边重复声明 `:bi`**。
3. **自关联与子表**：自关联 `"上级部门(selfRelation)"`；子表挂载 `"采购明细(SubTable:采购明细)"`。
4. **衍生计算字段**：主子表或多条关联主表必配 1～2 个汇总 `"总金额(Rollup:采购明细.金额.sum)"`（`sum/count/avg/max/min`）；按需配置他表字段 `"参考单价(Lookup:关联商品.销售单价)"`；业务单据标题推荐组合文本 `"借阅摘要(Concatenate)"`。
5. **字段丰富度**：主数据表 ≥ 15 个、业务单据表 ≥ 12 个、过程流水表 ≥ 8 个、子表 ≥ 3 个，覆盖主标识、核心属性、状态分类、时间、责任人、数量金额、说明凭证、计算衍生 8 个维度。

### 2. `views` 紧凑字符串语法
格式 `"视图名(Type)"`，`Type` ∈ `Table | Kanban | Calendar | Gantt | Gallery | Detail | Hierarchy | Map | Resource`，所依赖分组/日期/自关联/定位字段必须在 `fields` 中真实存在。

---

## 三、 `customPages`、`customActions`、`workflows`、`roles`、`aiAssistants`

1. **`customPages`（自定义页面数组）**：
   - 公共属性：`name`、`groupName`、`type`（`"dashboard"` 或 `"workspace"`）、`description`、`icon`（从 `references/hap-icon-palette.md` 选取带 `sys_` 前缀的合法图标，如 `"sys_control-panel_traffic"`、`"sys_hr_workbench"`）、`color`、`requirements`?。
   - `type: "dashboard"` 必填 `charts`（建议 6～10 项：1 个 `"全局筛选(FiltersGroup:维度1,维度2)"` + 4～6 个 `NumberChart` + 趋势/占比/排行图 + `PivotTable`，图表枚举使用标准 MCP `chartType`）。
   - `type: "workspace"` 必填 `components`（紧凑格式 `"名称(Type)"`，`Type` ∈ `Button | View | Text | Carousel | Section`）。
2. **`customActions`（按工作表分组的自定义动作数组）**：
   - 元素结构：`{ "worksheet": "工作表名", "requirements"?, "actions": [{ "name", "description", "type", "runWorkflowAfterSubmit"?, "targetWorksheet"?, "relateFieldName"?, "enableCondition"?, "intentHints"?, "requirements"? }] }`。
   - **三类 `type` 人工输入边界铁律（严禁选错类型！）**：
     - `"createRelatedRecord"`：**操作需收集人工输入并在另一张表新增记录**（如在 `图书` 点「发起借阅」填读者与应还日期新建 `借阅记录`，或在 `借阅记录` 点「登记异常」新建 `异常赔偿`）。必填 `targetWorksheet` 与源表 `fields` 中**已显式声明**的 `relateFieldName`（指向 `targetWorksheet` 的 `Relation` 字段名；若源表尚未声明该关联字段，必须先在源表 `fields` 补上该 `Relation` 字段！）；提交后需自动改状态/扣库存则设 `runWorkflowAfterSubmit: true` 并配 `intentHints`。
     - `"updateCurrentRecord"`：**操作需收集人工输入以更新当前记录字段**（如在 `借阅记录` 点「申请续借」输入新应还日期与续借原因）。当前表 `fields` 中必须真实存在对应承接字段，并在动作 `requirements` 中指明待填字段名；提交后需自动流转则设 `runWorkflowAfterSubmit: true` 并配 `intentHints`。
     - `"triggerWorkflow"`：**仅限 100% 零人工输入的一键自动操作**（点击后不弹任何表单，仅依赖当前记录已有字段、`triggerUser` 与当前系统时间即可完成，如「确认归还」「提交审批」）。必填 `intentHints: [{ "label": "..." }]`，严禁将需要点击人现场输入读者、日期、金额、原因或类型的动作设为 `"triggerWorkflow"`！
3. **`workflows`（系统自动化工作流数组）**：
   - 元素结构：`{ "name", "description", "trigger": { "type": "worksheet_event | schedule | date_field", "source": "工作表名或空串", "label": "触发条件描述" }, "intentHints": [{ "label": "..." }], "requirements"? }`（注：按钮动作流写在 `customActions` 中，不放入 `workflows`）。
4. **`roles`（角色权限数组）**：
   - 元素结构：`{ "name", "description", "roleScope": "general | externalPortal", "permissions": ["名称(worksheet)", "名称(customPage)", "名称(aiAssistant)"], "requirements"? }`。
5. **`aiAssistants`（AI 智能助手数组）**：
   - 元素结构：`{ "name", "groupName", "description", "icon": "sys_virtual-assistant_office", "color": "#9C27B0", "requirements"? }`（`icon` 必须带 `sys_` 前缀）。

---

## 四、 落盘前闭环自检清单

1. `navGroups` 100% 逐字覆盖所有工作表、自定义页面与 AI 助手的 `groupName`；所有 `icon` 均带合法 `sys_` 前缀；
2. 所有 `worksheetType: "subTable"` 子表均在 `parentWorksheet` 主表 `fields` 中有唯一对应的 `SubTable` 字段及至少 1 个 `Rollup` 字段；
3. 跨表关联严格遵守 `:bi` 单边发起、对端 `:reverse`、字典 `:uni`，零双边重复 `:bi`；
4. **自定义动作输入入口闭环**：逐个检查 `customActions`——凡需人工输入信息的动作严禁用 `triggerWorkflow`；`createRelatedRecord` 的 `relateFieldName` 在源表 `fields` 中真实存在且指向 `targetWorksheet`；`updateCurrentRecord` 待填字段在当前表 `fields` 中真实存在；严禁出现「审批通过/审批驳回」按钮；
5. 所有 `triggerWorkflow` 及 `runWorkflowAfterSubmit: true` 的动作均包含完整的 `intentHints`。
