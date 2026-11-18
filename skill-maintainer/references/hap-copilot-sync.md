# Copilot 与 AgentService 的共享内容及同步规则

本文说明哪些内容共享、哪些文件经过本地适配、规则应在哪里维护，以及当前同步脚本的执行方式和检查边界，供 Skill 维护者使用。实现位于本维护 Skill 的 [同步脚本](../scripts/sync_hap_copilot.py)；同步清单和映射以该脚本为准，本文解释其维护约定，不另行定义业务规则。

本文和同步工具属于维护侧资料，不放入公开发布的 `hap-app-copilot` 目录，也不从其 README 或业务入口引用。公开 Skill 可以保留来源说明，但不提供同步命令、维护工具入口或上游更新流程。

当前支持手动执行命令，将固定的 19 份共享规格镜像到目标 `hap-app-copilot`，并检查来源标记。它尚未实现 AgentService 全部新能力的一键发现、适配和更新。检查通过也不代表两端 Agent 行为完全一致。

## 1. 来源、目标与处理方式

| 项目 | 当前行为 |
|---|---|
| 默认来源 | 从脚本真实位置推导工作区布局，读取 `AI-work/Mingo/MDAgentService/assets/agents/prod` |
| 默认目标 | 与 `skill-maintainer` 同级的 `hap-app-copilot` |
| 输入 | 上游 `skills/{name}/SKILL.md` |
| 输出 | 本地 `references/{name}.md` |
| 方向 | AgentService 本地工作树 → 目标 Skill，单向覆盖 |
| 触发 | 维护者手动运行；脚本没有定时任务、文件监听或启动时自动更新机制 |

来源是本地文件，不是在线服务或远端仓库。脚本不会执行 Git fetch、pull、commit 或 push，也不验证本地代码是否已部署。源文件中的未提交修改同样会被读取；输出的 `prodGitHead` 仅是本地仓库当前 HEAD 的短哈希，不能证明文件内容全部来自该提交。无法读取 HEAD 时显示 `unknown`。

写入前，脚本会统一 CRLF 换行为 LF、剥离符合格式的 YAML frontmatter、按正则改写匹配到的 `skills/hap-*` 引用，并去掉末尾空白、补上一个换行。因此这是正文规范化后的镜像，不是源文件的逐字节复制，也不复制源 Skill 的其他资源文件。

## 2. 当前同步范围

`SHARED_SKILL_NAMES` 是固定白名单，共 19 项。

| 类别 | Skill 名称 |
|---|---|
| 通用指南与资源（5） | `hap-app-design-guide`、`hap-workflow-design-guide`、`hap-chart-design-guide`、`hap-icon-palette`、`hap-sample-data-spec` |
| 应用、表与字段（4） | `hap-domain-app-spec`、`hap-domain-worksheet-spec`、`hap-domain-custom-field-spec`、`hap-domain-worksheet-index-spec` |
| 规则、视图与动作（3） | `hap-domain-business-rule-spec`、`hap-domain-view-spec`、`hap-domain-custom-action-spec` |
| 页面、图表与助手（3） | `hap-domain-custom-page-spec`、`hap-domain-worksheet-chart-spec`、`hap-domain-chatbot-spec` |
| 门户与权限（2） | `hap-domain-external-portal-spec`、`hap-domain-role-spec` |
| 工作流与记录（2） | `hap-domain-workflow-spec`、`hap-domain-record-data-spec` |

`hap-domain-print-template-spec` 不在镜像清单内；Copilot 使用 `modify/print-template-file.md` 承接本地文件制作。AgentService 的打印规范和提示词保持原样。

`--sync-specs` 只写这些规格文件。它不会改写目标 Skill 的入口、工作流、Build SOP、Modify 手册、安全规则、影响地图、Audit 指标或运行脚本。

### 2.1 文件分类与权威位置

下表本地路径相对于本仓库根目录，上游路径相对于 AgentService 的 `assets/agents/prod`。只有第一类要求正文镜像一致；同源适配文件保留业务依据，同时使用本地上下文、编排和交付方式。

| 类型 | Copilot 文件 | 权威来源及维护方式 |
|---|---|---|
| 共享镜像（19 份） | `hap-app-copilot/references/{name}.md`，名称见上表 | 上游 `skills/{name}/SKILL.md` 定义通用规则；先修改上游，再同步规范化正文，不在镜像中独立维护另一套规则 |
| 同源适配：方案（2 份） | `hap-app-copilot/plan/1a_plan_overview.md`、`hap-app-copilot/plan/1b_plan_schema.md` | 分别参考 `skills/hap-app-plan/SKILL.md`、`skills/hap-app-plan-builder-spec/SKILL.md`；人工维护本地方案与产物契约 |
| 同源适配：构建（12 份） | `hap-app-copilot/build/steps/` 下全部步骤 | 对应 `build-app/` 下的子 Agent YAML；准确映射以脚本的 `BUILD_STEP_YAML_MAP` 为准，人工提取并适配执行顺序与规则 |
| 同源适配：修订操作卡 | `hap-app-copilot/modify/modify_guide.md` | 对应脚本 `MODIFY_YAML_LIST` 中 12 个修订执行器；人工维护领域操作卡，不复制服务端任务包装 |
| 同源适配：公共修订规则 | `hap-app-copilot/modify/safety-rules.md`、`hap-app-copilot/modify/impact-map.md`、`hap-app-copilot/modify/execution-boundaries.md` | 分别参考上游 `hap-revision-safety` / `hap-revision-execution` / `hap-revision-backup`、`hap-revision-impact-map`、`hap-revision-execution-boundaries`；通用规则变化时核对并适配本地对应文件，具体来源见各文件“同源基准” |
| 同源适配：打印 | `hap-app-copilot/modify/print-template-file.md` | 参考服务端打印规范及执行器，保留本地精简文件规程；具体边界见第 7 节 |
| 同源适配：数据与审批 | `hap-app-copilot/workflows/data.md` | 参考上游 `app-query-agent.yaml` 与 `skills/hap-data-agent-rules/SKILL.md` 取数/展示准则，剔除 `<workEnd />` 等云端专属标签并扩展本地记录写入、审批处理与 PBP 触发分级门禁 |
| 本地运行支持 | `hap-app-copilot/SKILL.md`、`hap-app-copilot/HOST_ADAPTER.md`、`hap-app-copilot/workflows/`、`hap-app-copilot/build/CONTEXT.md`、`hap-app-copilot/build/OUTPUT_CONTRACT.md`、`hap-app-copilot/build/PROGRESS.md`、`hap-app-copilot/scripts/` | 本地入口、宿主工具适配、编排、上下文、回执和运行脚本；各职责文件定义本地运行契约，不要求与服务端文件全文相同 |
| 本地发布与界面支持 | `hap-app-copilot/README.md`、`hap-app-copilot/agents/openai.yaml`、`hap-app-copilot/.gitignore` | 安装说明、界面元数据及忽略配置，不属于共享镜像 |

### 2.2 “一致”的判断口径

- **逐字节一致**：原始文件连同 frontmatter、引用路径和换行全部相同；当前镜像流程不以此为目标。
- **规范化正文一致**：按第 1 节转换源文件后，与本地正文全文相同；这是 `--check` 对 19 份共享镜像的判定标准。
- **业务规则与行为一致**：需要核对提示词、执行顺序、工具契约和相关回归；来源标记存在或正文镜像一致都不能单独证明这一点。

## 3. 执行方式

要求 Python 3，且能够访问本地源目录和目标目录。以下变量须替换为当前机器的实际绝对路径；来源可以是主工作树，也可以是检出已确认提交的独立工作树：

```bash
HAP_SKILLS_ROOT='/absolute/path/to/hap-skill-work'
HAP_PROD_DIR='/absolute/path/to/MDAgentService/assets/agents/prod'
```

### 只检查，不修改文件

```bash
python3 "$HAP_SKILLS_ROOT/skill-maintainer/scripts/sync_hap_copilot.py" \
  --prod-dir "$HAP_PROD_DIR" \
  --copilot-dir "$HAP_SKILLS_ROOT/hap-app-copilot" \
  --check
```

需要机器可读报告时，在该命令后追加 `--json`。

### 同步共享规格，然后检查

```bash
python3 "$HAP_SKILLS_ROOT/skill-maintainer/scripts/sync_hap_copilot.py" \
  --prod-dir "$HAP_PROD_DIR" \
  --copilot-dir "$HAP_SKILLS_ROOT/hap-app-copilot" \
  --sync-specs --check
```

同步会直接覆盖对应目标文件，包括本地手工修改，不做差异合并、备份或冲突询问。执行前应确认源目录正确，并保留需要保留的本地改动。脚本逐文件写入，不提供事务或回滚：即使存在缺失源文件，其他可用文件仍可能已写入；此时返回失败，并跳过后续 `--check`。

### 可选：清理旧版规格

仅在确认需要清理旧版本文件时，为同步命令追加 `--clean-legacy`。它会在复制前删除 `LEGACY_REFERENCE_FILES` 固定清单中存在的旧文件，不会清理所有未识别文件，也不会修复其他文档对旧文件的引用。单独配合 `--check` 使用不会执行清理。

### 参数与返回值

| 参数 | 作用 |
|---|---|
| `--prod-dir` | 指定来源的 `assets/agents/prod` 目录；省略时使用默认布局 |
| `--copilot-dir` | 指定目标 Skill 根目录；省略时使用同级目录 |
| `--sync-specs` | 覆盖同步固定清单中的规格正文 |
| `--check` | 只读检查规格正文和本地来源标记 |
| `--clean-legacy` | 仅随同步执行固定旧文件清单清理 |
| `--json` | 将检查报告输出为 JSON；同步进度消息仍为普通文本，组合使用时整个标准输出不是纯 JSON |

至少需要 `--sync-specs` 或 `--check`。正常同步或检查通过返回 `0`；源文件缺失或检查未通过返回 `1`；命令行参数错误返回 `2`。其他文件系统异常可能直接中断脚本，且不会撤销已完成的写入。

## 4. 检查结果能证明什么

| 检查项 / JSON 字段 | 实际判断 |
|---|---|
| `missingSpecs` | 19 项清单中，上游源文件或本地目标文件是否缺失 |
| `driftedSpecs` | 本地正文是否与规范化后的源正文完全一致；报告中的哈希为 SHA-256 前 12 位，比较本身使用全文 |
| `extraReferenceFiles` | `references` 直接子级中，非隐藏普通文件的文件名主体是否不在白名单内；不递归检查子目录 |
| `missingBuildAnchors` | `BUILD_STEP_YAML_MAP` 对应的 12 份本地 Build SOP 是否存在，并包含预设 YAML 路径字符串 |
| `missingModifyAnchors` | 本地 Modify 手册是否存在，并包含 `MODIFY_YAML_LIST` 中的 12 个 YAML 路径字符串 |
| `localStepIssues` | `LOCAL_STEP_SOURCE_MAP` 指定的本地步骤是否存在、是否包含对应来源标记，以及这些上游来源文件是否存在；不比较正文语义 |
| `ok` | 上述六类问题是否均为空 |

**Build / Modify 检查不读取上游 YAML，不检查其存在性、内容或版本，也不比较两端规则语义。** 本地只要保留了路径字符串，即使上游行为已经变更，来源标记检查仍可能通过。本地步骤来源检查额外核实对应上游文件存在，但仍不比较两端内容或行为。

结构与引用检查需要另行执行：

```bash
python3 "$HAP_SKILLS_ROOT/skill-maintainer/scripts/audit_skill.py" \
  "$HAP_SKILLS_ROOT/hap-app-copilot"
```

该检查用于发现断链、孤立资源及明显重复等结构问题，不能替代业务语义审查或真实功能验证。

## 5. 当前未覆盖的部分

| 未覆盖项 | 影响与后续处理 |
|---|---|
| 新增、改名、删除的上游 Skill 自动发现 | 白名单外的变化不会自动纳入，也不会因上游新增文件而报错；需维护者判断范围并更新清单 |
| 白名单外的修订规则 | 如 `hap-revision-backup`、`hap-revision-safety`、`hap-revision-impact-map`、`hap-revision-execution-boundaries` 不由当前脚本镜像；需检查本地对应规则是否需要适配 |
| 主 Agent 和子 Agent YAML 行为更新 | 不转换提示词、分工或执行策略；需对照源码人工更新本地工作流和 SOP |
| Plan、Build、Modify、Audit 的本地契约与运行实现 | 不更新方案 Schema、DAG、回执校验、上下文加载映射或审查指标；需按具体变更联动维护 |
| MCP 接口和服务端代码变化 | 不读取工具 Schema 或 C# 实现，不更新工具数量门禁和参数调用约定；需另行核对实际工具能力 |
| Skill 附属资源 | 不复制源目录中的脚本、模板、图片或其他附件；需要时单独接入 |
| 版本基线与变更记录 | 不保存上次同步提交、文件哈希清单或同步历史，不能自动列出“自上次同步以来”的完整能力变化 |
| 自动化触发与远端更新 | 不拉取远端、不监听上游变化，也不自动提交、推送或部署 |
| 安全合并与功能验收 | 不保护目标手工修改、不原子更新、不回滚，也不验证 MCP 调用或业务结果 |

当 AgentService 出现新能力时，先确定它落在共享规格、Agent 行为、接口还是服务端实现中。白名单内的规格可以用当前命令同步；其他变化需要检查本地对应职责文件并完成适配、引用检查和相关行为验证。不能仅凭 `--check` 通过就宣布新能力已完整同步。

## 6. 领域通用规则与 AgentService 执行协议的归属

共享规格定义通用业务约束，服务端专用协议由对应 Agent 的 `prompt.system` 承接。目标提示词已有的协议直接复用，不复制第二份完整定义。角色、记录数据和外部门户的职责归属如下，上游路径相对于 `assets/agents/prod`。

| 共享规格 | 服务端专用协议及权威提示词 | 共享规格保留内容 / 本地核对点 |
|---|---|---|
| `hap-domain-role-spec` | `modify-app/role-permission-revision-sub-agent.yaml`：任务目标包装、可信用户变量与服务实现说明；`build-app/roles-build-sub-agent.yaml` 已有 viewContext 映射，直接复用 | 真实 ID、可信操作者、权限覆盖与保留、成员粒度和恢复保护保留；本地角色搭建 SOP 与修改手册使用本地上下文或实时查询 |
| `hap-domain-record-data-spec` | `modify-app/record-data-revision-sub-agent.yaml`：停止条件对应的状态回执、示例生成策略、createdIds；`modify-app/app-revision-agent.yaml` 已有入口边界、跨批次解析与依赖阻断，直接复用 | 授权、数量阈值、冻结、防重、对账、停止条件及两阶段结转保留；本地按真实 rowIds 执行，不构造服务端任务包装 |
| `hap-domain-external-portal-spec` | `modify-app/external-portal-revision-sub-agent.yaml` 与 `modify-app/app-revision-agent.yaml` 已有组织身份注入及附件交接协议，直接复用 | 当前组织、可信素材来源、素材优先级与权限边界保留；本地使用已核实组织 ID 和当前环境的附件读取能力 |

这三份规格随 19 项白名单同步，不自动转换 YAML。共享规则先改上游 Skill，再同步公开镜像；仅服务端协议变化时改对应提示词。涉及本地也需要的新能力时另行评估本地流程，专用协议不写入共享规格。当前同步检查不会发现提示词内容的遗漏，维护者须核对实际加载的提示词与关键流程回归。

## 7. Copilot 打印本地文件规程的维护

打印是本地适配项，不镜像完整的服务端 Skill。`modify/print-template-file.md` 按读取原件、制作副本、校验、原生 MCP 上传组织，只保留 HAP 占位符、文件兼容和交付要求；通用排版教程、沙箱协议和内部辅助模块不进入公开包。

- 上游业务依据为 `skills/hap-domain-print-template-spec/SKILL.md`；执行来源为 `modify-app/print-template-revision-sub-agent.yaml`，均相对于 AgentService 的 `assets/agents/prod`，由 AgentService 维护。
- 本地 `modify/modify_guide.md` 的打印操作卡负责纯配置与删除，文件新建或替换才读取 step；`hap-app-copilot/scripts/resolve_context.py` 返回按需 step 引用，不把文件制作正文注入纯配置任务。
- `--sync-specs` 仅覆盖 19 份镜像，既不生成打印镜像，也不覆盖 step。`--check` 检查 step 及其来源标记和上游文件存在；旧 `hap-app-copilot/references/hap-domain-print-template-spec.md` 若残留，会作为白名单外文件报告。该文件不在 `--clean-legacy` 的清理清单中，需维护者确认后单独处理。
- step 是面向本地的人工适配，当前工具不自动提炼上游业务规则，也不检测语义变化。上游占位符、兼容、权限或验收规则调整时，维护者对照变更更新 step；仅沙箱协议变化时不复制到本地。安全规则仍在本地公共文件维护，不在 step 复制授权策略或改变 170 工具门禁。
- [维护回归测试](../tests/test_print_step.py)覆盖：旧镜像不会被同步重新引入、step 不被覆盖、step 或来源缺失能报告、打印与模板别名均能加载 step，纯配置渲染不携带制作全文。同步工具、说明和验证脚本继续仅在维护侧。

## 8. 后续更新的维护顺序

1. **确定比较基线**：先在 AgentService 仓库执行 `git fetch origin`，以维护目标分支或指定版本确定来源基线，并检查相关未提交差异。脚本读取实际工作树；使用检出已确认基线的源工作树并显式传入 `--prod-dir`，不能仅凭工作树干净就认为它已包含最新上游变更。
2. **判断规则归属**：共享通用规则先改上游 Skill；服务端专用协议改对应 Agent 提示词；本地宿主、编排和运行契约改本地职责文件。通用业务规则跨端适用时联动维护，不把同一完整定义复制到多个位置。
3. **先检查，再按范围更新**：使用第 3 节的只读检查识别漂移并确认差异原因；需要同步时才执行 `--sync-specs --check`。同源适配文件按第 2.1 节人工核对；新增能力不在白名单内时先判断是否应纳入，再修改清单和必要映射。
4. **验证受影响内容**：共享镜像执行正文检查；适配文件核对业务语义和工具契约；执行结构与引用检查，并根据实际行为变更运行对应回归。保持 170 工具门禁和原有业务执行规则，不因整理或同步顺带调整。
5. **交付**：在当次维护报告中说明源版本、同步文件、人工适配文件、刻意保留的差异和验证结果；检查报告只读成功不等于完成新能力同步。文档和维护入口留在维护侧，提交及推送按用户明确指令执行。
