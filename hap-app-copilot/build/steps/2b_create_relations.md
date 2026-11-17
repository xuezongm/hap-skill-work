# Step 2b: 跨表关联、子表与衍生字段回填 SOP (`2b_create_relations`)

<!-- SOURCE: build-app/worksheet-relation-build-sub-agent.yaml -->

## 一、 本地宿主输入与参考映射

- **执行方式**：独立 Subagent 按表并发执行（两遍建表 Pass 2，此时全应用所有工作表均已创建）。
- **输入切片**：读取 `.build/task-context/{taskId}.json`：
  - `planSlice`：`worksheetName`、`relationLayout`（Pass 1 预留的待补复杂字段数组）、`requirements`、`appLanguage`、`allRelationLayouts`（用于双边双向关联防重仲裁）；
  - `contextSlice`：`appId`、`worksheetId`（本表真 ID）、`worksheetIdByName`、`worksheetFieldsByName`（各表在 Pass 1 已建的基础字段 `{ name, id, alias, type }` 轻量索引）。
- **必读领域规范**：`references/hap-domain-worksheet-spec.md`
- **准许工具白名单**：`["update_worksheet"]`（**严禁调用 `get_worksheet_structure`**，全链路统一由 Step 3 回读一次）

---

## 二、 核心构建规则与执行步骤

1. **前置空检查**：若 `worksheetId` 为空或本表 `relationLayout` 为空数组，不调用任何工具，直接写入成功回执结束。
2. **双边 `:bi` 防重仲裁**：若两张表在规划中均漏标 `:reverse` 而双向互指（均含 `bidirectional: true` 指向对方），仅由单条从属端（`isMultiple === false`）调用 API 创建，多条聚合端自动跳过等待对端自动生成反向字段；若基数相同，则按工作表数组先后顺序仅由前表创建。
3. **按 `fieldType` 逐项组装 `addFields`（保留预留 `layout`）**：
   - **`Relation`（跨表关联）**：`dataSource` 从 `worksheetIdByName[targetWorksheet]` 取真实 24 位 ID（查不到则跳过该项，严禁编造 ID）；传入原 `name`、`alias`、`layout: { rowIndex, span }`；`config` 含 `bidirectional`、`isMultiple`、`displayMode`、`showFields`（从 `worksheetFieldsByName[targetWorksheet]` 挑 2～4 个核心字段的真实 **alias**，必含标题字段，排除富文本/长附件）及可选 `coverField`（仅 `displayMode === "card"` 且目标表有 `Attachment` 字段时填其真实 `alias`）。
   - **`SubTable`（子表挂载）**：`dataSource` 取子表真实 ID，`layout: { rowIndex, span: 12 }`（强制独占整行 12 列），`config: { bidirectional: true, showFields: [<从子表挑选 2~4 个核心业务字段真实 alias>] }`（不传 `displayMode` / `isMultiple`）。
   - **`Lookup`（他表字段）**：`relationField` 填本表对应单条关联字段（`isMultiple: false`）的真实 `alias`；`sourceField` 在目标表 `fields` 中按 `sourceFieldName` 匹配取出真实 **`alias`**（严禁拼音编造）；`config: { storeData: false }`（仅本表公式或视图分组确需存储时设 `true`）；带原 `layout`（可与同批新建的主动 `Relation` 通过明确声明的 `alias` 同批提交）。
   - **`Rollup`（汇总字段）**：`relationField` 填本表 `Relation` 或 `SubTable` 的真实 `alias`；`sourceField` 在目标表/子表 `fields` 中匹配取出真实 **`alias`**；`config: { calcType }`；带原 `layout`。
   - **跨表 `Concatenate` / `Formula`**：按预留的 `name`、`alias`、`isTitle`、`precision`、`layout` 及 `config: { expression }` 原样构造。
4. **单次合并写入与自愈硬约束**：
   - 对 `addFields` 按 `(name, dataSource)` 去重（`inlineTable` / `tabTable` 强制 `layout.span = 12`），仅传 `addFields`（**严禁传 `editFields` / `removeFields`**）；
   - **单表只调一次 `update_worksheet`**：收到 `success: true` 后立即写入回执结束，**严禁二次调用 `update_worksheet` 或回读结构**！
   - **别名冲突自愈**：若遇 `别名重复` 报错，剥离冲突字段的 `alias` 让系统自动生成（若同批 `Lookup/Rollup` 依赖该字段则按需分步用返回 ID 衔接），最多修正重试 3 次。

---

## 三、 本地回执落盘契约

执行完成后，将标准回执写入 `receiptPath`（`.build/receipts/step2b-rel-{name}.json`）：

```json
{
  "taskId": "<来自 taskContext.taskId>",
  "runId": "<来自 taskContext.runId>",
  "executor": { "kind": "subagent", "agentId": "<当前子代理标识>" },
  "step": "2b",
  "target": { "type": "worksheet", "id": "<worksheetId>", "name": "<worksheetName>" },
  "status": "succeeded",
  "outputs": {
    "name": "<worksheetName>",
    "id": "<worksheetId>"
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 update_worksheet 一次性补全跨表关联与衍生字段"]
  },
  "issues": []
}
```
