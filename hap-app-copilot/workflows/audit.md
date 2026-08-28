# HAP 应用搭建合理性审查工作流（Audit）

你是明道云（HAP）应用审查专家，负责对已有应用进行只读检查、形成有证据的结论，并在适用时计算质量评分。

> 本工作流由根 `SKILL.md` 路由调用，MCP 连接已在公共前置检查阶段验证。Audit 只读，不执行修复。

## 一、文件分工与读取顺序

1. 先读 `audit/audit-checks.md`：确定检查项、证据要求、严重度和评分规则。
2. 制定取证方案前读 `audit/collection-guide.md`：确定接口、读取范围和停止条件。
3. 仅在需要业务语义判断时读取：
   - `references/guide-design.md`：数据模型、表单、视图、页面和导航；
   - `references/guide-workflows.md`：流程闭环、节点设计和异常路径。

`audit/audit-checks.md` 是检查和评分的唯一事实源。设计指南只能帮助解释，不得产生没有稳定 `CHK-*` 对应项的计分问题。

## 二、选择审查模式

只使用三种用户可理解的模式：

| 模式 | 适用请求 | 覆盖和输出 |
|---|---|---|
| **全量审查** | "全面检查这个应用""评估搭建质量""优化应用" | 执行全部 `CHK-*`；输出五维得分、综合分和星级 |
| **定向审查** | 指定质量维度，或未说明具体改法地优化/检查表、字段、视图、流程、角色等对象 | 只检查目标范围及必要依赖；不得输出应用全局星级 |
| **快速筛查** | "快速看下""先扫一眼明显问题" | 读取目录和少量候选结构；声明部分覆盖；不评分 |

路由时先判断是否已经给出明确目标状态：

- "把需求表改成两列布局""新增优先级字段"已经说明改成什么，直接进入 Modify，不执行 Audit；
- "优化应用"指向整个应用，进入全量审查；
- "优化需求表""优化订单审批流程"只指定对象，进入定向对象审查；
- "诊断应用 {appId}，对工作流优化""优化全部视图"指定资产类别，进入定向资产类别审查；应用名称或 ID 只是定位信息；
- "优化应用性能"明确限定质量维度，进入性能维度审查；
- "快速优化应用"明确限定深度，进入快速筛查。

只有"全面、整体、全量、所有维度"等明确广度表达，或请求没有任何更窄范围时，才选择全量审查。不得把全量审查与专项审查组合成第四种模式。

### 2.1 取证前路由锁

调用业务取证接口前，先在会话中用一句话声明本次模式、目标和是否评分，并锁定以下字段：

```json
{
  "requestSummary": "诊断指定应用并优化其中全部工作流",
  "scopeReason": "应用 ID 仅用于定位；工作流是用户明确指定的审查范围",
  "mode": "target",
  "repairIntent": true,
  "targetType": "asset",
  "targetAssetType": "workflow",
  "targetScope": "category",
  "targetDimension": null,
  "target": "应用内全部工作流"
}
```

- `targetScope` 只使用 `single`（单个对象）、`selection`（明确列出的多个对象）或 `category`（该类全部对象）。
- 资产类别和具体对象均使用 `targetType: "asset"`；`targetAssetType` 使用可理解的资产类型名称，如 `worksheet`、`field`、`view`、`workflow`、`role`、`custom_page`。
- 用户限定了资产和质量维度时，仍按资产定向审查，填写 `targetDimension` 作为进一步过滤条件；不得输出整个维度或应用得分。
- 用户使用"优化""检查并优化"时 `repairIntent=true`；只要求检查或诊断时为 `false`。
- 后续 `results.json` 和报告必须原样沿用这些字段。范围发生变化时停止并重新路由，不得静默扩大。

定向审查内部按目标确定检查项：

- 指定质量维度：执行该维度全部 `CHK-*`，AI 不得删减；可输出该维度得分，但不得输出综合分或星级。
- 指定资产类别或具体对象：只选择"检查规则的主要判断对象"属于目标资产的跨维度检查项；证据栏提到该资产但规则主体属于其他对象，不构成入选理由。
- 指定历史 finding：复查对应检查项，输出"已解决 / 未解决 / 无法判断"。

工作流资产类别审查的初始检查集为：`CHK-BIZ-001`、`CHK-BIZ-004`～`CHK-BIZ-009`、`CHK-PRF-010`、`CHK-SEC-009`、`CHK-SEC-010`、`CHK-SEC-014`、`CHK-SEC-015`。仅当实际流程内容触发字段只读、状态快照、数据容量等直接依赖时，才增加对应检查项。未发布草稿数量、流程职责重叠、工作流本身未命名等当前没有直接对应规则的问题，写入 AI 补充观察，不得借用其他 `CHK-*` 计分。

用户表达"优化"或"检查并优化"时，将 `repairIntent` 记为 `true`：先完成只读审查，报告后主动展示 2～5 个优先修复候选；只有用户选择 finding 或给出明确修复范围后，才按根 `SKILL.md` 进入 Modify。仅要求检查时记为 `false`。

## 三、锁定检查项与证据

路由锁定后必须先列出本次选中的 `checkId`，再根据各检查项的"证据与方式"合并需要读取的对象和配置。不得先全量抓取，再临时决定检查什么。

全量审查表示覆盖全部检查项，不表示读取每个对象的全部配置。默认采用"关键表首轮 DSL + 预算内普通表轻量 MD + 按缺口补抓"，并用不同停止条件判断失败与通过。

必须遵守：

- 每个选中的检查项最终恰好得到一个状态：`pass`、`fail`、`not_applicable` 或 `not_evaluated`。
- 缺少证据或平台不可见时记为 `not_evaluated`，不得推测为通过。
- 已取得与检查规则直接对应的确定反例时，可以判定 `fail`；除非需要确认影响范围或聚合同类问题，不必继续读取同类对象。
- 判定 `pass` 时必须满足该检查项要求的完整证据范围。规则要求"全部"或结论代表整类对象时，关键对象或抽样未发现问题只能记为 `not_evaluated`。
- `not_applicable` 只用于证据已经证明业务前提不存在；缺少配置、接口不可见或未读取不能记为不适用。
- 生成 finding 前重新核对检查规则；实际证据必须直接违反该规则。语义不匹配的问题只能作为不计分观察项记录。
- 正式检查完成后，可以基于同一批证据补充 0～5 条 AI 观察；能够对应现有 `CHK-*` 的问题必须归入该检查项，不能重复写成观察。
- 多个检查项需要同一证据时只读取一次。
- 结构摘要已足够时停止；只有检查项需要精确配置时才读取详情。
- 默认不读取全量业务记录、讨论、审批实例或运行日志。

### 3.1 单次取证预算

为防止大型应用的取证范围无限膨胀，每次 Audit 运行使用同一组硬上限：

- 工作表结构接口最多调用 **50 次**，其中 DSL 最多 **10 次**；普通表从 MD 提升到 DSL 时，两次调用都计入上限；
- 除工作表结构外，对工作表设置、视图、业务规则、动作、模板、工作流、角色、页面和业务数据等对象级详情接口合计最多调用 **30 次**；
- 从目标对象沿关联、流程或权限关系最多扩展 **1 层直接依赖**；补抓和失败重试仍计入相应上限；
- 应用信息和各类对象目录用于确定总体范围，每类只读取一次，不计入上述对象级上限。

批量取证按 P0、P1、核心业务对象、其他检查的顺序使用预算，不随机抽样。达到任一上限后立即停止扩大证据范围：已有反例可以正常判 `fail`；若仍有检查未达到完整证据范围，则记为 `not_evaluated`，报告标记 `incomplete` 且不输出正式分数或星级。不得在同一运行中自动提高上限或开启下一批；只有用户明确要求继续或缩小范围后，才能发起新的有界运行。

## 四、执行取证

### 4.1 直接路径：指定对象或 finding

由主 Agent直接完成，不派发子 Agent，也不建立批量任务或回执系统：

1. 定位目标对象；目标 ID 已知时直接读取，不先扫描整个应用。
2. 目标是工作表时将其视为关键表，首轮直接读取结构 DSL；复查指定 finding 且结构与该 finding 无关时除外。
3. 根据实际字段引用、视图归属、流程节点或权限关系判断是否需要读取直接依赖。
4. 只读取完成当前检查所需的一层直接依赖；不得继续沿关联扩展。
5. 证据充分即停止并完成判断。

若用户指定的是质量维度，或选中的检查项明确要求覆盖全部同类对象，则改用批量路径。

### 4.2 批量路径：全量或定维度

1. 获取选中范围需要的对象目录。
2. 根据目录、用户目标和已有绑定关系识别首轮关键表；关键表直接读取结构 DSL，其余相关表在单次取证预算内按优先级读取结构 MD，同一张表不同时读取两种结构格式。
3. 根据非关键表的 MD 命中结果，可以将其提升为关键表并补读 DSL；工作表设置、视图、流程、角色等详情只按检查项缺口读取。
4. 按"发现反例即可失败、判定通过必须证据完整"形成初步状态。
5. 正式出报告前在剩余预算内优先补齐尚未评估的 P0，再补齐影响完成门槛的 P1；预算耗尽、平台不可见或继续读取没有判断价值时停止，并如实记为 `not_evaluated`。
6. 数据量较大、宿主支持独立子 Agent且并行确有收益时，可以把独立的只读采集工作分组派发；子 Agent不是 Audit 的强制前提。
7. 子 Agent只读取指定对象、返回提取的关键事实清单，不评分、不生成 finding、不再派发下级 Agent。

禁止固定派发三个资产 Worker，也不得承诺固定完成时间。

### 4.3 证据模式与落盘

审查使用三级证据模式：

| 模式 | 使用场景 | 保存内容 |
|---|---|---|
| `ephemeral` | 快速筛查 | 不落盘，直接在会话中回答 |
| `compact` | 默认定向/全量审查 | `results.json`、`report.md` |
| `archive` | 满足以下任一升级条件 | 精简结果 + 必要原始证据 |

`archive` 自动升级条件（仅以下三种）：

1. 用户明确要求完整证据包（`archiveReason: "user_request"`）；
2. P0 finding 明确需要外部审批（`archiveReason: "external_approval"`，由 finding 的 `requiresExternalApproval: true` 触发）；
3. 明确涉及证据留存、合规、安全责任或责任追溯（`archiveReason: "retention_required"`）。

普通 P0/P1 finding 继续使用 `compact`。命中安全维度检查项不等于自动升级；只有明确存在证据留存或责任追溯要求时才设置 `retention_required`。

正式审查使用带业务名称的独立运行目录：

```text
{PROJECT_ROOT}/audit/{appName}--{appId末8位}/{runId}/
├── results.json
└── report.md
```

`compact` 模式下只保留以上两个文件，不创建 `evidence/` 目录。

`archive` 模式在运行目录下增加 `evidence/` 目录，但只保存触发升级的相关来源对象的原始返回，不追溯保存本次全部工具返回：

```text
{PROJECT_ROOT}/audit/{appName}--{appId末8位}/{runId}/
├── evidence/
│   └── {对象名称}--{对象ID末8位}.json
├── results.json
└── report.md
```

`archive` 模式的文件命名使用"对象名称--对象 ID 末 8 位"；名称中的 `/\:*?"<>|` 替换为 `-`。原始文件路径记录在 `sources[sourceId].rawPath` 中。

每次 MCP 接口成功返回后，在当前会话中即时分析返回内容，提取检查所需的字段和值记入 `sources` 和 `facts`，然后丢弃原始返回。不得先在会话中完成结论、最后再虚构来源元数据。

快速筛查使用 `ephemeral` 模式，直接在会话中完成，不创建运行目录。

## 五、逐项检查与结果文件

主 Agent基于工具返回逐项判断，将以下内容写入 `results.json`：

```json
{
  "runId": "20260826-xxxx",
  "appId": "app-id",
  "appName": "应用名称",
  "evidenceMode": "compact",
  "requestSummary": "诊断指定应用并优化其中全部工作流",
  "scopeReason": "应用 ID 仅用于定位；工作流是用户明确指定的审查范围",
  "mode": "target",
  "repairIntent": true,
  "targetType": "asset",
  "targetAssetType": "workflow",
  "targetScope": "category",
  "targetDimension": null,
  "target": "应用内全部工作流",
  "collectionBudget": {
    "worksheetStructureCalls": {"limit": 50, "used": 8},
    "worksheetDslCalls": {"limit": 10, "used": 3},
    "otherDetailCalls": {"limit": 30, "used": 12},
    "dependencyDepthLimit": 1,
    "limitReached": false
  },
  "sources": {
    "S1": {
      "tool": "get_workflow_structure",
      "objectType": "workflow",
      "objectId": "workflow-id",
      "format": "json",
      "capturedAt": "2026-08-28T10:00:00+08:00"
    }
  },
  "selectedCheckIds": ["CHK-BIZ-006"],
  "checks": [
    {
      "checkId": "CHK-BIZ-006",
      "dimension": "business",
      "status": "pass",
      "facts": [
        {
          "sourceId": "S1",
          "path": "trigger.fields",
          "value": ["status"]
        }
      ],
      "actualEvidence": "已发布流程仅由 status 字段更新触发",
      "coverage": {
        "inspected": 1,
        "total": 1
      }
    }
  ],
  "observations": [
    {
      "title": "核心流程职责存在重叠",
      "sourceIds": ["S1"],
      "actualEvidence": "两个已发布流程处理相同状态变更并重复发送通知",
      "impact": "后续维护时需要同步修改两套逻辑，容易产生行为差异",
      "suggestion": "评估合并公共处理逻辑或抽取可复用子流程",
      "requiresBusinessConfirmation": true
    }
  ]
}
```

`archive` 模式时，触发升级的来源在 `sources` 中增加 `rawPath`，并在运行级增加 `archiveReason`：

```json
{
  "evidenceMode": "archive",
  "archiveReason": "external_approval",
  "sources": {
    "S1": {
      "tool": "get_role_details",
      "objectType": "role",
      "objectId": "role-id",
      "format": "json",
      "capturedAt": "2026-08-28T10:00:00+08:00",
      "rawPath": "evidence/管理员--a1b2c3d4.json"
    }
  }
}
```

`fail` 检查项的 finding 示例：

```json
{
  "findingId": "CHK-BIZ-006:workflow:workflow-id",
  "assetType": "workflow",
  "assetId": "workflow-id",
  "assetName": "订单状态更新",
  "sourceIds": ["S1"],
  "actualEvidence": "已发布流程未限制触发字段，任意字段更新都会触发",
  "expectedRule": "更新触发工作流应指定必要触发字段，避免任意修改误触发。",
  "repairBoundary": "修改已发布工作流前需要确认当前无待处理实例",
  "requiresExternalApproval": false
}
```

结果必须满足：

- `sources` 记录本次运行调用的所有 MCP 工具及其目标对象。每个 source 必须包含 `tool`、`objectType`、`objectId`、`format` 和 `capturedAt`。`sourceId` 是运行内唯一的不透明标识（如 `S1`、`S2`），不编码语义。
- `pass`、`fail` 必须包含非空 `facts` 数组和 `coverage` 对象。每个 fact 包含 `sourceId`（引用顶层 `sources`）、`path`（返回结果中的字段路径）和 `value`（观察到的值）。
- `coverage` 包含 `inspected`（已检查对象数）和 `total`（当前检查项需要覆盖的对象总数）。`total` 允许为 `null`，表示总量无法确定。
- `total` 为 `null` 时禁止判定 `pass`，只能记为 `not_evaluated`。`pass` 时必须 `inspected == total`。`inspected` 不得大于 `total`（当 `total` 非 null）。
- `pass` 必须填写 `actualEvidence`，简述证据中直接支持通过结论的事实，不能只写"正常""符合要求"等空泛结论。
- `fail` 必须包含非空 `findings` 数组。每个 finding 使用 `{checkId}:{assetType}:{assetId}` 作为稳定 `findingId`，并记录 `assetType`、`assetId`、`assetName`、`sourceIds`、`actualEvidence`、`expectedRule`、`repairBoundary` 和 `requiresExternalApproval`。
- finding 的 `sourceIds` 必须非空，所有 ID 存在于顶层 `sources`，且属于其父检查项 `facts` 使用过的来源。
- finding 的 `requiresExternalApproval` 是布尔值。当 P0 finding 的修复需要当前 Agent 和用户之外的第三方审批时设为 `true`，触发 `archive` 升级。
- finding 的 `expectedRule` 必须逐字复制 `audit-checks.md` 中该 `checkId` 的检查规则，不得扩写规则以容纳不相关问题。
- `not_applicable` 必须填写 `reason`；`not_evaluated` 必须填写非空 `missingEvidence` 数组，不得把原因文字伪装成证据来源。`not_evaluated` 可以包含部分 `facts` 和 `coverage`（当已检查部分对象但未能覆盖完整范围时）。
- 严重度和扣分只从 `audit-checks.md` 读取，不在 finding 中重复维护。
- 必须逐项形成结论；禁止使用"预先列出失败项，其余检查项全部默认 `pass`"的生成逻辑。尚未实际判断的检查项一律写为 `not_evaluated`。
- `observations` 可省略或为空，最多保留 5 条。每条观察必须包含 `title`、`sourceIds`（引用本次运行的 `sources`）、`actualEvidence`、`impact`、`suggestion` 和 `requiresBusinessConfirmation`。
- 观察不得包含 `checkId`、严重度、扣分、状态或 `findingId`，不参与覆盖率、风险和评分。缺少直接证据的猜测不得输出；需要业务事实确认时将 `requiresBusinessConfirmation` 设为 `true`。
- `repairIntent` 只控制报告后是否主动展示修复候选，不改变审查范围、评分规则或写入权限。
- `collectionBudget` 必须记录本次实际用量；达到上限时将 `limitReached` 设为 `true`，并把受影响的检查项记为 `not_evaluated`。

执行：

```bash
python3 {SKILL_DIR}/scripts/audit_calc.py {PROJECT_ROOT}/audit/{appName}--{appId末8位}/{runId}/results.json
```

脚本校验路由字段、检查项覆盖、来源和事实引用、Finding 规则绑定，并在适用时计算分数和来源统计；不负责取证或业务判断。快速筛查不运行该脚本。将脚本输出写入报告，不得手工另算一套分数。

## 六、报告输出规格

全量和定向审查无论覆盖率是否达到评分门槛，都必须生成当前运行目录下的 `report.md`。覆盖率不足时，报告明确标记 `incomplete`、列出未评估项，并且不输出正式分数或星级；不得以覆盖不足为由省略报告。

### 6.1 全量审查报告规格

报告按以下结构输出，**严禁机械平铺几十项重复条目**：

1. **审查概览看板**：状态、风险等级、覆盖率和规模统计；增加简短的来源覆盖摘要，列出总来源数、按工具类型分布和取证预算实际用量及是否触顶；仅在状态为 `complete` 时展示综合得分、星级及五维得分表；
2. **逐维度审查（按 5 大业务维度独立分节）**：
   - 按 **结构健康度、业务完整度、用户体验、性能与容量、安全与维护** 独立成章；
   - 每章包含核心现状简评；仅在状态为 `complete` 时展示该维度得分评级；
   - **同类问题聚合**：同一检查项若涉及多个对象（如 20 个视图列超标、7 张表缺少 Divider），**必须合并为一条 Finding 并列出涉及对象清单与批量治理建议**，标明 `checkId`、严重度（P0/P1/P2）与业务影响；
3. **AI 补充观察（不计分）**：仅在存在观察时输出，最多 5 条；每条说明对象、直接证据、可能影响、建议及是否需要业务确认，并明确不影响正式评分；
4. **未评估项与人工核验 (Manual Obligation)**：列出因平台不可见需人工核验的检查项与行动建议；
5. **优先修复路线图**：按业务影响与 P0 → P1 排序，列出最具治理价值的 **Top 5 正式行动项**；高价值观察可以在其后单独列为"待确认优化机会"，不得混入正式 Finding 排序。

### 6.2 其他模式输出规格

- **定向维度审查**：仅输出目标维度得分、评级、该维度的聚合 Findings、补充观察与未评估项；不得输出全局综合分或星级；
- **定向资产类别审查**：输出目标资产总数、目录覆盖数、详情读取数、未深入数、逐项结论及可选补充观察；不输出应用综合分、星级或五维得分；
- **定向具体对象审查**：输出目标对象、实际检查覆盖、逐项结论（涉及对象、问题与建议）及可选补充观察；不评分；
- **finding 复查**：输出原 finding ID、当前状态（已解决/未解决/无法判断）与复查证据；不评分；
- **快速筛查**：输出已查看范围与候选风险清单；必须明确声明"仅为部分覆盖"，不评分。

### 6.3 完成门槛

全量和定向审查只有同时满足以下条件，才能在会话中宣布"审查完成"：

1. `results.json` 与 `report.md` 已写入并回读成功；
2. `audit_calc.py` 执行成功，报告中的覆盖率、风险和适用分数与脚本输出一致；
3. 报告模式、目标和评分范围与路由锁及 `results.json` 完全一致，不出现未定义的混合模式；
4. 报告的来源统计与脚本输出的 `sourceInventory` 一致；对象总数只能来自目录接口返回，不得把列表数量写成详情覆盖数量；
5. 所有 `sourceIds` 引用存在于顶层 `sources`；finding 的 `sourceIds` 属于其父检查项 `facts` 使用过的来源；
6. `archive` 模式时，`sources` 中包含 `rawPath` 的条目对应的文件必须存在于当前运行目录内；
7. 每个选中检查项恰好有一个状态，每个失败项都有结构化 finding；
8. 不存在尚未评估的 P0 检查项；
9. 会话最终回复同时提供报告和结果文件路径。

`audit_calc.py` 返回 `incomplete` 不代表执行失败；仍应按上述要求生成不含正式评分的报告。

会话最终回复保持简洁，只说明审查状态、有效覆盖率或正式分数、3～5 个优先正式问题、必要时 1～2 条高价值补充观察，以及报告与结果文件路径；不要复述完整取证过程或工具调用流水。

## 七、衔接 Modify

`repairIntent=true` 时，在报告摘要后按风险和业务价值展示 2～5 个候选 finding，并请用户选择；高价值补充观察可以另行展示，但不得伪装成 finding 或自动视为已授权修改。用户已经用 finding ID、严重度范围等方式明确修复范围时，可以直接使用该范围；用户明确选择某条观察时，将其作为新的直接修改请求，必要时先确认目标状态。

用户选择修复范围后，回到根 `SKILL.md` 的"审查后修复"流程：

1. 只处理用户选择的 finding；
2. 审查证据只用于定位线索；
3. 修改前重新核对环境、组织、应用和目标对象，并读取实时配置；
4. 按 `workflows/modify.md` 重新读取实时状态、判断必要连带修改、按风险确认并执行回读验证。
