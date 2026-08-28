# Step 6: 配置自定义页面与统计图表 SOP (6_create_pages)

本文档是 Build 阶段 **Step 6（按页面并发配置自定义页面组件与统计图表）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [单页面执行 SOP 流水线](#三-单页面执行-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与错误自愈](#五-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：子代理按页面并发；
- **任务目标**：根据切片规划为自定义页面批量创建统计图表（柱状图/折线图/数值指标卡等），并将图表、富文本、视图等组件编排入页面布局中；
- **核心输入契约（全部预装在任务切片中，直接读取内存切片即可）**：
  - `taskContext.planSlice.page`：当前页面的图表（`charts`）或组件（`components`）规划；
  - `taskContext.worksheetContextSlice`：全量工作表的真实字段结构与 controlId 映射（**已包含全量字段映射，直接读取使用，严禁调用 `get_worksheet_structure`**）；
  - `taskContext.contextSlice`：包含 `appId`、`pageId`、`worksheetIdByName`、`viewIdByName`（**已包含当前页面 ID 与视图 ID，直接使用，严禁调用 `get_custom_page_structure`**）。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-pages-charts.md](../../references/spec-pages-charts.md)（自定义页面 24 栅格、FiltersGroup 联动与 9 种图表 Schema）

---

## 三、 单页面执行 SOP 流水线

### 1. 批量创建统计图表 (Charts)
遍历切片中的图表规划：
1. **数据源字段映射**：直接从切片的 `worksheetContextSlice` 提取维度与指标字段的真实 `controlId`；
2. **调用 MCP 创建图表**：调用 `create_chart`：
```json
{
  "appId": "<appId>",
  "worksheetId": "<worksheetId>",
  "name": "本月各部门销售额对比",
  "reportType": "bar",
  "xaxes": { "controlId": "biz_dept" },
  "yaxisList": [{ "controlId": "biz_amount", "normType": 1, "alias": "销售额" }]
}
```
记录返回的图表 ID（`reportId`）。

### 2. 编排页面组件布局 (update_custom_page)
页面采用 **48 栅格系统**（`x + w <= 48`）。直接使用切片中的 `contextSlice.pageId`，组装包含顶部筛选组、统计图表、视图嵌入与按钮等组件的完整数组，调用 `update_custom_page`：

> [!CAUTION]
> **filtersGroup ID 规则（避坑关键）**：
> - **外层 `config.filtersGroupId`**：**新建筛选组必须留空或完全不传**（由服务端自动生成；若传入自定义 UUID 会报 430001 错误）；
> - **内层 `filters[].filterId`**：**必须传入生成的 36 位 UUIDv4**（服务端强校验非空）。

```json
{
  "appId": "<appId>",
  "page_id": "<pageId>",
  "components": [
    {
      "componentType": "filtersGroup",
      "position": { "x": 0, "y": 0, "w": 48, "h": 4 },
      "config": {
        "filters": [
          {
            "filterId": "c8b1a234-5678-4901-abcd-ef0123456789",
            "filterDataType": "Option",
            "dataType": 11,
            "controlId": "<statusControlId>",
            "name": "业务状态",
            "filterType": 2,
            "advancedSetting": { "direction": "2", "allowitem": "1" },
            "objectControls": [
              {
                "objectId": "<chartObjectId>",
                "type": 1,
                "worksheetId": "<worksheetId>",
                "controlId": "<statusControlId>"
              }
            ]
          }
        ]
      }
    },
    {
      "componentType": "chart",
      "name": "本月各部门销售额对比",
      "position": { "x": 0, "y": 4, "w": 24, "h": 8 },
      "config": {
        "worksheetId": "<worksheetId>",
        "objectId": "<chartObjectId>",
        "chartType": "barChart",
        "dataScope": "all",
        "dimension": [{ "field": "<deptControlId>" }],
        "values": [{ "field": "<amountControlId>", "aggregation": "SUM" }]
      }
    }
  ]
}
```

---

## 四、 输出交付物契约 (.build)

执行成功后，将当前页面配置的图表与标准回执写入独立任务回执文件：
- **文件路径**：`.build/receipts/step6-page-{targetPage}.json`
- **内容格式**：
```json
{
  "taskId": "step6-page-{targetPage}",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "6",
  "target": { "type": "page", "name": "{targetPage}" },
  "status": "succeeded",
  "outputs": {
    "pageName": "{targetPage}",
    "pageId": "page_id_1",
    "chartsCreated": [
      { "name": "本月各部门销售额对比", "reportId": "rep_id_1" }
    ]
  },
  "verification": {
    "passed": true,
    "evidence": ["各图表根据 create_chart 返回成功捕获 reportId，update_custom_page 成功更新页面布局"]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与错误自愈

1. **断言 1 (图表全量创建)**：所有规划的统计图表均调用 `create_chart` 创建成功且记录 `reportId`；
2. **断言 2 (页面更新成功)**：调用 `update_custom_page` 响应 `success: true`；
3. **断言 3 (回执通知)**：将包含 `chartsCreated` 的标准回执写入 `.build/receipts/step6-page-{targetPage}.json`；
4. **自愈机制**：若 `update_custom_page` 报 430001 错误，检查 `filtersGroupId` 是否为空。
