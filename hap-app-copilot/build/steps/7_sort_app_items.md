# Step 7: 应用项导航智能排序 SOP (7_sort_app_items)

本文档是 Build 阶段 **Step 7（对应用导航分组内的应用项进行业务语义智能排序）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [业务排序法则 (6 大层级动线)](#二-业务排序法则-6-大层级动线)
3. [执行 SOP 流水线](#三-执行-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与错误自愈](#五-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：单原子 Subagent 独立执行（任务 ID: `step7-sort-items`）；
- **任务目标**：结合业务语义、角色使用习惯与产品设计规范，对每个导航分组下的所有应用项（自定义页面/仪表盘、工作台、工作表、AI 助手）进行智能排序，彻底消除多路并发建表和异步创建导致的分组内导航乱序；
- **核心输入契约**：
  - `appId`：应用 ID；
  - `groupNames` / `sections`：导航分组名称数组；
  - `sectionIdByName`：分组名称 → sectionId 映射字典（来自 `hap-context.json`）；
  - `worksheetIdByName`：已建工作表 ID 映射字典；
  - `customPageIdByName`：已建自定义页面 ID 映射字典；
  - `chatbotIdByName`：已建 AI 助手 ID 映射字典；
  - `hap-plan.json`：规划中的工作表、页面与 AI 助手分组归属。
- **准许调用工具清单 (Tool Whitelist)**：`["sort_app_items"]`

---

## 二、 业务排序法则 (6 大层级动线)

将每个分组下的全部项（自定义页面、工作台、工作表、AI 助手）汇总，按以下业务动线标准排列：

```text
┌────────────────────────────────────────────────────────┐
│ ① 门户/工作台/全局总览 (置顶)                           │
│   仪表盘 (Dashboard) 或工作台 (Workspace) 优先排在最前   │
│   (如「销售总览」、「健康管理工作台」)                   │
├────────────────────────────────────────────────────────┤
│ ② 核心业务单据与主实体                                  │
│   高频业务主表 (如「客户」、「合同」、「用药计划」)      │
├────────────────────────────────────────────────────────┤
│ ③ 关联从属表与业务明细                                  │
│   从属明细表紧随其主单据之后 (如「服药打卡记录」紧随计划) │
├────────────────────────────────────────────────────────┤
│ ④ 台账与流水日志                                       │
│   快照台账与追踪流水 (如「体征监测记录」、「出入库流水」) │
├────────────────────────────────────────────────────────┤
│ ⑤ 基础字典与分类配置 (沉底)                             │
│   低频基础配置与字典表 (如「家庭成员」、「药品分类」)   │
├────────────────────────────────────────────────────────┤
│ ⑥ AI 智能助手                                          │
│   常驻辅助问答工具，通常排在分组末尾                    │
└────────────────────────────────────────────────────────┘
```

---

## 三、 执行 SOP 流水线

### 1. 建立名称到真实物理 ID 的全局映射字典 (`nameToId`)
- 从 `worksheetIdByName` 提取：`wsName -> worksheetId`；
- 从 `customPageIdByName` 提取：`pageName -> pageId`；
- 从 `chatbotIdByName` 提取：`botName -> chatbotId`。

### 2. 按分组逐一计算排序列表
遍历应用中的每个导航分组：
1. 获取该分组的 `sectionId`（若查不到则跳过）；
2. 筛选出属于该分组的全部应用项（来自 `hap-plan.json` 中的 `groupName` 或 `section` 字段）；
3. 按照上述 **6 大层级动线法则** 对项名称进行智能排序；
4. 将排好序的名称通过 `nameToId` 转换为真实物理 ID 数组 `itemIds`（过滤未找到真 ID 的项）。

### 3. 调用 MCP 工具执行物理排序
- **若 `itemIds` 包含 2 个及以上 ID**：调用 `sort_app_items`：
  ```json
  {
    "appId": "<appId>",
    "sectionId": "<sectionId>",
    "itemIds": [
      "<page_id_dashboard>",
      "<worksheet_id_main>",
      "<worksheet_id_detail>",
      "<chatbot_id>"
    ]
  }
  ```
- 若某分组内只有 1 个或 0 个项，无需调用。

### 4. 写入任务回执
将执行结果写入回执文件：
- **文件路径**：`.build/receipts/step7-sort-items.json`

---

## 四、 输出交付物契约 (.build)

```json
{
  "taskId": "step7-sort-items",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "7",
  "target": { "type": "app_navigation", "name": "全局应用项排序" },
  "status": "succeeded",
  "outputs": {
    "sectionsSorted": 3,
    "appItemsSorted": true
  },
  "verification": {
    "passed": true,
    "evidence": ["成功调用 sort_app_items 对各导航分组内的页面、工作表与 AI 助手完成业务动线排序"]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与错误自愈

1. **断言 1 (真实 ID 校验)**：`itemIds` 传入的所有 ID 必须在 `nameToId` 中真实存在，严禁编造；
2. **断言 2 (回执落盘)**：标准回执成功写入 `.build/receipts/step7-sort-items.json`；
3. **自愈机制**：若某项未找到真 ID，跳过该项继续排序其余项；若接口报错重试最多 2 次。
