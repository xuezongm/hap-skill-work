# 自定义页面与统计图表完整平台规格 (spec-pages-charts)

本文档是 HAP（明道云）平台关于 **自定义页面（Dashboard / Workspace）**、**48 栅格组件编排（filtersGroup、button、text、carousel、view、section）** 与 **图表内嵌配置（Inline Chart Config）** 的唯一权威事实源（SSOT），1:1 对齐官方生产级设计规范。

---

## 目录

1. [页面配置与字段 ID 来源约定](#一-页面配置与字段-id-来源约定)
2. [统计数据源选择原则（事实表 vs 维度表）](#二-统计数据源选择原则事实表-vs-维度表)
3. [页面结构组织（Dashboard 仪表盘 vs Workspace 工作台）](#三-页面结构组织dashboard-仪表盘-vs-workspace-工作台)
4. [48 栅格布局尺寸规范](#四-48-栅格布局尺寸规范)
5. [FiltersGroup 全局数据筛选器规范](#五-filtersgroup-全局数据筛选器规范)
6. [图表内嵌配置规范（Inline Chart Config）](#六-图表内嵌配置规范inline-chart-config)
7. [按钮组件规范 (button)](#七-按钮组件规范-button)
8. [轮播图组件规范 (carousel)](#八-轮播图组件规范-carousel)
9. [文本组件与精准高度公式 (text)](#九-文本组件与精准高度公式-text)
10. [图表类型选型速查与搭配原则](#十-图表类型选型速查与搭配原则)

---

## 一、 页面配置与字段 ID 来源约定

为每个自定义页面分别调用一次 `update_custom_page`。

### 字段 ID 来源
- `worksheetId`：优先取工作表 `alias`，无 alias 用 `id`；
- `viewId`：**每个图表必填**——HAP 图表建在某个视图之上，缺它会报 `viewId 不能为空`、导致**整页写入失败**。从 `viewContext` 里该工作表（按名称匹配到其 `worksheetId`）的 `views` 取一个**真实视图 id**：默认取该表的「全部」表视图（无则取第一个 `type=table` 的视图）。**绝不可省略、绝不可填空串、绝不用别名或视图名代替 id。**
- `dimension/values[].field`：优先取字段 `alias`，无 alias 用 `id`；计数固定传 `"rowid"`；
- **禁止凭空编造任何 ID，所有 ID 必须来自 `worksheetContext` / `viewContext`**。

---

## 二、 统计数据源选择原则（事实表 vs 维度表）

> [!CAUTION]
> **不能把维度表作为统计数据源，必须用事实表**。

- **事实表**：借阅记录、订单、工单、销售流水、考勤记录…… 每行代表一次业务事件；
- **维度表**：图书分类、商品类目、员工档案、客户档案、部门表…… 每行代表一个实体。

**正确做法**：在事实表上，以分类字段（Relation 字段或单选字段）作为维度分组，对事实行计数或求和。

| 分析目标 | ✅ 正确数据源 | ❌ 错误数据源 |
|---|---|---|
| 各分类借阅占比 | 借阅记录表（按分类字段分组） | 图书分类表 |
| 各客户订单量 | 订单表（按客户字段分组） | 客户档案表 |
| 各部门工单数 | 工单表（按部门字段分组） | 部门表 |

---

## 三、 页面结构组织（Dashboard 仪表盘 vs Workspace 工作台）

根据 `customPages` 的 `pageType`，采用不同的页面组织方式。

### 1. Dashboard（仪表盘）
页面按「筛选器 → 分段 + 统计」方式组织，阅读顺序：筛选器 → 核心指标 → 分析图表。

**标准结构**：
```
filtersGroup（全局数据筛选器，置于最顶部）           ← 筛选区（y=0, w=48, h=5）
section（核心指标）                                ← 分段区（w=48, h=2）
numberChart × 3~6                               ← KPI 指标区（w=12 或 w=8, h=7）
section（数据分析）                                ← 分段区（w=48, h=2）
lineChart / columnChart / barChart / pieChart ... ← 分析区（w=24 或 w=48, h=12）
```
- **必须**在最顶部放置 1 个 `filtersGroup` 筛选器组件；
- 必须包含 section 组件（2~3 个）；
- 必须同时包含 KPI（3~6 个）和分析图表（2~4 个）；
- KPI 必须在分析图表之前。

### 2. Workspace（工作台）
页面按「使用指南 → 快捷入口 → 核心指标 → 业务列表与辅助图表」方式组织，兼顾快捷操作与即时数据洞察。

**Plan 声明的核心组件（直接使用）**：
```
text（使用指南，含业务导引）         ← 顶部引导区（h=6~10），上方不加 section
button（一组 3~6 个快捷按钮）       ← 快捷入口区（紧接 text 下方，无独立 section，h=6）
view × 2~4                         ← 核心业务列表（分栏占左侧 67%，w=32, h=22）
```

**Build 自动扩展的辅助组件（基于 worksheetContext 推断）**：
```
section × 2~3                      ← 分段标题，命名具体反映业务主题，严禁模糊命名
numberChart × 4~6                  ← KPI 指标卡片区（横向等宽排列，每个 w=12 或 w=8，h=7）
chart × 2 per view                 ← 每个 View 右侧搭配 2 个辅助图表（上下垂直堆叠，w=16, h=11）
```

**自动扩展推断规则**：
1. **KPI 指标卡**（`numberChart`）：基于 Plan 中声明的所有 View 数据源工作表，选取 4~6 个最有业务价值的统计维度创建指标卡，集中放在第一个 Section 下方；
2. **辅助分析图表**：每个 View 右侧搭配 2 个图表（饼图+柱图/条形图），从该 View 的数据源工作表中选取有业务含义的维度字段（优先选：状态/类型等选项字段 → 时间字段 → 关联字段）；
3. **分栏布局**：View 占左侧 67%（`w=32, h=22`），2 个辅助图表占右侧 33%（`w=16, h=11`），上下垂直堆叠；
4. **Section 命名**：结合 View 的业务主题和辅助图表的分析维度，生成具体的分段标题（如 `变更审批与风险分析`、`重点项目跟进与工时分析`）；
5. **Text 使用指南**：根据页面操作路径复杂度选择列表式或分栏卡片式。

---

## 四、 48 栅格布局尺寸规范

所有组件基于 48 列栅格，`x + w ≤ 48`。

| 组件类型 | 推荐宽度 | 推荐高度 |
|---|---|---|
| `filtersGroup` | **固定**通栏 `w=48` | **推荐高度** `h=5`（`y=0` 置顶） |
| `section` | **固定**通栏 `w=48` | `h=2` |
| `numberChart` | 4 张一行 `w=12`；6 张一行 `w=8`（紧凑） | `h=7` |
| 分析图表（趋势/分布/对比） | 半宽 `w=24` 或通栏 `w=48` | 推荐高度 `h=12`（与 View 搭配时 `w=16, h=11`） |
| `pivotTable` | 固定通栏 `w=48` | 推荐高度 `h=12` |
| `button` | **固定**通栏 `w=48` | **固定高度** `h=6` |
| `view` | Dashboard 固定通栏 `w=48`；Workspace 分栏 `w=32`（左侧 67%） | 推荐高度 `h=22` |
| `text` / `carousel` | 单独出现时通栏 `w=48`；组合并排时各半宽 `w=24` | text 高度见第九节公式；carousel 单独时 `h=10`；并排时两者等高以 text 为准 |

**布局原则**：
- KPI 区同宽、同高、对齐排列；趋势图优先放分析区左侧或上方；
- 信息量大的图表/视图可用通栏，不强制半宽；
- 优先追求可读性和视觉平衡，不机械套坐标。

---

## 五、 FiltersGroup 全局数据筛选器规范

> [!CAUTION]
> **Dashboard 页面必须在最顶部配置 1 个 `filtersGroup` 组件。**

### 核心构建规则
1. **置顶布局**：固定位置 `x: 0, y: 0, w: 48, h: 5`，所有其他组件的 `y` 坐标从 `5` 开始往下排列；
2. **全量联动与 ID 规则**：
   - 页面中的**所有**图表和视图组件均须配置 `config.objectId`（36 位 UUIDv4），并在筛选器的 `objectControls` 中完成绑定；
   - **外层 `config.filtersGroupId`**：新建页面时**必须留空或不传**（由服务端自动生成）；
   - **内层 `filters[].filterId`**：**必须传入生成的 36 位 UUIDv4**；
3. **图表时间联动**：若 FiltersGroup 包含时间维度（如 `创建时间`/`ctime`），被联动的图表不设内置时间范围限制（设为全量），由筛选器统一控制；若无时间筛选器，图表自行配置合理的默认时间范围（如本月）；
4. **关键配置避坑**：
   - **平铺排在末尾**：`advancedSetting.direction="1"`（平铺）会独占整行，**必须将所有平铺筛选器排在 `filters` 数组的最末尾**，避免界面割裂；
   - **日期快捷项格式**：`advancedSetting.daterange` 必须传**纯数字数组字符串**（如 `"[0,1,2,4,7,21]"`，内部不带引号），根据 `dateRangeType` 挑选 3~5 个常用项；
   - **高级设置小写**：`advancedSetting` 内的所有键名（`direction`, `allowitem`, `daterange`）必须全小写。

---

## 六、 图表内嵌配置规范（Inline Chart Config）

在 `update_custom_page` 中，图表直接作为 `componentType: "chart"` 内嵌在 `components` 数组内。

### 1. Chart Config 完整字段结构
```json
{
  "type": "chart",
  "name": "各处理阶段工单分布",
  "location": { "x": 0, "y": 14, "w": 24, "h": 12 },
  "config": {
    "appId": "693b95b0-3a7c-4fd1-a755-0dc1b08d1227",
    "worksheetId": "biz_work_order",
    "viewId": "6a82b33f8b6788c07b39ece9",
    "objectId": "c9284fa1-3298-48b2-bcf8-518204918234",
    "chartName": "各处理阶段工单分布",
    "chartType": "columnChart",
    "dataScope": "permission",
    "timeFieldId": "ctime",
    "timeRange": "currentMonth",
    "dimension": [
      { "field": "biz_stage", "granularity": 3 }
    ],
    "values": [
      { "field": "rowid", "aggregation": "COUNT" }
    ],
    "rightValues": [],
    "targetValues": [],
    "stack": false,
    "percent": false,
    "lineChartStyle": "smooth"
  }
}
```

### 2. ChartType 平台枚举映射表

| 图表类型 (`chartType`) | 适用场景 | 维度与度量配置 | 特殊配置 |
|---|---|---|---|
| `numberChart` | KPI 单值汇总指标卡 | `values: [{ field, aggregation }]` | 推荐 `w: 12/8, h: 7` |
| `columnChart` | 纵向分类对比柱状图 | `dimension` (1~2 项) + `values` | 可选 `stack: true` / `percent: true` |
| `barChart` | 横向条形对比图（类别多/名称长） | `dimension` + `values` | 可选 `stack: true` |
| `lineChart` | 时间趋势走势图 | `dimension` (时间字段) + `values` | 建议 `lineChartStyle: "smooth"` |
| `pieChart` | 占比分布饼图（类别 ≤ 8） | `dimension` + `values` | 类别过多时改用 TopN 或 barChart |
| `dualAxisChart` | 双量纲分析（主轴量+副轴率） | `dimension` + `values` + `rightValues` | 副轴度量放在 `rightValues` |
| `rankingChart` | 排行榜 TopN | `dimension` + `values` | 需设置 `limit: 5~10` |
| `pivotTable` | 多维交叉透视表 | `dimension` (行+列维度) + `values` | 固定通栏 `w: 48, h: 12` |
| `funnelChart` | 阶段转化漏斗图 | `dimension` (阶段字段) + `values` | 阶段按业务顺序流转 |
| `gaugeChart` | 目标达成率仪表盘 | `values` | 需指定 `gaugeMin` / `gaugeMax` |
| `progressChart` | 子弹进度图 | `values` + `targetValues` | 目标值度量放在 `targetValues` |
| `regionMap` / `worldMap` | 地理分布图 | `dimension` (省市区字段) + `values` | **仅当存在地区字段时生成** |

---

## 七、 按钮组件规范 (button)

**所有按钮必须合并到一个 button 组件内**——通过 `buttons` 数组包含多个按钮项，而非为每个按钮创建独立组件。

```json
{
  "type": "button",
  "name": "快捷操作",
  "location": { "x": 0, "y": 8, "w": 48, "h": 6 },
  "config": {
    "style": 2,
    "width": 1,
    "count": 6,
    "mobileCount": 2,
    "buttons": [
      {
        "name": "发起采购申请",
        "icon": "add",
        "action": 1,
        "value": "worksheetId_xxx"
      },
      {
        "name": "待我审批",
        "icon": "view_eye",
        "action": 2,
        "value": "worksheetId_xxx",
        "viewId": "viewId_xxx"
      }
    ]
  }
}
```

> [!CAUTION]
> **固定 4 参数必填**：`style=2`，`width=1`，`count=6`，`mobileCount=2`。缺任何一个按钮组件都会创建失败！
> - `icon` 按 action 类型固定：1(新建记录)→`add`，2(打开视图)→`view_eye`，3(自定义页面)→`custom_navigation`，4(外部链接)→`launch`；
> - 文本设置：只设置 `name`/`title`，**禁止**设置 `explain`；
> - `action=1`（新建记录）：`value` 填 worksheetId（不支持 alias）；
> - `action=2`（打开视图）：`value` 填 worksheetId，`viewId` **必填**（不支持 alias）。

---

## 八、 轮播图组件规范 (carousel)

- **固定设置**：`action=1`（打开记录），`openMode=3`（弹窗打开）；
- `title`：最能识别记录的主标题字段，仅支持文本类型字段；
- `subTitle`：描述性文本，仅支持文本类型字段（当工作表中有对记录的描述、说明字段时设置）。

---

## 九、 文本组件与精准高度公式 (text)

使用原生 HTML + 行内 CSS 编写页面使用指南卡片。**禁止 Markdown。**

### 精准高度计算公式 (h)
- **基础高度**：`h = 5`（用于消化外层 `padding` 和基础间距）；
- **普通文本**：主标题 `h + 1`，每一行说明段落 `h + 1`；
- **列表项**：每个 `<li>` 算作 `h + 1`（若单项字数超长折行则算 `h + 2`）；
- **Grid 卡片**：每行 Grid 卡片基础算作 `h + 4`（若卡片内说明文字达到 2 行或以上，则算 `h + 5`）；
- **示例**：
  - 纯列表：标题(1) + 说明(1) + 3个列表项(3) = 基础 5 + 1 + 1 + 3，最终 `h = 10`；
  - 单行 Grid：标题(1) + 1行Grid卡片(4) = 基础 5 + 1 + 4，最终 `h = 10`。

### 通用样式规则
- **外层 `<div>`**：`height: 100%; box-sizing: border-box; overflow: hidden; background: #1e293b; border-radius: 12px; padding: 20px 24px;`；
- **所有文本标签必须显式写内联 `color` + `font-size`**：
  - `<h4>` → `font-size: 17px; font-weight: 600; margin-top: 0; color: #ffffff;`
  - `<p>` / `<li>` → `font-size: 14px; line-height: 1.8; margin-bottom: 0; color: #cbd5e1;`

---

## 十、 图表类型选型速查与搭配原则

| 分析目的 | 优先使用图表类型 | 适用字段与数据特征 |
|---|---|---|
| **KPI 单值** | `numberChart` | 总额、总笔数、达成率、均值 |
| **趋势变化** | `lineChart`（smooth 平滑） | 时间序列走势（按日、按月、按季） |
| **双轴对比** | `dualAxisChart` | 销售额(柱) + 增长率(线) |
| **分类对比** | `columnChart` / `barChart` | 状态、部门、类型、渠道 |
| **占比分布** | `pieChart` | 类别 ≤ 8 的占比分布（如合同类型分布） |
| **TopN 排名** | `rankingChart` | 销售 Top 10、畅销商品 Top 5 |
| **多维交叉** | `pivotTable` | 部门 × 季度支出交叉透视 |
| **地理分布** | `regionMap` | 客户省份分布、网点分布（必须有 Region 字段） |

- **页面应包含不同分析目的的图表**，避免整页单一类型；
- 分类过多时限制分类数量或使用 TopN；
- 若某类分析无法形成清晰结论，坚决不生成；
- **单图真实同源**：图表数据与业务字段必须 100% 真实映射，严禁生造不存在的字段。
