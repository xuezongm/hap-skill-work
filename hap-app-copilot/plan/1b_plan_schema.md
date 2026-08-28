# HAP 应用规划 Schema 规格指南 (1b_plan_schema)

本文档是 HAP App Builder 的 **Plan 产物 Schema 规格指南**。与明道云官方 `mingdao-app-plan-builder-spec` 保持 100% 严格一致，定义紧凑字符串语法（Relation/SubTable/Rollup/Lookup）、主子表双向绑定闭环硬约束与单边声明铁律。

---

## 顶层 JSON 骨架结构

```json
{
  "org_id": "来自 Step 0 选择的组织 ID",
  "appName": "应用名称（2~8字，严禁系统/管理/平台等冗长后缀）",
  "language": "zh-CN",
  "appIcon": "图标名称，如 0_lego 或 sys_ 文件名",
  "appColor": "主题色 HEX，如 #2196F3",
  "navLayout": "group | tree | top | card",
  "navColor": "appColor | white | black",
  "enableExternalPortal": false,
  "navGroups": ["业务总览", "核心业务", "基础档案", "系统管理"],
  "worksheets": [],
  "customPages": [],
  "customActions": [],
  "workflows": [],
  "roles": [],
  "aiAssistants": []
}
```

### 属性约束说明：
* **`org_id`**：组织 ID，键名必须使用下划线风格 `org_id`，**严禁写成驼峰 `orgId`**。
* **`appName`**：应用名称（2~8 字），**严禁**使用“系统/管理/平台/软件/工具/应用/后台”等传统笨重后缀（如用“图书借阅大厅”优于“图书借阅管理系统”）。
* **`appIcon`**：应用图标，必须从 `references/spec-app-styles.md` 中挑选契合业务语义的预设图标。
* **`appColor`**：应用主题色，必须使用 `references/spec-app-styles.md` 中提供的官方 9 色板 Hex 色值。
* **`navLayout`**：导航布局形态。`"group"`（左侧分组，默认推荐）、`"tree"`（树状深层级）、`"top"`（顶部横向导航）、`"card"`（工作台卡片导流）。
* **`navColor`**：导航栏背景色，只能从 `appColor`、`white`、`black` 三个枚举中选择。
* **`enableExternalPortal`**：是否启用外部门户。若规划了外部门户角色（`roleScope: "externalPortal"`），此项必须为 `true`。
* **`navGroups`**：导航分组呈现与排序数组。列出所有分组名称，UI 与 Build 严格按此顺序渲染与建分组。

---

## 一、`worksheets`（工作表数组）

工作表数组中每个对象包含：
- `name`：工作表名称
- `groupName`：所属导航分组名称（必须从 `navGroups` 数组中逐字匹配，严禁简写或同义改写）
- `description`：一句话说明该表的业务定位与核心用途
- `worksheetType`（可选）：`"normal"`（默认，普通工作表）或 `"subTable"`（子表）。子表是从属于主表的明细表，需额外声明 `parentWorksheet`（主表名称）。子表的最低字段数量要求降低为 3～8 个
- `parentWorksheet`（仅子表必填）：主表名称
- `icon`：从 `references/spec-app-styles.md` 中挑选契合业务语义的图标，同一分组内图标不雷同
- `color`：从 9 色板挑选 HEX 色值
- `fields`：紧凑字符串数组 `["字段名(Type)", ...]`（见下方字段规范）
- `views`：紧凑字符串数组 `["视图名(Type)", ...]`（见下方视图规范）
- `businessRulesNotes`（可选）：字符串数组，使用纯自然语言描述业务规则（显隐、只读、校验、赋值）
- `consistencyNotes`（必填）：字符串，描述本表字段与视图/工作流/动作的一致性关系

> **⚠️ 主子表双向绑定闭环硬约束**：凡是在 `worksheets` 中声明了 `worksheetType: "subTable"` 的子表，其 `parentWorksheet` 所指定的主表中，**`fields` 数组必须 100% 包含一个 `"子表名(SubTable:子工作表名)"` 字段**！严禁出现孤立子表。

### 1. `fields` 字段定义语法

- **JSON 字符串数组**，每个元素使用紧凑格式 `"名称(Type)"`。
- **系统默认字段（创建时间/创建者/最近修改时间/最近修改人）严禁出现在 fields 数组中**。

#### 关联与衍生字段语法：
1. **关联字段**：`"字段名(Relation:目标表名:基数:方向)"`：
   - `基数`：`single`（单条关联，多对一）或 `multiple`（多条关联，一对多/多对多）。
   - `方向`（三态标识，按业务角色准确标注）：
     - `:uni`（单向引用）：仅在本表创建单向选择下拉/卡片，目标表**不生成反向字段**。适用于字典、主数据引用（如单据选仓库、明细选商品、单据选供应商）。
     - `:bi`（双向主创建端）：**主动发起双向关联**，API 开启 `bidirectional: true`，HAP 将**自动在目标表生成反向 Tab 标签页表格（tabTable）**。适用于主从从属端发起（如请假单关联审批、订单关联客户）或多对多主动发起端（如项目关联员工）。
     - `:reverse`（双向反向承接端）：**单边声明铁律**——当对端表已声明了指向本表的双向关联（或主表已声明了 `SubTable`）时，本表若需在表单标签页中透视该关联，必须标记 `:reverse`（如 `"名下订单(Relation:订单:multiple:reverse)"`）。`:reverse` 字段不占用物理表单网格空间，建表引擎在处理时会自动跳过 API 调用，完全由对端的 `:bi` 自动带出，**严禁双边重复主动声明双向关联！**
2. **自关联**：`"字段名(selfRelation)"`，如 `"上级分类(selfRelation)"`。
3. **子表字段**：`"字段名(SubTable:子工作表名)"`，如 `"采购明细(SubTable:采购明细表)"`。每张子表必须且只能被其主表（`parentWorksheet`）在 `fields` 中声明一次 `SubTable` 字段。
4. **【强约束】主子表必配 Rollup（汇总）**：凡主表中声明了 `SubTable` 或多条关联，主表**必须至少配 1~2 个 `Rollup` 字段**计算总金额或总数量：`"字段名(Rollup:关联字段名.目标字段名.汇总方式)"`，如 `"明细总金额(Rollup:采购明细.金额.sum)"`。`汇总方式` 为 `sum/count/avg/max/min`。
5. **【按需推荐】存储型 Lookup 字段**：仅当带出字段需参与本表二次计算、视图分组筛选或审批工作流分支时才创建：`"字段名(Lookup:关联字段名.目标字段名)"`，如 `"参考单价(Lookup:关联商品.销售单价)"`。
6. **【强烈推荐】业务单据标题必配 Concatenate**：对于流水单据、流转记录，`isTitle` 标题字段强烈推荐使用组合文本：`"字段名(Concatenate)"`，如 `"借阅摘要(图书-借阅人)(Concatenate)"`。
7. **特殊输入控件**：电子签名 `Signature`、条码二维码 `Barcode`。
8. **选项字段**：`SingleSelect` / `MultipleSelect` / `Dropdown` 必须携带选项值，用 `/` 分隔：`"状态(SingleSelect:待处理/进行中/已完成/已逾期)"`。

#### 字段丰富度与 8 维度覆盖：
- **最低字段数量**：主数据表 **≥ 15 个**，业务单据表 **≥ 12 个**，过程流水表 **≥ 8 个**，子表 **≥ 3 个**；
- **8 维度覆盖**：每张表必须覆盖主标识、核心业务属性、状态分类、时间、责任协作、数量金额、说明凭证、**计算与衍生**共 8 个维度。

### 2. `views` 视图定义语法

- **JSON 字符串数组**，紧凑格式 `"视图名(Type)"`。
- **视图与字段必须闭环**：视图类型所依赖的字段必须在 `fields` 中存在（如 Kanban 需选项字段、Calendar/Gantt 需日期字段、Hierarchy 需自关联、Map 需定位字段）。
- **类型枚举**：`Table`, `Kanban`, `Calendar`, `Gantt`, `Gallery`, `Detail`, `Hierarchy`, `Map`, `Resource`。

---

## 二、`customPages`（自定义页面数组）

每个元素包含：
- `name`：页面名称
- `groupName`：所属导航分组名称（必须在 `navGroups` 中覆盖）
- `type`：`"dashboard"`（仪表盘，看数据）或 `"workspace"`（工作台，办事情）
- `description`：页面业务目的与目标用户描述
- `icon`：`dashboard` 固定使用 `"sys_control-panel_traffic"`，`workspace` 固定使用 `"2_3_statistics"`
- `color`：HEX 配色
- **`charts`（仅 `type="dashboard"` 必填）**：
  - 建议 **6~10 个图表**，固定包含 1 个 `FiltersGroup`、4~6 个 `NumberChart`（KPI）、2~6 个业务图表（趋势/占比/排行）、1~2 个 `PivotTable`。
  - **FiltersGroup 格式**：`"全局筛选(FiltersGroup:筛选维度1,筛选维度2)"`（如 `"全局筛选(FiltersGroup:创建时间,订单状态)"`）。
  - **图表类型枚举**：`NumberChart`, `GaugeChart`, `ProgressChart`, `ColumnChart`, `BarChart`, `LineChart`, `DualAxisChart`, `PieChart`, `FunnelChart`, `RankingChart`, `SymmetricBarChart`, `RadarChart`, `ScatterChart`, `PivotTable`, `RegionMap`, `WorldMap`, `WordCloud`。
- **`components`（仅 `type="workspace"` 必填）**：
  - 建议 **4~6 个 Button + 2~4 个 View**。
  - 紧凑格式：`"名称(Type)"`，Type ∈ `Button`(新建/跳转), `View`(内嵌待办), `Text`, `Carousel`(展示推荐), `Section`。

---

## 三、`customActions`（自定义动作按表分组数组）

按工作表分类的数组，每个元素包含 `worksheet`（工作表名称）和 `actions`（动作对象数组）：
```json
{
  "worksheet": "销售订单",
  "actions": [
    {
      "name": "提交审批",
      "description": "销售员填写完毕后发起主管审批",
      "type": "triggerWorkflow",
      "enableCondition": "订单状态为待提交",
      "intentHints": [
        { "label": "自动流转至直属部门主管审批" },
        { "label": "审批通过后将订单状态更新为已生效" }
      ]
    },
    {
      "name": "确认发货",
      "description": "库管员核对后确认出库发货",
      "type": "updateCurrentRecord",
      "enableCondition": "订单状态为已生效"
    }
  ]
}
```

### 动作对象属性规范：
- `name`：动作名称
- `description`：由谁在什么场景下点击，以及需要填写什么
- `type`：`"updateCurrentRecord"` / `"createRelatedRecord"` / `"triggerWorkflow"`
- `targetWorksheet`：仅 `type="createRelatedRecord"` 时填目标工作表名
- `relateFieldName`：仅 `type="createRelatedRecord"` 时填，源工作表中用于物理关联目标表的关联字段名称（该字段必须在源表 `fields` 中显式存在）
- `enableCondition`（可选）：按钮的前置状态条件描述
- `intentHints`：`type="triggerWorkflow"` 时必须填写业务效果与约束数组（`[{ "label": "..." }]`）

> **审批自检（严禁违反）**：严禁创建「审批通过」「审批驳回」等直接操作审批结果的自定义动作。审批流统一创建 `triggerWorkflow` 类型的动作（如「提交审批」），由工作流内部的审批业务块 (`approval_block`) 处理通过/驳回。

---

## 四、`workflows`（系统自动化工作流数组）

工作流数组中每个元素包含：
- `name`：工作流名称
- `description`：业务流转逻辑说明
- `trigger`：触发器对象：
  - `type`：`"worksheet_event"`（数据增删改） / `"schedule"`（定时） / `"date_field"`（日期到达）
  - `source`：`worksheet_event` 与 `date_field` 填关联工作表名，`schedule` 填 `""`
  - `label`：触发条件自然语言描述
- `intentHints`：业务效果与约束对象数组（`[{ "label": "..." }]`），描述目标与边界，不写具体节点步骤，不硬编码选项值。

---

## 五、`roles`（角色权限数组）

每个元素包含：
- `name`：角色名称（如 `"销售经理"`, `"仓库管理员"`）
- `description`：角色的职责定位与权限范围说明
- `roleScope`：角色类型。`"general"`（组织内部角色，默认）或 `"externalPortal"`（外部门户角色）
- `permissions`：紧凑字符串数组，格式 `"名称(worksheet)"`、`"名称(customPage)"`、`"名称(aiAssistant)"`。

---

## 六、`aiAssistants`（AI 智能助手数组）

每个元素包含：
- `name`：助手名称（如 `"销售智能问答助手"`）
- `groupName`：所属导航分组名称（必须在 `navGroups` 中覆盖）
- `description`：一句话说明助手的服务场景与能力范围
- `icon`：固定使用 `"17_6_reddit"`
- `color`：HEX 配色（偏紫色系）

---

## ⚠️ 提交前闭环自检清单

1. **`navGroups` 100% 覆盖**：所有工作表、自定义页面、AI 助手的 `groupName` 必须全部出现在 `navGroups` 中；
2. **主子表闭环**：所有 `worksheetType: "subTable"` 的子表，其主表 `fields` 中必须包含对应的 `SubTable` 字段，且主表至少包含 1 个 `Rollup` 汇总字段；
3. **关联三态单边声明**：`:bi` 仅由单边主动发起，反向展示端声明 `:reverse`，主数据引用声明 `:uni`，严禁双边重复 `:bi`；
4. **视图/规则闭环**：所有视图筛选条件与业务规则引用的字段及选项值，在 `fields` 中 100% 存在；
5. **动作工作流闭环**：所有 `type="triggerWorkflow"` 的自定义动作，均包含完整的 `intentHints`。
