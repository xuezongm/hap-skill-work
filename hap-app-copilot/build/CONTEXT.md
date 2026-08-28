# hap-context.json 结构定义

本文件定义 `{PROJECT_ROOT}/apps/{appName}/hap-context.json` 的完整结构。所有步骤读写 context 时必须遵守此 schema。

## 结构

```json
{
  "appId": "string",
  "appName": "string",
  "org_id": "string",
  "progress": "string (见 PROGRESS.md)",

  "sectionIdByName": {
    "分组名称": "sectionId"
  },
  "worksheetIdByName": {
    "工作表名称": "worksheetId"
  },
  "actionIdByName": {
    "动作名称": "actionId"
  },
  "viewIdByName": {
    "工作表名称-视图名称": "viewId"
  },
  "customPageIdByName": {
    "页面名称": "pageId"
  },
  "chatbotIdByName": {
    "助手名称": "chatbotId"
  },
  "roleIdByName": {
    "角色名称": "roleId"
  },
  "appDescUpdated": true,
  "sampleDataCreated": true,
  "buildRun": {
    "runId": "string",
    "executionMode": "subagent_required",
    "lastPhaseReport": ".build/phase-report.json",
    "blocked": false
  },
  "customActionWorkflows": [
    {
      "actionName": "string",
      "processId": "string",
      "published": true
    }
  ]
}
```

## 异步任务持久化回执与幂等规则

- **`appDescUpdated: true`**：Step 1b（描述与手册更新）完成回执。断点恢复时若为 `true` 则跳过 Step 1b。
- **`sampleDataCreated: true`**：Step 5（示例数据写入）完成回执。断点恢复时若为 `true` 则跳过 Step 5，**严禁重复写入导致数据翻倍**。
- **`workflows[i].processId`（记录在 `hap-plan.json`）**：Step 10 完成回执。断点恢复时若某系统工作流已有 `processId`，则跳过创建直接校验/发布。
- **`customActionWorkflows[i].published: true`**：Step 11 完成回执。断点恢复时若已发布则跳过。

## 写入规则

- **由确定性脚本独占写入**：所有 ID 映射和 `progress` 只能由 `build_runtime.py advance` 在阶段报告放行后原子写入，主调度器与 Subagent 严禁直接手工修改
- **只存 ID 映射**，不存 MCP 原始返回的完整对象
- 字段结构（fields）存储在独立文件 `worksheetContext.json`，不写入 `hap-context.json`，避免上下文膨胀

## worksheetContext.json 使用契约

`worksheetContext.json` 由阶段 2（Step 3 收集与 `merge_worksheet_context`）原子生成写入，**Step 4~11 只读**。

- Step 4~11 中需要的字段 ID、选项 key 等，**必须且只能从 `worksheetContext.json` 查找，严禁重复调用 `get_worksheet_structure`**
- 视图 ID 从 `viewIdByName`（存储在 `hap-context.json`）中获取
- 该文件在阶段 2 写入后**不再修改**
