# HAP 已有应用修改工作流

本文件定义 Modify 的唯一执行流程。在本地 Agent 环境中，应用修订默认采用 **“主 Agent 按需切片加载规范 + 当前会话内联闭环”** 的高效架构：不拆分子代理往返，直接复用同轮实时读取快照完成最小差异写入与必要核验。

---

## 1. 端到端核心流程

```text
明确修改目标与模式 (direct / audit_repair)
→ 运行 resolve_context.py 按命中领域加载最小规则包
→ 定向读取线上目标与一层必要直接依赖
→ 按 impact-map 分类 (requested / required_linked / recommended / no_change / unresolved)
→ 按 safety-rules 判定二元风险：low 连续执行 / high 展示方案确认（支持按需备份）
→ 按依赖顺序合并最少物理写入并传递真实对象 ID
→ 按效率优先纪律完成必要核验与异常回读防重
→ 用纯业务名称向用户简洁汇报结果与未完成/人工事项
```

线上实时状态是唯一事实源。严禁用本地历史计划、示例 ID 或旧对话快照代替实时核对；未经用户明确选中的 `recommended` 建议项严禁擅自写入。

---

## 2. 修改模式、领域标签与沟通准则

### 2.1 修改模式
- **`direct`**：用户明确说明对象要达到的目标状态，或明确要求新增、修改、删除、启停、数据迁移或少量示例数据写入；
- **`audit_repair`**：用户指定修复 Audit 报告中的具体 `findingId`（Finding 快照仅作定位线索，必须重新读取线上实时状态）。
- 若用户仅查询具体配置事实（如查看公开表单链接、查看角色当前权限、查看字段配置）或排查具体运行现象（如“为什么这条工作流没触发”），直接调用对应领域的最小只读工具回答用户，全程保持**只读**，不进入重型 Audit 也不落盘报告文件；若用户要求评估搭建合理性或只说宽泛“优化”而未给出明确目标状态，则路由至 `workflows/audit.md`。
- **URL 与 ID 精准定位支持**：若用户发送明道云网页链接（如 `/app/{appId}/{sectionId}/{worksheetId}/{viewId}`）或对象 ID，直接从 URL 提取目标 `appId`、工作表/页面/助手 ID 与 `viewId` 直达读取，无需重复扫描应用或工作表列表；目标应用或重名对象不唯一时，主动提示用户确认或直接发送页面链接/ID。

### 2.2 12 大标准修订领域标签 (`--assets` / `--domains`)
`app_navigation`、`worksheet`（含字段/布局/设置/规则/索引/工具栏筛选器）、`view_action`、`role_permission`、`custom_page`（画布与外链）、`worksheet_chart`、`chatbot`、`print_template`、`public_form`、`external_portal`、`workflow`、`record_data`。

### 2.3 用户沟通与展示红线
1. **隐藏内部标识**：面向用户的自然语言回复、澄清问题与确认方案中，只使用应用、分组、工作表、字段、视图、页面、角色、工作流的**业务名称**，严禁向用户裸露 24 位内部 ID、`biz_` 别名、批次号或底层 JSON 参数（真实 URL 链接除外；同名对象用所属分组或业务用途区分）。
2. **顾问式结构化点选消歧（强制优先调用 `ask_question`）**：
   - 当任务指代不明（如多张同名表）、新建宽泛对象缺少关键参数（如“加个自定义页面”需确定主题用途、所属分组、开放角色），或存在推荐连带选择（如承接分组、配套角色授权、可选示例数据）时，**必须优先调用宿主原生 `ask_question` 工具**将互不依赖的问题合并为单次点选卡片（首项给 `(Recommended)` 专业建议；角色授权与推荐配套题设 `is_multi_select: true` 支持多选，并保留“仅管理员可见 / 暂不配置”选项；用户需要自定义名称时可直接使用卡片自带的自由输入框）。
   - **正文不重复抄题**：调用 `ask_question` 前，正文只用 1～2 句话简述当前应用的真实分组/页面/表结构现状并声明当前未做写入，**严禁在正文里再输出 1/2/3 问题与选项列表**。**澄清轮保持零写入**。
3. **备份提示与自动备份衔接**：遵循 `modify/safety-rules.md` 第 三 节，纯文案/样式/显隐/排序免提醒；首次实质结构或数据修改单次友好提示可备份，命中 `high` 高危确认时可按用户意愿先调 `create_app_backup` 完成结构备份再执行写入，后续轮次严禁重复提示。

---

## 3. 最小上下文渐进加载（严禁盲吞全库文档）

确定本次涉及的目标领域后，立即运行一次上下文切片引擎：

```bash
python3 {SKILL_DIR}/scripts/resolve_context.py \
  --mode modify \
  --assets {domain1,domain2} \
  --render
```

1. **直接使用已渲染内容**：脚本会自动输出二元风险与 14 类删除直通底线、`modify/impact-map.md` 对应领域的连带表格，以及 `modify/modify_guide.md` 对应领域的操作卡（含推荐精确 MCP 工具集），**严禁再去通读 `modify_guide.md` 全文**。
2. **大体积指南与底层 Spec 按章节检索**：
   - 新建业务对象、设计跨表关系/角色、重做工作流或选型外部门户/打印模板/公开表单/物理索引时，先按章节加载设计指南，例如：
     ```bash
     python3 {SKILL_DIR}/scripts/resolve_context.py \
       --file references/hap-app-design-guide.md \
       --section "打印模板"
     ```
   - 对参考清单列出的 `references/hap-domain-*-spec.md`（及能力边界 `modify/execution-boundaries.md`），仅在构造具体复杂参数（如 `CustomField` React 脚本、四类业务规则条件树、页面 48 栅格组件、打印占位符）时用 `--file ... --section ...` 或局部读取查阅对应章节，同一会话内已加载内容直接复用。
3. 探查线上依赖后若发现涉及新的连带领域（如新建表需接续 `view_action` 和 `role_permission`），仅补读新增领域的章节。

---

## 4. 实时探查、风险判断与执行闭环

> **⚠️ Lazy MCP 调用与 `appId` 必传提醒**：本工作流及领域规范中的 `tool(param: ...)` 均为重点参数简写；首次通过 `call_mcp_tool` 调用某个工具前必须先 `read_file` 读取其 `.json` Schema 核准 `required` 必填项，且所有应用内对象接口（含工作表、视图、页面、工作流、机器人、角色、记录等）**必须显式传入 `"appId"`**（若报 `10001` 或单点 `401`，优先核查是否漏传 `"appId"`）。

1. **按决策缺口最小读取**：
   - 工作表概览默认用 `get_worksheet_structure(responseFormat: "md")`（涉及表单栅格排版或写后核对布局时直接用 `"dsl"`）；
   - 已有目标 ID 直接复用，不为确认已知对象存在重复拉取全应用列表；
   - 存量记录修改在形成确认方案前，必须先用实际目标筛选调用 `get_record_list(includeTotalCount: true, pageSize: 1, pageIndex: 1)` 探测准确数量；
   - 删除与关闭操作严格按 `modify/safety-rules.md` 的 14 类最小核查条件执行，不全应用遍历工作流。
2. **二元风险决策（`low` 直通 vs `high` 确认）**：
   - **`low`（常规）**：范围明确且无未决业务问题时，直接在当前轮次按依赖顺序连续执行完成（含目标必需的 `required_linked` 低风险配套，如默认视图翻新、必要导航排序及已选定角色的最小非敏感权限）；
   - **`high`（高危或必须确认条件）**：先说明准确目标、连带范围、数据/权限影响与恢复方式（若同时含不可自动执行的人工部分，先说明人工路径再确认自动部分），收到用户明确确认后再执行写入；若全部不可自动执行，直接给出人工操作路径，不发无意义确认。
3. **内联执行与超大任务弹性分批**：
   - **默认主 Agent 内联执行**：按 `modify/impact-map.md` 的固定依赖顺序（如 `worksheet → view_action → app_navigation → role_permission`）逐步调用推荐工具集，用前序步骤真实返回的 ID（如 `worksheetId`、`defaultViewId`、`pageId`、`chatbotId`）驱动下一步；
   - **超大规模改造可选分批**：仅当单次获批方案涉及极多独立重资产（例如同时新建/重构 >5 张工作表或 >3 条复杂工作流，预估工具调用 >30 次可能挤压上下文）时，若宿主支持独立子代理，主 Agent 可将已确定真实 ID 的独立领域子任务附带对应 `modify_guide` 章节委派子代理执行并汇总结果。
4. **验证与异常处置**：
   - 遵循 `modify/safety-rules.md` 第 五 节：明确同步成功回执直接记账；全量覆盖、数组替换、页面布局改动及数据迁移做一次最小充分回读核验；
   - 超时、断流或 `outputSchema` 返回校验异常时**先回读实际状态**，严禁盲目重放创建或发布；局部成功时保留已完成对象并如实报告剩余缺口，严禁擅删已建对象伪造回滚。

---

## 5. 跨轮次高风险日志与 Audit 修复衔接

- **轻量运行日志（仅高危/批量数据/多阶段跨轮次任务按需落盘）**：普通同轮修订不落盘本地文件；涉及 `high` 批量数据迁移或跨多轮恢复的复杂任务，可在 `{PROJECT_ROOT}/.hap-copilot/apps/{appName}/modify-runs/{runId}/execution-log.json` 记录范围、已完成项、真实新建 ID 与待办人工项（恢复执行时仍须先核对线上实时状态）。
- **Audit 修复衔接**：进入 `audit_repair` 时，先核对环境、组织、`appId` 与用户选中的 `findingId`，重新读取目标与直接依赖建立实时基线，只修复被选中的 Finding 及其 `required_linked` 连带项，完成后按需复核原检查项。
