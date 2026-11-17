# Step 8: 单角色创建与精细权限推演 SOP (`8_create_roles`)

<!-- SOURCE: build-app/roles-build-sub-agent.yaml -->

## 一、 本地宿主输入与参考映射

- **执行方式**：独立 Subagent 按单个角色并发执行。
- **输入切片**：读取 `.build/task-context/{taskId}.json`：
  - `planSlice`：`role`（含 `name`、`description`、`roleScope`: `"general" | "externalPortal"`、`permissions` 紧凑数组、`requirements`）、`appLanguage`；
  - `contextSlice`：`appId`、`worksheetIdByName`、`viewsByWorksheet`（或 `viewIdByName`）、`actionsByWorksheet`、`customPageIdByName`、`chatbotIdByName`。
- **必读领域规范**：`references/hap-domain-role-spec.md`、`references/hap-app-design-guide.md`（「角色权限」章节）
- **准许工具白名单**：`["create_role", "get_role_list"]`

---

## 二、 核心构建规则与执行步骤

- **输出语言与补充要求**：角色描述文案使用 `appLanguage` 指定语言；优先落实 `role.requirements` 中的权限细节。

### 1. 系统预设角色前置拦截（同名即复用，禁重复新建）
- 若 `role.name` 与系统预设角色名称（如「管理员」「运营者」「开发者」）**完全一致**：**严禁调用 `create_role`**！直接调用 1 次 `get_role_list(appId)` 查找对应同名预设角色的真实 `id`，组装回执输出结束。

### 2. 精细权限生成策略（固定 `permissionScope: "0"`）
1. **工作表权限 (`worksheetPermissions`)**：
   - 仅对 `role.permissions` 中声明的 `"表名(worksheet)"` 反查真实 `worksheetId`（查不到则跳过，不生成全零占位对象）；
   - 按角色职责推演 `recordDataScope` 档位：
     - **只读/查阅/审计/高管看板**：`read: 100, edit: 0, delete: 0`，`add: false`；
     - **一线普通操作角色**：通常 `read: 100`（或本人 `20`），`edit: 20, delete: 20`，按职责定 `add`；
     - **部门/团队主管角色**：可用 `30`（本人及下属），删除从严（`20` 或 `0`）；
     - **业务模块管理角色**：`read: 100, edit: 100`，`delete` 仅明确需要时设 `100` 否则 `20/0`；
   - 补齐必填子对象：`worksheetActions` / `recordActions`（普通角色默认关闭公开分享、导入、导出、批量操作、系统日志；`discuss: true`、`attachmentDownload: true`）、`paymentActions: { pay: false }`、`fieldPermissions: []`（Build 阶段固定传空数组，不编造字段 ID）；
   - **`recordPermissionInViews`（必传非空）**：提取该表全部真实视图 ID，生成 `{ viewId, read, edit, delete }`（视图读写删布尔值不得超过 `recordDataScope` 上限；找不到真实视图时跳过该表，严禁传空数组或假 `viewId`）。
2. **自定义页面与 AI 助手权限**：
   - `"页面名(customPage)"` → 反查真实 `pageId` 生成 `{ id: pageId, enable: true }` 放入 `pagePermissions`；
   - `"助手名(aiAssistant)"` → 反查真实 `chatbotId` 生成 `{ id: chatbotId, enable: true }` 放入 `chatbotPermissions`。

### 3. 调用 `create_role` 与重名幂等自愈
1. 调用 1 次 `create_role`：传 `appId`、`name`、`description`、`roleScope: role.roleScope || "general"`、`permissionScope: "0"`、`hideAppForMembers: "false"` 及三类权限数组（**严禁传入已废弃的旧参数 `type: "0"`**；三类权限至少一类非空）。
2. **重名错误幂等救治**：若 `create_role` 返回角色名称重复/已存在错误，立即调用 `get_role_list(appId)` 提取同名已有角色的真实 `id` 视同成功输出，**严禁改名重试或二次调用 `create_role`**。

---

## 三、 本地回执落盘契约

执行完成后，写入 `receiptPath`（`.build/receipts/step8-role-{name}.json`）：

```json
{
  "taskId": "<来自 taskContext.taskId>",
  "runId": "<runId>",
  "executor": { "kind": "subagent", "agentId": "<agentId>" },
  "step": "8",
  "target": { "type": "role", "id": "<roleId>", "name": "<roleName>" },
  "status": "succeeded",
  "outputs": {
    "roleName": "<roleName>",
    "roleId": "<24位真实roleId>",
    "roleScope": "<general或externalPortal>",
    "roleIdByName": { "<roleName>": "<24位真实roleId>" }
  },
  "verification": {
    "passed": true,
    "evidence": ["已完成角色精细权限矩阵构建并获取真实 roleId"]
  },
  "issues": []
}
```
