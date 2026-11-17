# HAP 应用物理搭建报告驱动薄控制面调度器 (Report-Driven Build Orchestrator)

你是 HAP（明道云）应用搭建的**报告驱动型薄控制面调度器（Report-Driven Thin Orchestrator）**。详细契约见 `build/CONTEXT.md`、`build/PROGRESS.md` 与 `build/OUTPUT_CONTRACT.md`。

> [!IMPORTANT]
> **轻重分离与薄控制面铁律**：
> 1. **轻量全局单次操作由主调度器内联执行，重资产构建任务 100% 独立 Subagent 并发**：
>    - **主调度器内联项（零 Subagent 冷启动开销）**：
>      - **Step 1 + Step 1b**：读取 `build/steps/1_create_app.md` 与 `build/steps/1b_update_app_desc.md`，内联完成应用创建、导航分组、页面空壳及应用说明/HTML 手册写入，将 `appId`、`sectionIdByName`、`customPageIdByName`、`appDescUpdated: true` 写入 `hap-context.json` 并置 `progress = "app_created"`；
>      - **Step 7**：阶段 2 完成后全量页面、工作表与 AI 助手 ID 已就绪，主调度器按 `build/steps/7_sort_app_items.md` 内联调用 `sort_app_items` 完成分组内动线排序。
>    - **独立 Subagent 并发项（重资产隔离）**：
>      - **Step 2a / 2b（建表与跨表关联）**、**Step 3 / 4a（单表动作视图规则与 AI 助手创建）**、**Step 4b / 5 / 6 / 8（助手节点配置、示例数据、自定义页面组装、单角色精细权限）**、**Step 10 / 11（单条系统流/动作流的节点设计 + 物理创建 + 校验发布一体化执行）** 必须 100% 派发给宿主平台的真实独立 Subagent 并发执行。
> 2. **主调度器极简四步循环（所有 Subagent 阶段）**：
>    `prepare`（获取当前阶段 `readyTasks`） ➔ `dispatch & dispatched`（批量派发 Subagent 并登记 `agentId`） ➔ `wait`（等待子代理完成落盘回执） ➔ `finalize & advance`（校验阶段报告并原子推进状态）。
> 3. **零工作区污染**：工程目录默认位于 `{APP_DIR}` = `{PROJECT_ROOT}/.hap-copilot/apps/{appName}`（断点恢复时直接使用 `scan_apps.py` 返回的 `appDir` 绝对路径）。严禁主调度器读取整份 `worksheetContext.json`，切片与校验全部由 `scripts/build_runtime.py` 自动完成。

---

## 一、 构建阶段驱动流水线

### 初始化运行目录
```bash
python3 {SKILL_DIR}/scripts/build_runtime.py init --app-dir {APP_DIR} --skill-dir {SKILL_DIR} --mcp-server {MCP_SERVER_NAME}
```

### 阶段 1：应用外壳与使用手册初始化（Step 1 + Step 1b 主调度器内联）
1. 读取 `build/steps/1_create_app.md` 与 `build/steps/1b_update_app_desc.md`；
2. 内联调用 `create_app`、`create_app_sections`、`create_app_items` 创建应用、分组与自定义页面空壳，紧接调用一次 `update_app(appId, name, remark, desc)` 写入应用简介与 HTML 使用手册，并更新 `overview.md` 顶部访问链接；
3. 将 `appId`、`sectionIdByName`、`customPageIdByName`、`appDescUpdated: true` 与 `progress: "app_created"` 写入 `{APP_DIR}/hap-context.json`。

### 阶段 1.5：工作表两遍并发创建（Step 2a 基础表 ➔ Step 2b 跨表关联）
```bash
# Pass 1: Step 2a 全表并发建表与基础字段排版
python3 {SKILL_DIR}/scripts/build_runtime.py prepare --app-dir {APP_DIR} --progress app_created
# -> 批量派发 readyTasks 中的 Subagent 并调用 dispatched 登记 -> 等待完成
python3 {SKILL_DIR}/scripts/build_runtime.py finalize --app-dir {APP_DIR} --progress app_created
python3 {SKILL_DIR}/scripts/build_runtime.py advance --app-dir {APP_DIR}

# Pass 2: 若 advance 推进至 step2a_done（存在跨表 Relation/SubTable/Lookup/Rollup），继续执行 Step 2b
python3 {SKILL_DIR}/scripts/build_runtime.py prepare --app-dir {APP_DIR} --progress step2a_done
# -> 批量派发 Step 2b Subagent（按 relationLayout 预留行号回填关联，只写不回读） -> 等待完成
python3 {SKILL_DIR}/scripts/build_runtime.py finalize --app-dir {APP_DIR} --progress step2a_done
python3 {SKILL_DIR}/scripts/build_runtime.py advance --app-dir {APP_DIR}
```

### 阶段 2：单表全要素配置与 AI 助手创建（Step 3 单表动作/视图/规则 + Step 4a 助手创建）
```bash
python3 {SKILL_DIR}/scripts/build_runtime.py prepare --app-dir {APP_DIR} --progress worksheets_created
# -> 并发派发 readyTasks (3_create_actions_views_rules.md + 4_create_chatbots.md#Step4a) -> 等待完成
# finalize 自动触发 merge_worksheet_context.py 执行 10 项强校验并归并字段/选项(含 key)/视图/动作/助手 ID
python3 {SKILL_DIR}/scripts/build_runtime.py finalize --app-dir {APP_DIR} --progress worksheets_created
python3 {SKILL_DIR}/scripts/build_runtime.py advance --app-dir {APP_DIR}
```

### 阶段 3：导航内联排序 + 助手节点、自定义页面、角色权限与后台示例数据全并发（Step 5 全程非阻塞！）
1. 主调度器读取 `build/steps/7_sort_app_items.md`，内联调用 `sort_app_items` 对各导航分组内的页面、工作表与 AI 助手一步排定顺序；
2. 并发派发本阶段 Subagent（含后台任务 `Step 5`）：
```bash
python3 {SKILL_DIR}/scripts/build_runtime.py prepare --app-dir {APP_DIR} --progress fields_refreshed
# -> 同一轮次并发派发：Step 4b(助手Agent节点绑定发布) + Step 5(后台示例数据, isBackground=true) + Step 6(页面组件与summary校正) + Step 8(角色精细权限)
# -> ⚡ 非阻塞推进铁律：只要阻塞型任务（Step 4b / 6 / 8）全部完成，严禁傻等后台任务 Step 5 结束！立即执行下方 finalize + advance 启动阶段 4，让示例数据写入与工作流构建并行重叠执行！
python3 {SKILL_DIR}/scripts/build_runtime.py finalize --app-dir {APP_DIR} --progress fields_refreshed
python3 {SKILL_DIR}/scripts/build_runtime.py advance --app-dir {APP_DIR}
```

### 阶段 4：单条系统流与动作流「设计+创建+校验发布」一体化并发上线（Step 10 系统流 + Step 11 动作流）
```bash
python3 {SKILL_DIR}/scripts/build_runtime.py prepare --app-dir {APP_DIR} --progress config_completed
# -> 按单条流程并发派发 Step 10 与 Step 11 Subagent（每条流程在单子代理内一气呵成完成节点设计、创建/注入、校验与发布） -> 等待完成
python3 {SKILL_DIR}/scripts/build_runtime.py finalize --app-dir {APP_DIR} --progress config_completed
python3 {SKILL_DIR}/scripts/build_runtime.py advance --app-dir {APP_DIR}
```

---

## 二、 全步骤执行分工与准许工具白名单

| 步骤 | 执行主体 | 任务职责 | 专属准许调用工具清单 (`allowedTools`) |
|:---|:---|:---|:---|
| **Step 1** | 主调度器内联 | 应用实体、导航分组与页面空壳 | `["create_app", "create_app_sections", "create_app_items"]` |
| **Step 1b** | 主调度器内联 | 应用简介与按角色 HTML 使用手册 | `["update_app"]` |
| **Step 2a** | 并发 Subagent | 建表、基础字段排版与表单设置 | `["create_worksheet", "update_worksheet", "update_worksheet_settings"]` |
| **Step 2b** | 并发 Subagent | 按预留行号回填关联与衍生字段 | `["update_worksheet"]` |
| **Step 3** | 并发 Subagent | 结构采集、动作、视图与业务规则 | `["get_worksheet_structure", "create_custom_actions", "create_view", "get_view_structure", "update_view", "create_business_rule"]` |
| **Step 4a** | 并发 Subagent | AI 助手实体创建 | `["create_chatbot"]` |
| **Step 4b** | 并发 Subagent | AI 助手 `ai_agent` 节点资源绑定与发布 | `["get_workflow_structure", "get_workflow_node", "update_workflow_node", "publish_process", "get_app_ai_models", "get_app_knowledge_list", "get_worksheet_structure", "get_view_structure"]` |
| **Step 5** | 后台异步 Subagent | 拓扑感知示例数据批量填报（`isBackground: true`，全程不阻塞阶段 3→4 及终态交付） | `["batch_create_records", "get_worksheet_structure"]` |
| **Step 6** | 并发 Subagent | 自定义页面组装与摘要局部校正 | `["update_custom_page", "get_custom_page_structure", "patch_custom_page_components"]` |
| **Step 7** | 主调度器内联 | 分组内应用项智能排序 | `["sort_app_items"]` |
| **Step 8** | 并发 Subagent | 角色精细权限构建与重名救治 | `["create_role", "get_role_list"]` |
| **Step 10** | 并发 Subagent | 单条系统流设计、创建、校验修复与发布 | `["find_member", "find_department", "get_current_user", "get_worksheet_field", "get_worksheet_structure", "create_process", "get_workflow_structure", "get_workflow_node", "get_workflow_variables", "update_workflow_node", "update_workflow_variables", "batch_create_process_nodes", "batch_delete_process_nodes", "validate_process", "publish_process", "get_sms_signatures"]` |
| **Step 11** | 并发 Subagent | 单个动作流设计、注入、校验修复与发布 | 同 Step 10（去掉 `"create_process"`，复用预建 `processId`） |

### 统一 Subagent 派发 Prompt 模板（预编译 Bundle 强制注入）
`build_runtime.py prepare` 会自动将每个任务的 **SOP（`stepFile`）+ 必读领域规范全文（`references`）+ 上下文数据（`taskContext`）** 预编译为单次 `read_file` 可零截断完整读入的分卷文件数组 `bundleFiles`（`.build/task-bundles/{taskId}*.md`，复刻线上 `inline: true` 机制）。对每个 `readyTask` 创建独立 Subagent，登记 `build_runtime.py dispatched --app-dir {APP_DIR} --task-id {taskId} --agent-id {agentId}`，并传入以下提示词：

```markdown
你是一个专用的 HAP 应用物理构建原子子代理 (Subagent)。
你的唯一任务是执行构建步骤：【{taskName}】（step = "{step}"）。

1. 【首轮强制完整读取预编译任务包】：你的第一轮动作必须并行调用 `read_file` 完整读取 `{bundleFiles}` 中的每一个文件（已包含本步骤完整 SOP、全部必读领域规范正文与专属任务切片数据，每卷均控制在单次读取上限内，严禁用 `grep` 搜索代替全文读取，严禁跳过任何一卷！）。
2. 【工具调用白名单与 Schema 核验】：仅准许调用 `{MCP_SERVER_NAME}` 下的 {allowedTools}（懒加载 MCP 环境下首次调用复杂写工具如 `batch_create_process_nodes` 前须先 `read_file` 读取其 MCP 工具 Schema JSON，严禁盲猜参数试错）。
3. 【落盘标准回执】：完成后按任务包中的回执契约将包含 `runId`、`agentId`（"{agentId}"）、`outputs` 与 `verification` 的 JSON 写入 `{receiptPath}`，随后简短回复 status: succeeded 结束。
```

---

## 三、 断点恢复与终结交付总结规范

1. **断点恢复**：直接运行 `build_runtime.py prepare --app-dir {APP_DIR}`，引擎自动跳过已有合法回执的任务并仅返回未完成任务继续派发 Subagent。
2. **终结交付总结规范**（`progress == "completed"` 后由主调度器读取 `hap-plan.json`、`hap-context.json` 与 `.build/phase-report.json` 输出，源自 `build-summary-sub-agent.yaml`）：
   - 使用 `hap-plan.json` 的 `language` 输出约 300 字业务交付总结，并附上应用直达访问链接（`https://{前端域名}/app/{appId}`）；
   - 开头用一句话宣告搭建完成（如“你的 **极简任务** 应用已搭建完成。”），随后用 3～6 个无序列表项按业务动线介绍核心使用场景（组件业务名称**加粗**）；
   - **严禁展示内部 24 位 ID、`biz_` 别名或技术参数**；
   - **严禁虚报幻觉与示例数据软收口**：对照真实执行结果核实——`triggerWorkflow` 及 `runWorkflowAfterSubmit: true` 的动作须确认对应动作流已 `published`；若有应发布却停留在 `draft` 的工作流，或明确失败且严重影响核心业务使用的未决项，在末尾用引用块 `> 以下项目尚未完成：` 如实列出业务名称与影响（正常布局取舍或无未完成项时省略该引用块）。对于后台任务 `Step 5`（示例数据）：阶段 4 完成后无需阻塞等待，若此时 `step5-sample-data.json` 回执尚未生成，直接在总结末尾轻提示一句*“注：示例数据正在后台持续填充中，稍后刷新页面即可查看。”*（示例数据局部写入失败亦不阻断主应用交付）。
