# Step 2b：补充跨表关联与衍生字段 SOP (2b_create_relations)

本文档是 Build 阶段 **Step 2b（按需并发补充跨表关联、子表、Lookup、Rollup、跨表公式与拼接字段）** 的专属作业指导书，1:1 对齐官方生产级子代理设计规范。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [6 种待补字段类型构造规则 (A 到 F)](#三-6-种待补字段类型构造规则-a-到-f)
4. [双边声明防重仲裁与单次调用铁律](#四-双边声明防重仲裁与单次调用铁律)
5. [单表执行 SOP 流水线](#五-单表执行-sop-流水线)
6. [输出交付物契约 (.build)](#六-输出交付物契约-build)
7. [⛔ 验证断言与别名重复自愈重试](#七-⛔-验证断言与别名重复自愈重试)

---

## 一、 执行定位与输入契约

- **执行定位**：两遍建表的 Pass 2 阶段。此刻所有工作表均已建好基础字段，本步专门把跨表关联与衍生计算字段补回，落到 Pass 1 预留的行号位置上；
- **只补关联、不回读**：本步**严禁调用 `get_worksheet_structure`**。本表完整字段（含新关联与反向关联）由后置步骤统一回读刷新；
- **核心输入契约**：
  - `worksheetContext`：已建工作表轻量索引 `[{ name, id, alias, fields: [{ name, id, alias, type }] }]`；
  - `worksheetIdByName`：表名到 worksheetId 映射字典；
  - `relationLayout`：Pass 1 预留的本表待补复杂字段数组。若该数组为空或未找到本表，直接返回成功回执，不调任何工具。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-worksheets.md](../../references/spec-worksheets.md)（工作表结构、Relation、SubTable、Lookup、Rollup、CascadingSelect 平台规格）
>
> **准许调用工具清单 (Tool Whitelist)**：`["update_worksheet"]`

---

## 三、 6 种待补字段类型构造规则 (A 到 F)

遍历 `relationLayout` 数组中的每个待补全字段，根据其 `fieldType` 分别构造 `update_worksheet.addFields` 项：

### 【情况 A】跨表关联 (fieldType: "Relation")
- `type`: `"Relation"`
- `name`: 来源于 `relationLayout.name`
- `alias`: 来源于 `relationLayout.alias`
- `dataSource`: 根据 `relationLayout.targetWorksheet`，在 `worksheetIdByName` 查目标表 ID；**查不到则跳过该关联字段**（不编造 ID）
- `layout`: 直接使用 `relationLayout` 中的 `rowIndex` 和 `span`
- `config`: 高级属性配置：
  - `bidirectional`: 取自 `relationLayout.bidirectional`（为 true 时系统自动在目标表回填反向字段，为 false 时为单向引用）
  - `isMultiple`: 取自 `relationLayout.isMultiple`（true 一对多/多对多，false 多对一）
  - `displayMode`: 取自 `relationLayout.displayMode`（`"dropdown"` / `"card"` / `"inlineTable"` / `"tabTable"`）
  - `showFields`: 目标表显示字段的 **别名 (alias) 数组**：
    - 从目标表 fields 中挑选 **2-4 个最有业务价值的字段** alias（必须包含目标表的标题字段，排除富文本、附件等复杂类型）
  - `coverField`: 卡片封面，**仅当 `displayMode === "card"` 时有效**：
    - 检查目标表 fields 中是否有 `type === "Attachment"` 的字段。若有且为视觉标识（产品图、头像、Logo），提取其 `alias` 填入；纯文档类或无附件时不传。

### 【情况 B】明细子表 (fieldType: "SubTable")
- `type`: `"SubTable"`
- `name`: 来源于 `relationLayout.name`
- `alias`: 来源于 `relationLayout.alias`
- `dataSource`: 查目标子工作表 ID
- `layout`: `rowIndex` 取自 `relationLayout`，**`span` 固定为 `12`（子表必须独占整行）**
- `config`:
  - `bidirectional`: `true`
  - `showFields`: **必填**，从子表 fields 中挑选 **2-4 个最有业务价值的子字段** alias（排除富文本、附件）
- ⚠️ **注意**：不需要 `displayMode`、`isMultiple` 等 Relation 专属属性。

### 【情况 C】Lookup 字段 (fieldType: "Lookup")
- `type`: `"Lookup"`
- `name`: 来源于 `relationLayout.name`
- `relationField`: 使用 `relationLayout.relationField`（关联字段真实 alias 或 ID）。**注意：该关联字段必须是单条关联（`isMultiple: false`）**
- `sourceField`: 从 `worksheetContext` 中查找**目标表**的字段列表，用 `relationLayout.sourceFieldName`（中文名）匹配字段 `name`，取其真实 `alias`（**严禁拼音化或编造别名**）
- `config`: `{ storeData: true }`（存储数据类型，物理复制落库，支持被公式计算引用与筛选）
- `layout`: 直接使用 `relationLayout` 中的 `rowIndex` 和 `span`

### 【情况 D】Rollup 字段 (fieldType: "Rollup")
- `type`: `"Rollup"`
- `name`: 来源于 `relationLayout.name`
- `relationField`: 使用 `relationLayout.relationField`（可以是 Relation 或 SubTable 字段）
- `sourceField`: 从 `worksheetContext` 中查找**目标表/子表**的字段列表，用 `relationLayout.sourceFieldName`（中文名）匹配字段 `name`，取其真实 `alias`
- `config.calcType`: 取自 `relationLayout.calcType`（`"sum" | "count" | "avg" | "max" | "min"`）
- `layout`: 直接使用 `relationLayout` 中的 `rowIndex` 和 `span`

### 【情况 E】复合文本组合 (fieldType: "Concatenate")
- `type`: `"Concatenate"`
- `name`: 来源于 `relationLayout.name`
- `alias`: 来源于 `relationLayout.alias`
- `isTitle`: `relationLayout.isTitle === true`
- `layout`: 直接使用 `relationLayout` 中的 `rowIndex` 和 `span`
- `config`: `{ expression: relationLayout.expression }`

### 【情况 F】复合数值公式 (fieldType: "Formula")
- `type`: `"Formula"`
- `name`: 来源于 `relationLayout.name`
- `alias`: 来源于 `relationLayout.alias`
- `precision`: `relationLayout.precision ?? 2`
- `layout`: 直接使用 `relationLayout` 中的 `rowIndex` 和 `span`
- `config`: `{ expression: relationLayout.expression }`

---

## 四、 双边声明防重仲裁与单次调用铁律

### 1. 双边声明防重仲裁机制
- **主子表 (SubTable) 场景（主表唯一创建原则）**：
  - 若主表声明了 `SubTable:子表名`（或子表属于明细子表）：**物理创建权 100% 独占归属于主表（父表）**！
  - **子表端绝对严禁调用 API 创建指向主表的关联字段**（主表建 SubTable 时系统已在子表自动生成关联）。若 `relationLayout` 误含子表指向主表的关联，**子表 Subagent 必须直接跳过**！
- **常规双向关联 (Relation) 场景（单条从属端优先原则）**：
  - 若两张表在 Plan 中均未标记 `:reverse` 且都包含了指向对方的双向关联（如 审批申请 ↔ 请假单）：
  - **优先由从属单据端（`isMultiple === false` 的单条端）作为主创建方调用 API**；主表/聚合端（`isMultiple === true` 的多条端）自动跳过不调 API，依赖对端自动带出反向 TabTable；
  - 若双方基数相同（均为 multiple 或均为 single），在 `worksheets` 列表中排在前面的表作为主创建方，排在后面的表跳过。
- **反向声明字段 (:reverse) 场景**：
  - 若字段标记了 `:reverse`，代表对端创建双向关联后在本表自动生成的反向控件，**本表严禁调用 API 重复创建，直接跳过**。

### 2. 单次调用内去重
组装完 `addFields` 后，按 `(name, dataSource)` 去重，**同一个关联字段绝不在一次 addFields 里出现两次**。

### 3. 单次调用与成功即终结铁律（硬约束）
- 每张表**仅调用一次** `update_worksheet`（把本表所有待补关联合并放进同一个 `addFields` 数组）；
- 只传 `addFields` 加关联，**不传 `editFields` / `removeFields`**（不动本表已有业务字段）；
- **一旦收到 `success: true`，必须立即输出最终回执结束任务，绝对严禁再次发起任何工具调用**！

---

## 五、 单表执行 SOP 流水线

1. **提取待补清单**：从 `relationLayout` 获取本表记录；若为空直接写入成功回执并退出；
2. **解析目标表 ID 与字段 alias**：对照 `worksheetContext` 解析每个字段的 `dataSource` 与 `sourceField` 真实别名；
3. **调用 update_worksheet**：
   ```json
   {
     "appId": "<appId>",
     "worksheetId": "<本表worksheetId>",
     "addFields": [ ...组装后的关联与衍生字段数组... ]
   }
   ```
4. **输出任务回执**：写入 `.build/receipts/step2b-rel-{targetWorksheet}.json`。

---

## 六、 输出交付物契约 (.build)

- **回执文件路径**：`.build/receipts/step2b-rel-{targetWorksheet}.json`
- **回执格式**：
```json
{
  "taskId": "step2b-rel-{targetWorksheet}",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "2b",
  "target": { "type": "worksheet", "name": "{targetWorksheet}" },
  "status": "succeeded",
  "outputs": {
    "worksheetName": "{targetWorksheet}",
    "relationsAdded": ["biz_advice_supplier", "biz_total_amount"]
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 update_worksheet 成功注入关联与衍生字段"]
  },
  "issues": []
}
```

---

## 七、 ⛔ 验证断言与别名重复自愈重试

1. **断言 1 (调用成功即终结)**：收到 `success: true` 立即生成回执终止会话，**禁止再次调用** `update_worksheet`（重复调用会产生重复关联字段）；
2. **断言 2 (严禁回读)**：**不调用 `get_worksheet_structure`**，行号直接使用 `relationLayout` 预留行号，结构由后续步骤统一回读；
3. **别名重复自愈与重试机制**：
   - 若调 `update_worksheet` 遇到 `别名重复` 报错，**丢弃冲突字段的 `alias`（不传 `alias`，交由系统自动生成唯一标识）进行重试**；
   - 若同批次包含依赖该关联字段的 Lookup / Rollup 字段，**必须同步将其 `relationField` 修改为对应字段的 `id`** 后重新发起调用（最多重试 3 次）。
