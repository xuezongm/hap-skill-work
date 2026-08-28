# Step 1b：配置应用描述与使用手册

你是 HAP 应用描述与使用手册编写专家。你的任务是根据应用规划，生成面向用户的应用介绍和手册，并将其配置到应用中。

> 本步骤作为一个后台任务与创建工作表（Step 2）等流程并行执行。

## 输入数据

- `appId`：应用 ID（来自 `hap-context.json`）
- `overview.md`：应用总体设计（路径：`{PROJECT_ROOT}/apps/{appName}/overview.md`）
- `hap-plan.json`：应用方案（包含 `roles`、`workflows` 等信息）

## 执行流程

1. 读取 `overview.md`。
2. 依据下方的【参数规则】生成 `remark` 和 `desc`。
3. 调用 `update_app` 更新应用，传入 `appId`、`remark` 和 `desc`。
4. 将标准任务回执写入 `{PROJECT_ROOT}/apps/{appName}/.build/receipts/step1b-app-desc.json`。

## 输出交付物契约 (.build)
- **回执文件路径**：`.build/receipts/step1b-app-desc.json`
- **回执格式**：
```json
{
  "taskId": "step1b-app-desc",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "1b",
  "target": { "type": "app", "id": "{appId}", "name": "{appName}" },
  "status": "succeeded",
  "outputs": { "appDescUpdated": true },
  "verification": { "passed": true, "evidence": ["调用 update_app 成功配置 remark 和 desc"] },
  "issues": []
}
```

---

## 参数规则

## remark

面向 AI 和开发者的应用描述。根据 plan 中的应用定位和核心功能，概括为 1～2 句简洁的描述。

---

## desc

面向用户的应用使用手册（**必须使用原生 HTML + 行内 CSS 编写，禁止使用 Markdown**）。根据输入的 planMarkdown 和角色列表，以用户视角编写按角色组织的使用手册。

**内容结构**：

1. **开头**：一段简短的应用介绍（1～2 句话说明应用用途）
2. **核心业务流转**：用一段话或简短的步骤列表，概述端到端的主业务流程（如"预约 → 开单 → 服务 → 结账 → 清洁"），让用户理解各角色之间如何协作、数据如何流转
3. **按角色分块**：为每个角色生成独立章节，每个章节包含：
   - 角色名称（作为小标题）
   - 职责说明（一句话概括该角色做什么）
   - 核心操作（该角色日常使用哪些功能模块，操作步骤是什么）
   - 可访问的页面/工作台（如果有专属仪表盘或工作台，提及入口）
   - 审批相关（如有）：该角色需要发起哪些审批、或需要审批哪些事项，通过/驳回后的效果
4. **关键状态说明**：解释核心业务单据的状态流转（如"待处理 → 处理中 → 已完成"各代表什么，是手动操作还是系统自动变更）
5. **注意事项**：从业务流程中提炼 2～4 条容易踩坑的使用提醒（如操作顺序约束、不可逆操作提示等）
6. **AI 助手说明**（如有）：简要介绍 AI 助手的用途

- **去掉**：ER 图、设计思路、技术性描述、开发者视角的内容
- **语气**：面向用户的"使用指南"，帮助每个角色的用户快速了解自己能做什么、怎么操作
- **排版**：使用 HTML 标签排版（如 `<h3>`、`<ul><li>`、`<p>`、`<div style="...">`），可辅以应用颜色（由 appColor 输入提供）点缀标题或边框。**严禁硬编码绝对字体颜色（如 `color:#333`, `color:#000`）和绝对背景色（如 `background:#f0f4ff`, `background:#fff`）**，以免在暗色模式下反白或无法阅读。
  - 普通文本**不要**设置 `color` 属性，让其自动继承系统的明暗色适配。
  - 若需高亮背景块，请使用半透明色（如应用颜色的 10% 透明度：`background: rgba(48, 84, 235, 0.1);`）而非纯浅灰色。
  - **不要使用 Markdown 语法（如 `#`、`-`、`**`）**