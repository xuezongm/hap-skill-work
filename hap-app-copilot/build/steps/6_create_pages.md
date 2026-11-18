# Step 6: 自定义页面组件组装与布局校正 SOP (`6_create_pages`)

<!-- SOURCE: build-app/custom-page-config-sub-agent.yaml -->

## 一、 本地宿主输入与参考映射

- **执行方式**：独立 Subagent 按单个自定义页面并发执行（页面空壳已由 Step 1 创建就绪）。
- **输入切片**：读取 `.build/task-context/{taskId}.json`：
  - `planSlice`：`page`（含 `name`、`type`: `"dashboard" | "workspace"`、`description`、`charts` 或 `components`、`requirements`）、`appColor`、`appLanguage`；
  - `contextSlice`：`appId`、`pageId`（24 位真实 hex）、`worksheetIdByName`、`viewIdByName`；
  - `worksheetContextSlice`：全量已建工作表及真实字段列表（含 `id`、`alias`、`type`、`options`）。
- **必读领域规范**：`references/hap-domain-custom-page-spec.md`、`references/hap-chart-design-guide.md`（若需挑选数值卡片图标，按需查阅 `references/hap-icon-palette.md`）
- **主要业务工具**：`["update_custom_page", "get_custom_page_structure", "patch_custom_page_components"]`（**严禁调用 `create_chart`**！自定义页面内图表统一作为页面内联组件保存）

---

## 二、 核心构建规则与执行步骤

- **输出语言与补充要求**：页面内所有组件标题、按钮文案与筛选名称使用 `appLanguage` 指定语言；优先落实 `page.requirements` 中的视觉、图标显隐与对齐要求。

### 1. 指标核实、组件映射与整页组装
1. `pageId` 缺失时，从建壳结果、完整上下文或线上页面定位真实 ID；前置工作未完成则向主调度器报告具体依赖，按宿主适配继续恢复。
2. **先核实指标可实现性**：从 `worksheetContextSlice` 确定每个指标的真实数据源 `worksheetId`、字段 `id`/`alias` 与聚合口径（已有匹配的汇总/公式字段直接聚合，不重复套计算；差额保留减项、比率保留分母，无法由现有字段真实表达的指标跳过并记入 `notes`，严禁用恒零或无关总额冒充）。
3. **视图 ID 反查铁律**：组件引用视图时，必须从 `viewIdByName` 按目标表查找语义为“全部/All”的真实 24 位 `viewId`（找不到则取该表第一个真实 `viewId`），严禁填视图中文名、表名或空串。
4. **共用组件映射与 `filtersGroup` 置后输出**：
   - 为每个内联图表/视图分配稳定的本地 UUIDv4 `objectId`，`filtersGroup` 同一业务条件只建一个筛选项（内层 `filterId` 传 UUIDv4，外层 `filtersGroupId` 留空不传），在 `objectControls` 中绑定所有语义兼容的图表/视图 `objectId`；
   - `components` 数组中先排列被引用的 `chart` / `view` 组件，最后输出 `filtersGroup`（其坐标 `position` 仍置顶于 `y: 0`）；
   - **Dashboard** 按 `references/hap-domain-custom-page-spec.md` 转换全部有效 `charts` 并配齐 48 栅格排版；**Workspace** 转换 `Button / View / Text / Carousel` 并按规范默认补齐 KPI 卡片与右侧辅助分析图（`page.requirements` 明确排除统计时除外）；
   - **数值卡图标**：需显示图标时从 `references/hap-icon-palette.md` 选带 `sys_` 前缀的合法 `fileName` 写入 `components[].config.config.numberCard` 并显式开启图标显示开关，量级/小数位/单位写入 `values[]`。

### 2. 一次全量保存 + 摘要布局检查 + 局部补丁校正
1. **一次全量保存**：先按 [宿主适配](../../HOST_ADAPTER.md) 核实 `update_custom_page` 实时 Schema，再调用 1 次 `update_custom_page(appId, page_id: pageId, components)` 保存整页组件树（若写入前参数校验报错未落库，一次集中修正全部错误路径后重提，最多 3 次；若确认线上页面已有组件树落库或本次保存已成功，**严禁再次调用 `update_custom_page`**）。
2. **写后布局检查**：保存成功后，调用 1 次 `get_custom_page_structure(appId, page_id: pageId, detail: "summary")` 检查 48 列栅格坐标、左右组合顶底边对齐、容器坐标空间与组件重叠（无需读 `full`）。
3. **按需一轮局部校正（完建优先不阻断）**：若摘要显示存在重叠、错位或多余装饰容器遮挡，调用 `patch_custom_page_components`（仅传真实 `componentId`、原 `componentType`、位置/尺寸/父级差异及最新 `version`，省略 `config`）做一轮局部校正后再读一次 `summary` 核实收口。一旦 `update_custom_page` 已将核心页面组件树成功落库，即使个别派生指标跳过或可选局部微调触及平台边界，也必须保留已落库页面、在 `outputs.notes` / `issues` 说明差异并返回顶层 `status: "succeeded"`，严禁将已落库页面回执写成 `"failed"` 触发二次全量重跑冲突。

---

## 三、 本地回执落盘契约

执行完成后，将标准回执写入 `receiptPath`（`.build/receipts/step6-page-{name}.json`）：

```json
{
  "taskId": "<来自 taskContext.taskId>",
  "runId": "<runId>",
  "executor": { "kind": "subagent", "agentId": "<agentId>" },
  "step": "6",
  "target": { "type": "page", "id": "<pageId>", "name": "<pageName>" },
  "status": "succeeded",
  "outputs": {
    "pageName": "<pageName>",
    "pageId": "<pageId>",
    "completed": true,
    "notes": []
  },
  "verification": {
    "passed": true,
    "evidence": ["已调用 update_custom_page 保存组件树并通过 summary 回读核对布局"]
  },
  "issues": []
}
```
