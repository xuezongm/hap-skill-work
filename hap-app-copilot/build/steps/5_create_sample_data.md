# Step 5: 拓扑感知示例数据批量填报 SOP (`5_create_sample_data`)

<!-- SOURCE: build-app/sample-data-sub-agent.yaml -->

## 一、 本地宿主输入与参考映射

- **执行方式**：独立后台 Subagent 执行（与阶段 3 页面、排序、角色、工作流设计并行运行）。
- **输入切片**：读取 `.build/task-context/step5-sample-data.json`：
  - `planSlice`：`worksheets`（含 `name`、`worksheetType`、`parentWorksheet`、`requirements`）、`appLanguage`；
  - `contextSlice`：`appId`、`worksheetIdByName`；
  - `worksheetContextSlice`：已自动过滤只读衍生字段（如自动编号、公式、日期公式、函数公式、汇总、他表字段、内联子表占位）的工作表可写字段切片，每个字段含 `{ id, name, alias?, type, dataSource?, options? }`（其中 `Relation` 字段的 `dataSource` 为目标表的 24 位 `worksheetId` 或 `"selfRelation"`，单多选/下拉的 `options` 为有效选项文本数组）。
- **必读领域规范**：`references/hap-sample-data-spec.md`（预设虚拟成员 ID、文档与分类图片资源）
- **主要业务工具**：`["batch_create_records", "get_worksheet_structure"]`

---

## 二、 核心构建规则与执行步骤

- **输出语言与排除规则**：所有记录文本严格使用 `appLanguage` 指定语言；优先遵循各表 `requirements` 的条数与场景要求（明确要求不生成示例数据的表直接从灌数清单排除，且不为关联被排除的表替其新建记录）。
- **Build 默认数量与取值策略**：
  - 未显式指定条数时：参数/全局设置表 `1` 条，字典/分类表 `3` 条，核心业务表 `8～10` 条，明细子表每条父记录 `2～3` 条明细，自关联表 `2` 条根记录 + `5` 条子记录；
  - 日期默认分布在当前时间前后 3 个月内；成员字段按 `references/hap-sample-data-spec.md` 选择预设虚拟用户 ID；`Attachment` 附件按字段业务用途选择文档或图片，资源选择与命名遵循该规范的“预设附件资源”，不因资源存在而扩展任务。
- **三批次依赖灌数顺序**：
  1. **第一批（无跨表引用的基础主数据/字典表）**：先调用 `batch_create_records` 写入，缓存返回的真实 `rowId` 数组；
  2. **第二批（含跨表 `Relation` 的业务单据表）**：从内存缓存取已建主表记录的真实 `rowId` 填入关联字段，调用 `batch_create_records` 并缓存本表 `rowId`；
  3. **第三批（`worksheetType === "subTable"` 明细子表）**：从缓存取所属主表（`parentWorksheet`）的真实 `rowId`，按主从写入规范为主记录批量生成明细行。
- **硬约束与防错红线**：
  - **`worksheet_id` 与字段 `id` 严禁编造**：必须逐字复制自 `worksheetContextSlice` 的 24 位 hex 字符串；`Relation` 字段通过其 `dataSource`（对照 `worksheetIdByName` 或 `"selfRelation"`）精确匹配上游表已生成的真实 `rowId`（含子表指向 `parentWorksheet` 的父记录关联字段）；若遇 `430022 worksheetId不存在` 或上下文缺失，按需调用 `get_worksheet_structure(responseFormat: "dsl")` 核实后继续；
  - **`rows` 结构强制契约**：每行必须为 `{ "fields": [{ "id": "<24位真实fieldId>", "value": <值> }] }`，严禁传扁平键值对；
  - **真实选项匹配**：`SingleSelect` / `MultipleSelect` / `Dropdown` 必须从 `worksheetContextSlice` 该字段的 `options` 数组取真实选项值，严禁自编；
  - **显式关闭工作流与完建不阻断**：所有 `batch_create_records` 调用固定传 `triggerWorkflow: false`；单表失败按 [宿主适配](../../HOST_ADAPTER.md) 排查续作，保留已创建记录，只补未完成部分；个别表或个别字段受表单强校验限制无法写入时，跳过受阻部分并在 `issues` 如实说明，顶层回执仍返回 `status: "succeeded"`，绝不阻塞主流程推进。

---

## 三、 本地回执落盘契约

全部目标表处理完毕后，将标准回执写入 `receiptPath`（`.build/receipts/step5-sample-data.json`）：

```json
{
  "taskId": "step5-sample-data",
  "runId": "<runId>",
  "executor": { "kind": "subagent", "agentId": "<agentId>" },
  "step": "5",
  "target": { "type": "sample_data", "name": "全局示例数据" },
  "status": "succeeded",
  "outputs": { "completed": true },
  "verification": {
    "passed": true,
    "evidence": ["已按主数据→业务单据→明细子表拓扑顺序完成示例记录批量写入"]
  },
  "issues": []
}
```
