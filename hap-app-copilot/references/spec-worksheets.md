# 工作表与字段定义平台规格 (spec-worksheets)

本文档是 HAP（明道云）平台关于 **工作表参数规则**、**字段设计与选型决策**、**关联与衍生体系（Relation / SubTable / Lookup / Rollup / CascadingSelect）**、**12 栅格排版体系**、**选项与色彩映射**、**默认值** 与 **表单体验增强设置** 的权威设计与技术规范。

---

## 目录

1. [工作表参数规则 (Worksheet Settings)](#一-工作表参数规则-worksheet-settings)
2. [字段设计业务思考与选型决策](#二-字段设计业务思考与选型决策)
3. [字段通用控制属性与约束 (Field Controls)](#三-字段通用控制属性与约束-field-controls)
4. [Date / DateTime / Time 显示格式 (Moment.js)](#四-date--datetime--time-显示格式-momentjs)
5. [alias 命名与跨表关联防冲突规范](#五-alias-命名与跨表关联防冲突规范)
6. [Divider 业务分段规范](#六-divider-业务分段规范)
7. [表单 12 栅格排版规则 (Layout)](#七-表单-12-栅格排版规则-layout)
8. [选项字段规范与色彩映射体系 (SingleSelect / MultipleSelect / Dropdown)](#八-选项字段规范与色彩映射体系-singleselect--multipleselect--dropdown)
9. [Relation 跨表关联字段规范](#九-relation-跨表关联字段规范)
10. [关联衍生与层级控件规范 (SubTable / Lookup / Rollup / CascadingSelect / Formula)](#十-关联衍生与层级控件规范-subtable--lookup--rollup--cascadingselect--formula)
11. [默认值 (defaultValue) 4 种 source 规范](#十一-默认值-defaultvalue-4-种-source-规范)
12. [字段辅助文本规范 (placeholder, desc, remark)](#十二-字段辅助文本规范-placeholder-desc-remark)
13. [工作表设置与表单体验增强规范 (update_worksheet_settings)](#十三-工作表设置与表单体验增强规范-update_worksheet_settings)

---

## 一、 工作表参数规则 (Worksheet Settings)

### 1.1 remark（必填，开发者/AI 注释）
面向开发者/AI 的工作表描述。根据 Plan 中该工作表的 `description`，生成一句简洁的描述，说明该表的业务定位与核心用途。

### 1.2 desc（必填，用户使用说明，原生 HTML 规范）
面向用户的工作表使用说明，在标题旁显示帮助图标，hover 时显示；当同时设置了 importantNote 时，desc 变为"详情"链接展开显示（**必须使用原生 HTML，禁止使用 Markdown**）。每张表都应生成一段简明的使用指南，根据表的业务特征涵盖以下要点（按实际情况裁剪，不硬凑）：
- 该表的核心用途和适用场景（这张表管什么、谁来用）；
- 数据的生命周期或流转路径（如"新建 → 审核 → 归档"）；
- 当有 importantNote 时，desc 中应包含其**详细说明**：哪些字段由系统/工作流自动维护、具体触发条件是什么等，作为 importantNote 一句话警告的展开补充。

> ⚠️ **只用 `<p>`、`<strong>`、`<br>` 标签**，禁止 `<div>`/`<ul>`/`<li>` 等嵌套结构。严禁输出 `&lt;p&gt;` 等转义实体。

### 1.3 importantNote（按需生成，重要提示文本）
显示在工作表标题下方的重要提示文本（始终可见）。**大部分表不需要设置**——当表存在以下典型场景时才设置，否则留空：
- 表中包含由工作流/系统自动更新的状态字段 → 提醒 `"状态字段由系统自动维护，请勿手动修改"`；
- 表的数据依赖其他表的前置数据（如报销单需先有关联项目）→ 提醒 `"请先在项目表中创建对应项目"`；
- 表涉及审批流程（从 plan 工作流方案推断）→ 提醒 `"提交后将进入审批流程，请确认信息无误后再提交"`；
- **`importantNoteColor`**：固定使用 `"#515151"`（深灰）。

### 1.4 addRecordButtonName（新建按钮名词定制）
设置新建记录按钮的自定义名称。界面已自带「+」号，**只写名词对象名称，不要带"新建/新增/添加"等动词**（默认是"记录"）：
- ✅ 正例：`"任务"`（界面呈现为「+ 任务」）、`"订单"`、`"客户"`
- ❌ 反例：`"新建任务"`（会导致「+ 新建任务」重复动词）

### 1.5 displayType（子表隐藏铁律）
- **子表（`worksheetType === "subTable"`）**：子表数据随主记录创建/删除，仅通过主表表单内的 `SubTable` 控件进行内嵌维护，不在应用左侧/顶部导航栏独立展示。建表时必须显式设置 `displayType: 2`（隐藏工作表）；
- **普通工作表（`worksheetType` 为 `normal` 或未设置）**：正常在导航栏展示，传 `displayType: 1` 或省略。

### 1.6 createDefaultView（固定 false）
固定设置为 `false`，禁止自动创建默认视图。视图在后续步骤中单独创建和配置。

---

## 二、 字段设计业务思考与选型决策

### 2.1 字段设计 8 大维度完整性（必须覆盖）
设计一张工作表字段时，必须对照以下 8 个维度依次补齐。**每个维度至少覆盖 1 个字段**，不得遗漏：

| 维度 | 说明 | 典型字段与类型 |
|---|---|---|
| ① **主标识** | 名称、编号、标题——让用户一眼识别该条记录 | 标题 (`Text`)、订单号 (`AutoNumber`)、单据全称 (`Concatenate`) |
| ② **核心业务属性** | 体现行业特征与业务深度的属性信息（最易被遗漏） | ISBN/出版社 (`Text`)、规格型号 (`Text`)、联系人 (`Text`)、所属行业 (`SingleSelect`/`Relation`) |
| ③ **状态与分类** | 驱动视图看板与自动化工作流流转的枚举 | 审批状态 (`SingleSelect`)、业务分类 (`Dropdown`)、紧急程度 (`SingleSelect`)、是否有效 (`Checkbox`) |
| ④ **时间维度** | 业务相关的时间节点（无需重复创建 ctime/utime） | 计划开始/结束 (`Date`/`DateTime`)、预约时段 (`Time`)、完成时间 (`DateTime`) |
| ⑤ **责任与协作** | 确定数据权限范围与通知推送对象 | 负责人 (`Collaborator`)、所属部门 (`Department`)、承办角色 (`Role`) |
| ⑥ **数量与金额** | 数量、金额、统计值——支撑工作流加减与汇总运算 | 单价/总额 (`Currency`)、库存数量/工时 (`Number`)、服务评分 (`Rating`) |
| ⑦ **说明与凭证** | 详情描述、凭据文件与签名确权 | 图文说明 (`RichText`)、合同扫描件 (`Attachment`)、验收确认 (`Signature`) |
| ⑧ **计算与衍生** | 系统自动计算/引用/汇总，用户无需手动填写 | 金额计算 (`Formula`)、逾期天数 (`DateFormula`)、带出单价 (`Lookup`)、明细总额 (`Rollup`)、条码 (`Barcode`) |

### 2.2 标题字段规范（isTitle）
每张工作表**有且仅有一个**标题字段（`isTitle: true`）。选择规则：
- 仅以下类型可设为标题：`Text`, `AutoNumber`, `Date`, `DateTime`, `PhoneNumber`, `Email`, `Concatenate`；
- **【强烈推荐】业务单据/流转记录 标题必配 `Concatenate`（文本拼接）**：对于没有天然单一短名称的业务单据/流转记录（如借阅记录、调拨单、维修工单、会议预约、审批申请、巡检记录），标题强烈推荐使用 `Concatenate` 自动拼接核心维度（如 `"$biz_code$ - $biz_customer_name$"`），避免标题单薄；
- **严格禁止**把人员(`Collaborator`)、部门(`Department`)、角色(`Role`)、定位(`Location`)、附件(`Attachment`)、关联(`Relation`)、富文本(`RichText`)、单选/多选等控件设为标题；
- 若表内没有天然标题字段，必须显式新建一个 `Text`、`AutoNumber` 或 `Concatenate` 字段作为标题。

### 2.3 字段类型选型决策清单

对照业务数据特征与使用场景，严格按照以下规则选型，严禁滥用 `Text`：

* **自由输入短文本** → `Text`
* **带格式长文本 / 制度条款 / 图文介绍** → `RichText`
* **普通数值 / 数量 / 工时 / 计量** → `Number`
* **金额 / 单价 / 预算 / 费用** → `Currency`
* **固定单值枚举（≤ 5 项，状态/优先级）** → `SingleSelect`
* **固定多值枚举（≤ 10 项，多标签）** → `MultipleSelect`
* **选项较多需搜索 / 下拉选择（> 5 项）** → `Dropdown`
* **单个确认 / 是与否开关** → `Checkbox`（严禁用 SingleSelect 选"是/否"）
* **1～10 级评分 / 满意度** → `Rating`
* **只要日期、年、年月** → `Date`
* **具体时刻点（含时分秒）** → `DateTime`
* **纯时间段（不含年月日）** → `Time`
* **手机号码** → `PhoneNumber`
* **固定电话 / 座机** → `LandlinePhone`
* **电子邮箱** → `Email`
* **地理位置 / GPS 坐标打卡** → `Location`
* **省市区行政区划（三级级联）** → `Region`
* **负责人 / 经办人 / 审批人** → `Collaborator`（严禁用 Text 录入人员）
* **组织部门 / 业务科室** → `Department`
* **业务角色 / 权限组** → `Role`
* **跨表引用 / 关联独立实体** → `Relation`
* **本表父子层级（上级任务/父分类）** → `Relation`（自关联）
* **从属明细数据（随单据创建/销毁）** → `SubTable`
* **树形层级分类（多级品类/组织树）** → `CascadingSelect`
* **引用他表字段（只读/带入）** → `Lookup`
* **汇总关联数据（求和/计数/均值等）** → `Rollup`
* **数值计算（四则运算与复杂公式）** → `Formula`
* **日期差值 / 日期偏移 / 实时倒计时** → `DateFormula`
* **文本拼接组合（格式化全称/标题）** → `Concatenate`
* **单据流水号** → `AutoNumber`
* **材料 / 图片 / 文件附件** → `Attachment`
* **电子手写签名** → `Signature`
* **条形码 / 二维码生成** → `Barcode`
* **业务分段 / 折叠卡片标题** → `Divider`
* **自定义代码组件 / 交互卡片** → `CustomField`（详细技术契约与 React 代码生成规范详见 [spec-custom-fields.md](file:///Users/user/应用搭建skill/skills/hap-app-builder/references/spec-custom-fields.md)）

### 2.4 高级与衍生控件设计铁律

1. **【强约束】主子表必配 `Rollup`（汇总）**：凡是在主表中声明了 `SubTable`（如采购明细、合同明细、订单明细），主表**必须至少配 1~2 个 `Rollup` 字段**计算总金额或总数量，主表无汇总属于残缺设计；
2. **【按需推荐】存储型 `Lookup` 触发标准**：仅当带出字段需要作为存储数据参与金额公式计算、支撑本表视图分组/统计筛选，或工作流审批路由时才主动创建存储型 `Lookup`；仅查看关联记录直接依赖 `Relation` 卡片显示字段即可；
3. **`SubTable` vs `Relation` 选型决策**：明细从属于主记录、不独立管理使用 `SubTable`；全局共享独立管理的实体使用 `Relation`。

---

## 三、 字段通用控制属性与约束 (Field Controls)

### 3.1 字段控制属性对照表
| 属性 | 适用类型 | 说明 |
|---|---|---|
| `isTitle` | Text / AutoNumber / Date / DateTime / PhoneNumber / Email / Concatenate | 每张表**仅一个**字段可设为 true（标题字段），其他控件不支持作标题，否则建表失败 |
| `required` | 大多数输入字段 | 必填校验。**注意：AutoNumber、Formula、Collaborator、Divider 不得设为 true**，否则建表失败 |
| `isReadOnly` | 大多数 | 只读锁定，禁止前台用户手动修改 |
| `isUnique` | Text / Number / Email / PhoneNumber 等 | 唯一性校验，防止重复录入 |
| `isHiddenOnCreate` | 任意 | 新建记录时是否隐藏（由系统自动写入或工作流计算回填）|
| `precision` | Number / Currency / Formula / DateFormula / Rollup | 小数位数（0-14）|
| `max` | Rating | 最大评分值（1-10）|

### 3.2 特殊字段类型约束
- **`Collaborator` / `Department` / `Role` 组织字段**：通过 `config.isMultiple`（boolean）控制单选与多选；含"人/员/负责人/所属部门"等单数语义 → `false`；含"团队/参与人/相关部门"等复数语义 → `true`；
- **`Concatenate`（文本拼接）**：`config.expression` 必填拼接公式，引用其他字段用 `$alias$` 包裹，可加固定分隔符。示例：`"$biz_code$ - $biz_name$"` → 显示 "ORD-001 - 张三"。可作为标题字段（isTitle）；
- **`Signature`（电子签名）**：直接传 `type: "Signature"`，布局推荐 `span: 12`；
- **`Barcode`（条码）**：`config.displayMode` 可选 `"code128"`（一维码，默认）或 `"qrCode"`（二维码）；`config.expression` 必填生成公式，引用字段用 `$alias$`（如 `"$biz_auto_number$"`）。

### 3.3 required 必填约束禁区
AutoNumber、Formula、Divider、Collaborator **不得设置** `required: true`，否则工作表创建会失败。

### 3.4 Formula 公式引用规则
Formula 的 `expression` 中引用其他字段必须用 `$alias$` 包裹，不能用 `name`。先确定所有字段 alias，再写 expression。
- 示例：`"$biz_total_amount$ * (1 - $biz_discount_rate$)"`

### 3.5 AutoNumber 常用编号模板
- 纯流水号：`[{ type: "sequence", length: 6, repeat: "never" }]`
- 日期 + 流水：`[{ type: "createdTime", format: "yyyyMMdd" }, { type: "sequence", length: 4, repeat: "day" }]`
- 前缀 + 流水：`[{ type: "text", value: "ORD-" }, { type: "sequence", length: 6, repeat: "never" }]`

---

## 四、 Date / DateTime / Time 显示格式 (Moment.js)

Date / DateTime / Time 字段必须显式传 `config.format`，采用 Moment.js 格式符号（**注意：与 AutoNumber 的 .NET 格式不同，不要混用**）。根据字段名称的语言选择符合其地区习惯的年月日顺序和分隔符（如中文用"年月日"、美式用 `MMM D, YYYY`、欧式用 `D MMM YYYY`）。精度可按业务需要裁剪（仅年、年月、年月日、带时分、带秒均可）。无法判断时用 ISO 格式 `"YYYY-MM-DD"` 兜底。

> ⚠️ **唯一易错点**：大写 `D` = 日，小写 `d`/`dd`/`ddd` = 星期。写反会显示异常。排班、日程、考勤等场景建议追加 `ddd`。

常用模板：
- 中文：`"YYYY年M月D日"`，带时间：`"YYYY年M月D日 HH:mm"`，带星期：`"YYYY年M月D日 ddd"`
- 英文：`"MMM D, YYYY"`，带时间：`"MMM D, YYYY HH:mm"`，带星期：`"ddd, MMM D, YYYY"`
- ISO 兜底：`"YYYY-MM-DD"`，带时间：`"YYYY-MM-DD HH:mm"`
- 仅年：`"YYYY"`，年月：`"YYYY-MM"` / `"YYYY年M月"`
- 纯时间：`"HH:mm"`（默认），仅小时：`"HH"`，含秒：`"HH:mm:ss"`

---

## 五、 alias 命名与跨表关联防冲突规范

每个字段必须设置 `alias`，命名约定：
- 全局唯一前缀 `biz_`；
- **普通业务字段**：后缀由字段语义对应的英文短词组成（snake_case），如 `biz_visitor_name` / `biz_visit_time` / `biz_status`。同表内 alias 必须唯一；
- **跨表关联（Relation / SubTable）字段**：**别名必须带上本工作表的名称/别名缩写前缀**（格式为 `biz_<本表名缩写>_<目标表名/字段名>`，例如「补货建议」关联供应商为 `biz_advice_supplier`、「采购入库单」关联供应商为 `biz_inbound_supplier`），防止多张表关联同类主数据时别名重复与冲突。

---

## 六、 Divider 业务分段规范

每张表都应使用 Divider 分组字段，分段名必须结合业务语义生成：
- 先按字段语义分组，再提炼分段名；
- 名称简洁自然，通常 2～6 个字，优先使用业务词（每张表建议 2～5 个 Divider，每组建议 3～8 个字段）；
- 附件、备注、说明、归档类内容放最后；
- ❌ **禁止使用空泛模板名**：`基本信息`、`归属与协作`、`计划与进度`、`审批与治理`、`备注与附件`；
- ✅ **应根据业务内容自然命名**：
  - 客户表：`客户资料`、`联系信息`、`跟进情况`
  - 合同表：`合同主体`、`签约安排`、`履约信息`
- Divider 固定属性：`required: false`，`layout: { rowIndex: N, span: 12 }`（N 按当前行号递增）。

---

## 七、 表单 12 栅格排版规则 (Layout)

每个字段的 `layout` 必须同时传 `rowIndex`（行号，从 0 开始递增）和 `span`（列宽）。

> [!CAUTION]
> **只有 `rowIndex` 相同的字段才会显示在同一行。** `rowIndex` 不同则一定分行，与字段数组顺序无关。同一行内各字段的 `span` 之和必须 = 12。

### 7.1 span 取值与每行字段数 (3 / 6 / 12)
**只允许三种值：3 / 6 / 12，禁止使用 4、8。**

| 每行字段数 | span | 说明 |
|---|---|---|
| 1 个字段独占 | 12 | 独占一行 |
| 2 个字段同行 | 6 | 两个字段设相同 rowIndex |
| 4 个字段同行 | 3 | 四个字段设相同 rowIndex |

❌ 不允许一行 3 个字段（span:4）

### 7.2 rowIndex 分配示例
```json
// Divider 独占一行
{ "alias": "div_basic", "type": "Divider", "layout": { "rowIndex": 0, "span": 12 } },
// 两个字段并排 (6 + 6 = 12)
{ "alias": "biz_name",   "layout": { "rowIndex": 1, "span": 6 } },
{ "alias": "biz_code",   "layout": { "rowIndex": 1, "span": 6 } },
// 四个字段同行 (3 + 3 + 3 + 3 = 12)
{ "alias": "biz_phone",  "layout": { "rowIndex": 2, "span": 3 } },
{ "alias": "biz_email",  "layout": { "rowIndex": 2, "span": 3 } },
{ "alias": "biz_date",   "layout": { "rowIndex": 2, "span": 3 } },
{ "alias": "biz_number", "layout": { "rowIndex": 2, "span": 3 } },
// 独占一行
{ "alias": "biz_remark", "layout": { "rowIndex": 3, "span": 12 } }
```

### 7.3 强制独占整行的字段类型
Divider、RichText、Attachment、Relation（displayMode 为 inlineTable / tabTable 时）、SubTable → 必须 `span: 12`，独占一个 `rowIndex`。
> Relation（displayMode=dropdown/card）时可与其他字段并排，其中 dropdown 推荐 span=3/6，card 推荐 span=6/12。

### 7.4 语义成组成对排版（同行并排）
紧凑字段（dropdown、Number、Currency、Date、PhoneNumber、Email、AutoNumber）优先 4 个一行（span:3，相同 rowIndex）；仅当语义上天然成对时才 2 个一行（span:6）。
- **span:3 示例（优先）**：数量 + 单价 + 金额 + 折扣率；联系电话 + 邮箱 + 入库日期 + 编号
- **span:6 示例（语义成对）**：开始时间 + 结束时间；状态 + 优先级；负责人 + 所属部门

---

## 八、 选项字段规范与色彩映射体系 (SingleSelect / MultipleSelect / Dropdown)

选项类控件（`SingleSelect`、`MultipleSelect`、`Dropdown`）统一遵循以下配置规范：

### 8.1 选项值解析与来源
- Plan 中的选项字段格式为 `"字段名(SingleSelect:选项1/选项2/选项3)"` 或 `"字段名(Dropdown:选项1/选项2)"`；
- **必须严格使用 Plan 中指定的选项值**，不要自行增减或改名——视图筛选和工作流均依赖确切的选项名称；
- 若 Plan 未携带选项值（如只写了 `"状态(SingleSelect)"`），根据业务语义自行补全真实业务选项，**绝对禁止**使用"选项1"、"选项2"等占位文本；
- 解析为 `options` 数组，每项包含 `index`（从 1 递增的整数）和 `value`（选项文本）。

### 8.2 isColorOptions 必须显式设置（硬约束）
每个选项字段必须在 `config` 对象中显式配置 `isColorOptions` 布尔值：
- **彩色选项**：必须设置 `config: { isColorOptions: true }`，同时 `options` 数组中的每个选项**必须带有 `color` 属性**（十六进制 HEX 颜色）；
- **非彩色选项**：必须设置 `config: { isColorOptions: false }`，`options` 数组中的选项**不得携带 `color` 属性**。

### 8.3 颜色映射与分类适用规则
- **必须使用彩色（`isColorOptions: true`）的场景**：状态、处理阶段、优先级、紧急程度、风险等级、审批结果等具有明显进度、情感倾向或告警意义的字段：
  - 负面 / 失败 / 拒绝 / 紧急 / 严重 → `#F52222`（红）
  - 正面 / 完成 / 通过 / 正常 → `#00C345`（绿）
  - 警告 / 待处理 / 待审核 / 中等 → `#FAD714`（黄）
  - 进行中 / 处理中 / 执行中 → `#2D46C4`（蓝）
  - 取消 / 归档 / 已作废 / 停用 → `#484848`（灰）
  - 调色盘备用集：`#C0E6FC` `#C3F2F2` `#00C345` `#EAB308` `#FF9300` `#F52222` `#EB2F96` `#7500EA` `#2D46C4` `#484848`
- **必须使用无色（`isColorOptions: false`）的场景**：纯业务分类、数据字典、行业类别、渠道来源、部门类别等中性无倾向的分类/标签字段。

---

## 九、 Relation 跨表关联字段规范

### 9.1 Relation 参数设置全集
每个 Relation 字段必须同时包含 `dataSource`、`config.isMultiple`、`config.bidirectional`、`config.displayMode` 四个属性。`displayMode` 非 `dropdown` 时，`config.showFields` 不得为空。

1. **`dataSource`**（字段顶层属性，非 config 内）：
   - **自关联（关联本表自身）**：填 `"selfRelation"`；
   - **跨表关联**：填目标表的真实 `worksheetId`（24 位 hex）；
   - **严禁**自行编造 ID，严禁从 plan 中直接复用任何未创建表的 ID；
   - **⛔ 严禁把跨表关联伪装为自关联**：`(Relation:xxx)` 格式的跨表关联字段在未建好目标表时严禁赋 `"selfRelation"`。
2. **`config.isMultiple`**（必填）：
   - `true`：一对多 / 多对多关联（一条记录可关联多条目标记录）；
   - `false`：多对一关联（一条记录只关联一条目标记录）；
   - 自关联（`dataSource: "selfRelation"`）时**必须设为 `false`**。
3. **`config.bidirectional`**（必填）：
   - 根据业务推导：`true` 为双向并在目标表生成反向字段，`false` 为单向引用；
   - 自关联（`dataSource: "selfRelation"`）时**必须设为 `true`**。
4. **`config.displayMode`**（必填，严禁省略）：

| displayMode | 适用场景 | 对应表类型 | 备注与布局 |
|---|---|---|---|
| `dropdown` | 关联目标是**字典/分类/标签表**（数据源表），仅选择引用、无需展示详情 | 如 `图书类型`、`客户级别`、`任务状态` | 条目少、结构简单，`span: 3/6` |
| `card` | 关联目标是**核心业务表**（实体表），需展示关键字段（**默认推荐**） | 如 `图书清单`、`订单`、`客户`、`项目` | 可设 coverField，`span: 6/12` |
| `inlineTable` / `tabTable` | 一对多且需集中展示 | 业务明细、子项清单 | **固定 `span: 12`** |

5. **`config.showFields`**（条件必填）：
   - `displayMode` 为 `card` → **必须 ≥ 2 个**，推荐 2-4 个（**必须包含目标表的标题字段**，挑选最具业务识别度的字段如编号、名称、金额、状态，排除富文本、附件等复杂控件）；
   - `displayMode` 为 `inlineTable` / `tabTable` → **必须 5-10 个**；
   - `displayMode` 为 `dropdown` → 不需要；
   - 取值：目标表中最具业务识别度的字段真实 `alias` 列表。
6. **`config.coverField`**（条件必填）：
   - 仅 `displayMode === "card"` 时有效；
   - 当目标表有附件字段，且该附件是记录的核心视觉标识（如产品主图、用户头像、房源照片、设备外观、Logo）时设置；
   - 以下场景**不设** coverField（缩略图无辨识意义）：操作截图、纯文档类附件（合同 PDF、报告、表格）、签名/回执。

### 9.2 关联关系模型与双向生成规则

> [!IMPORTANT]
> **平台双向关联机制**：
> 明道云在工作表中创建双向关联（`bidirectional: true`）或明细子表（`SubTable`）控件时，**底层会自动在目标关联表中生成对应的反向关联控件**。

1. **明细子表 (SubTable) 关系模型**：
   - 明细子表控件由主表（父表）承载并配置；
   - 主表添加子表控件后，从属子表会自动获得指向主表的父级关联，**子表不可且无需单独定义指向主表的关系控件**。
2. **双向关联 (Relation) 仲裁模型**：
   - 若两张表之间存在双向业务联系（且均未显式指定 `:reverse`）：
   - **以从属端/单条引用端（`isMultiple: false`）作为关系主定义表**；主表/多条端作为反向宿主表（自动承接反向卡片/Tab 列表），避免关系双向冗余定义；
   - 若双方引用基数相同（均为多对多或均为一对一），以业务发起方或前置表为主定义方。
3. **反向透视字段 (:reverse)**：
   - 标记为 `:reverse` 的字段属于展示层反向透视定义（详情页 Tab 列表），其底层控件由对端双向关联创建时自动生成，**不作为独立的新增关系控件定义**。

### 9.3 别名冲突安全处理规范
- 遇到 `别名重复`、超时或写入结果不明确时，必须先回读目标表，确认字段是否已创建/修改，禁止盲目重试。
- **Build 新建场景**：仅对尚未被引用的全新字段，可省略冲突 alias 或生成确定性唯一 alias；取得真实 `fieldId` 后，必须同步修正同批 Lookup / Rollup 的 `relationField`。只有确认上次写入未生效时才可有限重试。
- **Modify 存量场景**：遵循 `workflows/modify.md` 的实时读取与范围控制规则。已有字段或已被公式、Lookup、Rollup、工作流、页面引用的 alias 禁止静默丢弃或替换；必须停止、报告依赖，并在范围变化后重新判断风险和确认要求。

---

## 十、 关联衍生与层级控件规范 (SubTable / Lookup / Rollup / CascadingSelect / Formula)

### 10.1 SubTable 明细子表控件规范
明细子表（如采购明细、报销明细、评分项、打卡记录）以行内明细表格的形式嵌入主表表单中：
- `type: "SubTable"`, `dataSource: "<目标子表ID>"`, `config.displayMode: "SubTable"`；
- **`span: 12` 独占整行**，通常排在主表表单末尾；
- **子表工作表本身必须固定设置 `displayType: 2`（全部隐藏）**，不在侧边栏暴露入口；
- `config.bidirectional`: 固定 `true`；
- `config.showFields`: **必填 2~4 个子字段 alias**（排除富文本、附件等复杂类型）；
- ⚠️ **不需要** `displayMode`、`isMultiple` 等 Relation 专属属性；
- ⚠️ **子表端不需要且严禁再次创建指向主表的关联字段**。

### 10.2 Lookup 他表字段引用规范
Lookup 用于通过已建立的关联关系，自动从关联记录中带出指定字段的值并在本表中引用：
- **单条关联约束**：必须挂载在单条关联（`isMultiple: false`）字段上，不支持多条关联；
- **存储型 vs 动态引用决策**：
  - **开启存储副本（`storeData: true`）**：仅当带出字段需要参与本表公式计算（如引用单价计算总价）、支撑视图筛选/分组、或用于工作流审批路由时开启；
  - **动态只读引用（`storeData: false`）**：纯查看场景使用动态引用，或优先直接通过关联卡片显示字段展示，避免创建冗余字段。

### 10.3 Rollup 跨表汇总计算规范
Rollup 用于通过关联关系，对关联的多条记录进行跨表统计聚合：
- `type: "Rollup"`, `relationField: "<关联或SubTable字段alias或ID>"`, `sourceField: "<目标表度量字段alias或ID>"`, `precision: 0~14`；
- **`config.calcType`** 聚合函数枚举：
  - `"sum"`：求和（数值/金额字段）
  - `"count"`：计数（统计关联记录条数）
  - `"avg"`：平均值
  - `"max"`：最大值
  - `"min"`：最小值

### 10.4 Concatenate 跨表复合文本拼接
- `type: "Concatenate"`, `name: "<字段名>"`, `alias: "<alias>"`, `layout: { rowIndex, span }`；
- `config.expression`: 公式必须用 `$alias$` 包裹（如 `"$biz_order_code$ - $biz_customer_name$"`）；
- **可作为标题字段（`isTitle: true`）**。

### 10.5 Formula 跨表复合数值公式
- `type: "Formula"`, `name: "<字段名>"`, `alias: "<alias>"`, `precision: 2`, `layout: { rowIndex, span }`；
- `config.expression`: 引用本表基础字段、Lookup 引用字段或 Rollup 汇总字段进行复合数学计算，变量用 `$alias$` 包裹（如 `"$biz_rollup_amount$ * (1 - $biz_discount_rate$)"`）。

### 10.6 CascadingSelect 级联选择规范
CascadingSelect 用于在具有层级树形自关联的数据源表中进行多级联动选择（如行政区划、多级商品类目、多层级组织架构）：
- `type: "CascadingSelect"`, `dataSource: "<目标层级表ID>"`, `viewId: "<目标表树形视图ID>"`, `layout: { rowIndex, span }`；
- **`config.displayMode`**：`"cascader"`（级联下拉菜单）或 `"tree"`（树形展开弹窗）。

---

## 十一、 默认值 (defaultValue) 4 种 source 规范

### 11.1 何时设置与业务场景
默认值用于减少重复填写、提升录入效率。只有字段存在明确、稳定、可预期的初始值时，才建议设置。优先在以下场景设置默认值：

| 场景 | 做法 |
|---|---|
| 负责人字段 → 默认为当前操作用户 | `source: "system", value: "currentUser"` |
| 创建日期 → 默认为今天 | `source: "system", value: "now"` |
| 状态字段 → 有明确的初始状态（如"待处理"） | `source: "static", value: "待处理"` |
| 同一表单中的字段值 → 默认取当前表单内其他字段的值 | `source: "field", field: "startTime"`（如：结束时间默认取开始时间） |
| 选择关联记录后 → 自动带出该关联记录中的字段值 | `source: "relation", relationField: "customer", field: "phone"`（如：选客户后带出联系电话） |

### 11.2 4 种 source 使用规则
- **`system`**：用于系统内置值，如当前用户、当前时间、当前定位
- **`static`**：用于固定值，如状态默认"待处理"
- **`field`**：用于当前表单内其他字段的值
- **`relation`**：用于已选关联记录中的字段值

> **设计原则**：优先用于高频、重复、规则明确的填写场景；以减少输入成本为目标；不确定、易变化、依赖人工判断的字段不设默认值。

### 11.3 各字段类型支持范围矩阵
| 字段类型 | 多值 | static | system | field/relation |
|---|---|---|---|---|
| Text | ✅ | ✅ | — | ✅ |
| Number / Currency | — | ✅ | — | ✅ |
| SingleSelect | — | ✅(选项名) | — | ✅ |
| MultipleSelect / Dropdown | ✅ | ✅ | — | ✅ |
| Date / DateTime | — | ✅(YYYY-MM-DD HH:mm:ss) | `now` | ✅ |
| Collaborator / Department | config.isMultiple | — | `currentUser` | ✅ |
| Role | config.isMultiple | — | — | ✅ |
| PhoneNumber / Email | — | ✅ | `currentUser` | ✅ |
| LandlinePhone | — | ✅ | — | ✅ |
| Region | — | — | — | ✅ |
| Rating | — | ✅(数字) | — | ✅ |
| Location | — | — | `currentLocation` | ✅ |

> ⚠️ AutoNumber / Formula / Attachment / Relation / Divider 不支持 defaultValue。

---

## 十二、 字段辅助文本规范 (placeholder, desc, remark)

### 12.1 placeholder（必填）
所有输入型字段**必须设置 placeholder**，引导用户了解应输入什么内容。
支持的字段类型：`Text`、`Number`、`Email`、`PhoneNumber`、`LandlinePhone`、`Dropdown`、`Date`、`DateTime`、`Time`、`Currency`。

| 字段类型 | placeholder 示例 |
|---|---|
| Text（名称类） | "请输入客户全称" |
| Text（描述类） | "请简要描述问题现象和影响范围" |
| Number | "请输入数量" |
| PhoneNumber | "请输入手机号" |
| Email | "请输入邮箱地址" |
| Date/DateTime | "请选择日期" |
| Dropdown | "请选择" |

### 12.2 desc（按需生成）
面向用户的字段输入说明，显示在字段下方。当字段有**特别的填写要求**或**选项含义需要解释说明**时生成：
- 字段有格式要求、精度要求、业务规则等 placeholder 无法承载的信息 → 用 desc 补充，**不重复** placeholder 已表达的内容；
- 选项字段（SingleSelect/MultipleSelect）的选项含义不直观、需要用户理解区别时 → 用 desc 解释各选项的适用场景；
- 不支持 placeholder 的字段（如 Relation、Rating 等）有特殊操作要求时 → 用 desc 引导；
- Checkbox 字段勾选/不勾选的业务含义不明显时 → 用 desc 说明勾选代表什么；
- Formula / AutoNumber 等只读字段 → 用 desc 解释计算逻辑或编号规则，帮用户理解显示值。

示例：金额字段 → "含税金额，精确到分"；关联字段 → "选择本次服务对应的客户"；Checkbox → "勾选表示已确认收货"；公式字段 → "由系统根据 单价×数量 自动计算"。
> **禁止**生成仅重复字段名称的 desc（如字段"性别"→ desc"请选择客户性别"），这类无额外信息的 desc 不如不设。

### 12.3 remark（必填）
面向开发者/AI 的字段注释。build 阶段**必须为每个字段生成**，用一句话描述字段的业务用途（如"记录客户首次联系日期，用于计算客户生命周期"、"关联订单表，用于回溯采购来源"）。如果字段被工作流读写或被视图筛选依赖，应一并注明。

---

## 十三、 工作表设置与表单体验增强规范 (update_worksheet_settings)

建表成功拿到 `worksheetId` 后，AI 应根据工作表的**业务定位、字段构成与流程场景**自主推定。**仅当命中以下有价值的体验特征时，按需调用 `update_worksheet_settings` 工具进行增强；子表或纯字典表直接跳过不调**：

### 13.1 封面大图 (form.cover)
当本表包含 `Attachment` 附件且字段语义适合作为详情页主视觉封面时（如商品主图、物料照片、房源实拍、头像、设备铭牌、设计效果图等），配置其为封面，**推荐指定 `height: 200 ~ 400`** ；

### 13.2 新建表单标题 (form.title)
针对业务单据或流程发起表单，动态定制动作化标题（如 `"发起采购申请"`、`"提交故障报修"`、`"录入新客户"`、`"起草业务合同"` 等），替代默认机械的“新建 xxx”；

### 13.3 关联 Tab 标签页呈现 (form.tabs)
固定开启 `hideWhenSingle: true`（单个标签页时自动隐藏 Tab 栏消除视觉噪音）；Tab 位置默认设为 `"top"`（顶部 Tab），当关联 Tab 较多时（>3 个，如客户 360 视图、项目总览）设为 `"left"`（左侧 Tab 导航）；

### 13.4 场景化提交行为与专业文案 (submission)
- **审批/流转单据**（如请假、报销、采购申请、立项等）：定制业务化提交按钮（如 `"提交审批"`、`"提交立项"`、`"提交报修"` 等），并配置提交后自动打开刚创建记录详情（`afterSubmit: openCreatedRecord`）；
- **高频录入/基础建档/流水登记表**（如商品档案、物料主数据、联系人名片、访客登记、设备巡检、电销跟进等）：开启连续提交（`continueCreation: { enabled: true, buttonLabel: "保存并继续添加" }`），方便批量连续录入；
- **登记/填报单据**：定制提交按钮为 `"确认登记"`、`"保存记录"` 等；
- **高风险/重大单据**（如资产报废、合同作废、调账出库等）：按需开启提交二次确认弹窗（`submitConfirmation`），提升系统严肃性与防错体验。
