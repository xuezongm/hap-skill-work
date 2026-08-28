# Step 5：创建高仿真示例数据 SOP (5_create_sample_data)

本文档是 Build 阶段 **Step 5（直接基于已建工作表元数据批量生成与注入高仿真示例数据）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [三批分层拓扑填报执行流水线 (SOP)](#三-三批分层拓扑填报执行流水线-sop)
4. [自关联层级表两阶段创建流程](#四-自关联层级表两阶段创建流程)
5. [输出交付物契约 (.build)](#五-输出交付物契约-build)
6. [⛔ 验证断言与错误自愈](#六-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行定位**：在所有工作表、跨表关联与高级设置完成后，直接读取已建好的工作表结构，为应用注入高度契合业务语境的高仿真演示数据；
- **核心输入契约**：
  - `appId`：当前应用 ID（来自 `hap-context.json`）；
  - `worksheetContext`：已建工作表完整元数据索引（来自 `worksheetContext.json`，每张表包含 `worksheetId`、`worksheetName` 与完整 `fields` 字段列表）；
- **字段取值与填报边界（LLM 规则执行）**：
  - **字段标识**：`fields[].id` **必须使用字段的真实 24 字符 hex 物理 ID (`field.id`)**，严禁使用 alias 或中文名；
  - **自动跳过不可写字段**：自动跳过 `Divider`（分段）、`Formula`（公式）、`DateFormula`、`AutoNumber`（编号）、`Lookup`（他表字段）、`Rollup`（汇总）、`SubTable`（明细内嵌）、`Signature` 及系统只读字段（`rowid`, `ownerid`, `caid`, `ctime`, `utime`, `uaid`）；
  - **严格选项匹配**：`SingleSelect`、`MultipleSelect`、`Dropdown` 字段的值必须严格从 `field.options` 列表中选取已有文本；
  - **调用约束**：调 `batch_create_records` 时 **`triggerWorkflow` 固定传 `false`**。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-sample-data.md](../../references/spec-sample-data.md)
> （数据生成条数分层规则、字段类型填值格式对照、内置虚拟用户列表、分类预设附件资源库、拟真度与偏态分布要求）
>
> 📖 [references/resource-sample-images.md](../../references/resource-sample-images.md)
> （全量静态图片直链库）
>
> **准许调用工具清单 (Tool Whitelist)**：`["batch_create_records"]`

---

## 三、 三批分层拓扑填报执行流水线 (SOP)

数据填充必须严格按拓扑依赖顺序分批推进，并在内存中维护 `rowIdCache: Map<string, string[]>`（表名 → 真实生成的 rowId 数组）：

### 阶段 1：基础主数据与独立表（第 1 批）
1. **筛选范围**：无跨表关联，或仅依赖字典表/自关联的基础主数据表（如 `客户`、`供应商`、`仓库`、`图书类型`、`商品分类`）；
2. **生成与写入**：
   - 按照 `spec-sample-data.md` 规定的条数（配置表 1 条、字典表 3 条、核心表 8-10 条）生成数据；
   - 调用 `batch_create_records` 写入，获取返回的 `rowIds` 数组；
   - 记录到缓存：`rowIdCache[worksheetName] = rowIds`。

### 阶段 2：业务从属单据与流水表（第 2 批）
1. **筛选范围**：依赖第 1 批主数据的单据、工单、订单、申请表（如 `采购入库单`、`出库申请单`、`维保工单`）；
2. **内存级联绑定**：
   - 针对表中的 `Relation` 字段，读取其 `dataSource` 对应的目标表 ID 与表名；
   - 从 `rowIdCache[targetWorksheetName]` 中挑选真实的 `rowId`（按偏态分布打散）填入 Relation 字段；
3. **生成与写入**：调用 `batch_create_records` 写入，并缓存本批次生成的 `rowIds`。

### 阶段 3：明细子表（第 3 批）
1. **筛选范围**：**被主表中的 `SubTable` 控件作为 `dataSource` 引用的工作表**（如采购单对应的 `采购明细`、入库单对应的 `入库明细`、报销单对应的 `费用明细`）；
2. **主表绑定填报**：
   - 从 `rowIdCache[parentWorksheetName]` 获取对应主表的全部 `rowId`；
   - 为主表的**每条记录**分别生成 2~3 条明细行；
   - **必须在子表的 Relation 关联字段中填入对应主表记录的 `rowId`**（如 `["主表真rowId"]`），确保明细内嵌挂载到主表详情页；
3. **批量写入**：对子表调用 `batch_create_records` 一次性全量写入。

---

## 四、 自关联层级表两阶段创建流程

当某张表的 Relation 字段其 `dataSource` 指向本表自身时，执行两阶段插入：

1. **阶段一（根节点创建）**：
   - 调用 `batch_create_records` 插入 **2 条根记录**，`fields` 数组中**不传**该自关联字段；
   - 从返回值捕获 2 条根记录 ID（`rootRowIds = [id1, id2]`）；
2. **阶段二（子节点物理挂载）**：
   - 再次调用 `batch_create_records` 插入 **5 条子记录**；
   - 在子记录的自关联字段中，填入 `rootRowIds` 中的真实 ID。

---

## 五、 输出交付物契约 (.build)

全量工作表示例数据写入完成后，生成任务回执：
- **回执文件路径**：`.build/receipts/step5-sample-data.json`
- **回执格式**：
```json
{
  "taskId": "step5-sample-data",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "5",
  "target": { "type": "sample_data", "name": "全局示例数据" },
  "status": "succeeded",
  "outputs": {
    "sampleDataCreated": true,
    "totalRecordsCreated": 48
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 batch_create_records 成功为各表分批写入仿真数据并完成 Relation 级联绑定"]
  },
  "issues": []
}
```

---

## 六、 ⛔ 验证断言与错误自愈

1. **断言 1 (物理 ID 校验)**：提交前检查每个 `fields[].id` 必须是 `worksheetContext` 中对应字段真实的 24 字符 hex ID；
2. **断言 2 (选项值校验)**：选项字段的值必须在 `field.options` 列表中严格存在；
3. **断言 3 (Relation rowId 有效性)**：Relation 字段的值必须是前序步骤 API 真实返回的 `rowId`，严禁编造；
4. **断言 4 (回执落地)**：全量写入后必须产出 `.build/receipts/step5-sample-data.json`；
5. **错误自愈策略**：
   - 若单张表写入失败，分析报错信息（如选项不匹配或字段 ID 错误），对照 `worksheetContext` 修正参数后重试；
   - 若目标关联表无可用记录，跳过该关联字段或重新拉取。
