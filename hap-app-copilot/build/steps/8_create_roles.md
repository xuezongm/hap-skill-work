# Step 8: 创建角色与权限 SOP (8_create_roles)

本文档是 Build 阶段 **Step 8（按角色并发创建业务角色与权限）** 的专属作业指导书。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [单角色执行 SOP 流水线](#三-单角色执行-sop-流水线)
4. [输出交付物契约 (.build)](#四-输出交付物契约-build)
5. [⛔ 验证断言与错误自愈](#五-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：子代理按角色并发；
- **任务目标**：根据 `hap-plan.json` 创建应用的自定义业务角色，配置基础数据查看/编辑范围，并在需要时生成结构化前台微调指引；
- **核心输入契约**：
  - `hap-plan.json`：角色规划（`roles`）；
  - `hap-context.json`：`appId`。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-roles-permissions.md](../../references/spec-roles-permissions.md)（角色权限模型、安全门禁与待办清单）

---

## 三、 单角色执行 SOP 流水线

1. **提取角色规划**：提取当前角色的名称、描述与权限范围；
2. **调用 MCP 创建角色**：调用 `create_role`：
```json
{
  "appId": "<appId>",
  "name": "销售主管",
  "description": "负责本部门销售合同审核与客户跟进数据管理"
}
```
获取返回的 `roleId`。

3. **配置字段级权限 (按需)**：若当前角色需要特殊的字段级只读/隐藏保护，在 `create_role` 的 `worksheetPermissions` 中直接传入 `fieldPermissions`（如 `[{"id": "field_id", "read": true, "edit": false}]`）。

---

## 四、 输出交付物契约 (.build)

执行成功后，将当前角色 ID 与回执写入独立任务回执文件：
- **文件路径**：`.build/receipts/step8-role-{targetRole}.json`
- **内容格式**：
```json
{
  "taskId": "step8-role-{targetRole}",
  "executor": { "kind": "subagent", "agentId": "{agentId}" },
  "step": "8",
  "target": { "type": "role", "name": "{targetRole}" },
  "status": "succeeded",
  "outputs": {
    "roleName": "{targetRole}",
    "roleId": "role_id_1",
    "roleIdByName": { "{targetRole}": "role_id_1" }
  },
  "verification": {
    "passed": true,
    "evidence": ["调用 create_role 成功创建角色并捕获 roleId: role_id_1"]
  },
  "issues": []
}
```

---

## 五、 ⛔ 验证断言与错误自愈

1. **断言 1 (角色创建成功)**：`create_role` 返回成功且捕获合法 `roleId`；
2. **断言 2 (回执通知)**：将包含 `roleId`、`roleName` 的标准回执写入 `.build/receipts/step8-role-{targetRole}.json`；
3. **自愈机制**：若角色名称重复，追加序号或业务后缀重试。
