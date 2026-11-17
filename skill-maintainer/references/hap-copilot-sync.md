# 与 AgentService 的同步说明

本文说明当前同步脚本的实际行为，供 Skill 维护者使用。实现位于本维护 Skill 的 [同步脚本](../scripts/sync_hap_copilot.py)；同步清单和映射以该脚本为准。

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

`hap-domain-print-template-spec` 不在镜像清单内；Copilot 使用 `modify/steps/print_template.md` 承接本地文件制作。AgentService 的打印规范和提示词保持原样。

`--sync-specs` 只写这些规格文件。它不会改写目标 Skill 的入口、工作流、Build SOP、Modify 手册、安全规则、影响地图、Audit 指标或运行脚本。

## 3. 执行方式

要求 Python 3，且能够访问本地源目录和目标目录。以下变量应设为当前机器上真实的绝对路径；示例对应现有工作区布局：

```bash
HAP_SKILLS_ROOT='/Users/user/AI-work/应用搭建skill/skills'
HAP_PROD_DIR='/Users/user/AI-work/Mingo/MDAgentService/assets/agents/prod'
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

2026-11-17 角色、记录数据和外部门户三份共享规格中的服务端专用协议归入对应 Agent 的 `prompt.system`。共享规格继续定义通用业务约束；目标提示词已有的协议直接复用，不复制第二份完整定义。下表的上游路径相对于 `assets/agents/prod`。

| 共享规格 | 服务端专用协议及权威提示词 | 共享规格保留内容 / 本地核对点 |
|---|---|---|
| `hap-domain-role-spec` | `modify-app/role-permission-revision-sub-agent.yaml`：任务目标包装、可信用户变量与服务实现说明；`build-app/roles-build-sub-agent.yaml` 已有 viewContext 映射，直接复用 | 真实 ID、可信操作者、权限覆盖与保留、成员粒度和恢复保护保留；本地角色搭建 SOP 与修改手册使用本地上下文或实时查询 |
| `hap-domain-record-data-spec` | `modify-app/record-data-revision-sub-agent.yaml`：停止条件对应的状态回执、示例生成策略、createdIds；`modify-app/app-revision-agent.yaml` 已有入口边界、跨批次解析与依赖阻断，直接复用 | 授权、数量阈值、冻结、防重、对账、停止条件及两阶段结转保留；本地按真实 rowIds 执行，不构造服务端任务包装 |
| `hap-domain-external-portal-spec` | `modify-app/external-portal-revision-sub-agent.yaml` 与 `modify-app/app-revision-agent.yaml` 已有组织身份注入及附件交接协议，直接复用 | 当前组织、可信素材来源、素材优先级与权限边界保留；本地使用已核实组织 ID 和当前环境的附件读取能力 |

这三份规格继续随 19 项白名单同步，不自动转换 YAML。共享规则后续仍先改上游 Skill，再同步公开镜像；仅服务端协议变化时改对应提示词。涉及本地也需要的新能力时另行评估本地流程，不能把专用协议重新塞回共享规格。当前同步检查不会发现迁移后提示词的遗漏，维护者须核对实际加载的提示词与关键流程回归。

本次不改两份设计指南、公共安全规则、授权与数据阈值、公开 Skill 的 170 工具门禁及原有执行流程。同步说明和迁移记录继续仅保留在维护侧，不加入公开包或其 README。

## 7. Copilot 打印本地 step 的维护

打印是本地适配项，不再同步完整的服务端 Skill。`modify/steps/print_template.md` 按读取原件、制作副本、校验、原生 MCP 上传组织，只保留 HAP 占位符、文件兼容和交付要求；通用排版教程、沙箱协议和内部辅助模块不进入公开包。

- 上游业务依据为 `skills/hap-domain-print-template-spec/SKILL.md`；执行来源为 `modify-app/print-template-revision-sub-agent.yaml`，均相对于 AgentService 的 `assets/agents/prod`。本次不改这两个上游文件。
- 本地 `modify/modify_guide.md` 的打印操作卡负责纯配置与删除，文件新建或替换才读取 step；`scripts/resolve_context.py` 返回按需 step 引用，不把文件制作正文注入纯配置任务。
- `--sync-specs` 仅覆盖 19 份镜像，既不重新生成旧打印镜像，也不覆盖 step。`--check` 检查 step 及其来源标记和上游文件存在；旧 `references/hap-domain-print-template-spec.md` 若残留，会作为白名单外文件报告。该旧文件在本次调整中移除，不扩大旧版清理开关的删除范围。
- step 是面向本地的人工适配，当前工具不自动提炼上游业务规则，也不检测语义变化。上游占位符、兼容、权限或验收规则调整时，维护者对照变更更新 step；仅沙箱协议变化时不复制到本地。安全规则仍在本地公共文件维护，不在 step 复制授权策略或改变 170 工具门禁。
- [维护回归测试](../tests/test_print_step.py)覆盖：旧镜像不会被同步重新引入、step 不被覆盖、step 或来源缺失能报告、打印与模板别名均能加载 step，纯配置渲染不携带制作全文。同步工具、说明和验证脚本继续仅在维护侧。
