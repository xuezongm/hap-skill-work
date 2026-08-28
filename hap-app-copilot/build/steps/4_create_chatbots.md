# Step 4: 创建 AI 智能助手 SOP (4_create_chatbots)

本文档是 Build 阶段 **Step 4（创建应用专属 AI 助手与知识库关联）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [执行 SOP 流水线](#三-执行-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与错误自愈](#五-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：独立子代理；
- **任务目标**：根据 `hap-plan.json` 创建应用的专属 AI 智能问答助手，绑定工作表与知识库，配置场景化欢迎语与快捷提问；
- **核心输入契约**：
  - `hap-plan.json`：AI 助手规划（`chatbot`）；
  - `hap-context.json`：`appId`、已建工作表 ID 映射。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-chatbots.md](../../references/spec-chatbots.md)（AI 助手创建、模型选型与知识库挂载）

---

## 三、 执行 SOP 流水线

1. **读取 Plan 与工作表映射**：提取助手名称、提示词（`systemPrompt`）及需要检索的工作表 ID 列表；
2. **调用 MCP 创建助手**：调用 `create_chatbot`：
```json
{
  "appId": "<appId>",
  "name": "智能问答助手",
  "systemPrompt": "...",
  "worksheets": [ ...工作表ID数组... ],
  "welcomeMessage": "...",
  "shortcuts": [ ...快捷提问数组... ]
}
```
获取返回的 `chatbotId`。

---

## 四、 输出交付物契约 (.build)

执行成功后，将助手 ID 与回执写入独立任务回执文件：
- **文件路径**：`.build/receipts/step4-chatbot.json`
- **内容格式**：
```json
{
  "taskId": "step4-chatbot",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "4",
  "target": { "type": "chatbot", "name": "智能问答助手" },
  "status": "succeeded",
  "outputs": {
    "chatbotId": "bot_id_123",
    "chatbotName": "智能问答助手",
    "chatbotIdByName": { "智能问答助手": "bot_id_123" }
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 create_chatbot 成功创建智能问答助手并捕获 chatbotId: bot_id_123"]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与错误自愈

1. **断言 1 (创建成功)**：`create_chatbot` 返回成功且捕获合法 `chatbotId`；
2. **断言 2 (回执通知)**：将包含 `chatbotIdByName` 的标准回执写入 `.build/receipts/step4-chatbot.json`；
3. **自愈机制**：若创建报错提示工作表 ID 非法，从 `hap-context.json` 重新获取合法工作表 ID。
