# 角色与权限体系完整平台规格 (spec-roles-permissions)

本文档是 HAP（明道云）平台关于 **角色创建 (create_role)**、**角色更新 (update_role)**、**精细权限分配 (permissionScope: 0)**、**视图数据权限 (recordPermissionInViews)**、**字段级权限 (fieldPermissions)** 与 **操作矩阵** 的唯一权威规范，1:1 对齐官方生产级设计标准。

---

## 目录

1. [权限推理与 permissionScope 强制约束](#一-权限推理与-permissionscope-强制约束)
2. [工作表精细权限 (worksheetPermissions)](#二-工作表精细权限-worksheetpermissions)
3. [视图数据权限（recordPermissionInViews，必传且极端重要）](#三-视图数据权限recordpermissioninviews必传且极端重要)
4. [工作表与行记录操作权限 (Actions)](#四-工作表与行记录操作权限-actions)
5. [级联权限（页面与 AI 助手权限）](#五-级联权限页面与-ai-助手权限)
6. [权限推理原则与角色惯例参考](#六-权限推理原则与角色惯例参考)
7. [Modify 新增对象的默认权限与同步规则](#七-modify-新增对象的默认权限与同步规则)

---

## 一、 权限推理与 permissionScope 强制约束

> [!CAUTION]
> **所有角色必须使用 `permissionScope: 0`（精细权限分配）。** 禁止使用 80/60/30/20 等全局快捷值。精细权限能产出更专业、更安全的角色配置，必须为每个角色配置完整的 `worksheetPermissions` 和 `pagePermissions`。

---

## 二、 工作表精细权限 (worksheetPermissions)

为应用中涉及到的工作表配置以下权限：

### 1. recordDataScope（记录数据范围）
- **`read`**：`0`=无权查看，`20`=只看自己，`100`=查看全部；
- **`edit`**：`0`=无权编辑，`20`=只编辑自己，`100`=编辑全部；
- **`delete`**：`0`=无权删除，`20`=只删除自己，`100`=删除全部。

---

## 三、 视图数据权限（recordPermissionInViews，必传且极端重要）

> [!CAUTION]
> **`recordPermissionInViews` 是角色可访问的视图权限。如果不传此参数或传空数组，角色将无法在应用界面中看到该表的任何记录，等于完全没有工作表的数据权限！**
> 必须从 `worksheetContext` 提取相应视图的 `viewId` 传入并开启权限。如果业务要求该角色能访问所有视图，则必须把该表**所有的 `viewId`** 都一一传进来。

---

## 四、 工作表与行记录操作权限 (Actions)

### 1. worksheetActions（工作表级操作）
- `shareView`：是否可分享视图（通常仅管理角色开启）；
- `import`：是否可导入数据；
- `export`：是否可导出数据（财务、管理类角色开启）；
- `discuss`：是否可发起讨论（默认 true）；
- `batchOperation`：是否可批量操作（管理类角色开启）。

### 2. recordActions（行记录级操作）
- `add`：是否可新增记录；
- `share`：是否可分享记录（默认 false）；
- `discuss`：是否可讨论记录（默认 true）；
- `systemPrint`：是否可打印（单据类业务开启）；
- `attachmentDownload`：是否可下载附件（默认 true）；
- `log`：是否可查看操作日志（管理类角色开启）。

### 3. paymentActions
- `pay`：是否有支付权限（默认 false）。

### 4. 动作与打印模板黑名单限制 (unableCustomButtons / unablePrintTemplates)
- **`unableCustomButtons`**：`string[]`，禁用的自定义动作/按钮 ID 列表。默认 `[]`（全量动作可用）；需要对该角色禁用某些高危/敏感动作（如终审、核销）时填入对应 `actionId`；
- **`unablePrintTemplates`**：`string[]`，禁用的打印模板 ID 列表。默认 `[]`（全量模板可用）；需要对该角色禁用某些敏感单据模板（如薪资单、核心协议）时填入对应 `templateId`。

---

## 五、 级联权限（页面与 AI 助手权限）

- **`fieldPermissions`**：字段级权限。在需要隐藏或保护某几个字段时传入（例如只读 `edit: false`、隐藏 `read: false`），字段 ID 从 `worksheetContext` 中读取；
- **`pagePermissions`**：自定义页面权限。从 `customPageContext` 按名称反查 `pageId`，开启 `enable: true`；
- **`chatbotPermissions`**：AI 助手权限。从 `chatbotContext` 按名称反查 `id`，开启 `enable: true`。

---

## 六、 权限推理原则与角色惯例参考

1. **基于描述深度推演**：根据角色 `description` 语义分配详细权限。若描述仅为"查阅/汇总"，绝不能给 `edit` 或 `delete` 权限；
2. **默认职能惯例参考**：
   - **未体现为可见范围的工作表**：`read: 0, edit: 0, delete: 0`，且 `add: false`；
   - **普通业务角色（销售、内勤）**：通常只对自己负责的数据有写权限（`read: 100, edit: 20, delete: 20`）；
   - **管理类角色（主管、总监）**：通常具有所有数据的写权限（`read: 100, edit: 100, delete: 20/100`）；
   - **只读巡查角色（老板、审计）**：全局或指定表的只读（`read: 100, edit: 0, delete: 0`）。

---

## 七、 Modify 新增对象的默认权限与同步规则

新增对象时必须先读取所有相关角色的实时详情，再按以下默认模型编译连带操作。不得把“对象创建成功”直接等同于“目标角色已经可用”。

| 新增对象 | 默认权限状态 | 必要同步 |
|---|---|---|
| **工作表 (`worksheet`)** | 不会自动对普通角色开放完整数据与视图权限 | 回读真实 `worksheetId` 及各 `viewId`，为目标角色在 `worksheetPermissions` 中配置行级数据范围（`recordDataScope`）、视图权限（`recordPermissionInViews`）与操作权限；必须保留角色已有其他表的配置 |
| **自定义页面 (`page`)** | 不会自动对非管理员角色可见 | 回读真实 `pageId` 后，在目标角色的 `pagePermissions` 中追加 `{ id: pageId, enable: true }`，保留已有页面列表 |
| **对话机器人 (`chatbot`)** | 不会自动对普通角色开放 | 回读真实 `chatbot_id` 后，在目标角色的 `chatbotPermissions` 中追加 `{ id: chatbotId, enable: true }`，保留已有助手列表 |
| **视图 (`view`)** | 不会自动进入现有角色的 `recordPermissionInViews` | 取得真实 `viewId` 后，只向需要使用该视图的角色追加，并保留角色已有视图列表 |
| 字段 | 对已经拥有工作表访问权的角色默认可用 | 普通字段无需逐角色添加；敏感字段必须在创建后对不应访问的角色增加 `fieldPermissions`（设为 `read: false` / `edit: false`） |
| 自定义动作 | 挂载到视图后，默认对拥有该视图及记录权限的所有角色可用 | 普通动作挂载后即对视图内全员可用；敏感/高危操作在目标角色的 `unableCustomButtons` 中填入其 ID 进行禁用 |
| 打印模板 | 创建后默认随工作表打印权限（`systemPrint`）对已有角色可用 | 普通模板无需修改角色；敏感模板在目标角色的 `unablePrintTemplates` 中填入其 ID 进行禁用，或通过模板自身限制下载权限（`downloadPermission: "managers"`）与绑定指定视图（`specificViews`）收缩可用范围 |

> [!CAUTION]
> **`update_role` 是全量覆盖更新**：未传入的已有权限项会被全部清除。因此更新角色前**必须先调用 `get_role_details` 获取完整配置，在已有 `worksheetPermissions`、`pagePermissions`、`chatbotPermissions` 数组上增量追加新对象后整体写回**，绝对禁止只传单一新增对象。

### 7.1 字段、普通动作与普通模板采用“默认开放、敏感收紧”

1. **普通业务资产**：新增普通字段、常规动作（已挂载到视图）及常规打印模板，默认沿用工作表及视图现有权限，**无需为每个角色重复制造覆盖配置**；
2. **敏感资产收紧**：
   - **敏感字段**：在目标角色的 `fieldPermissions` 中将无权角色设为 `read: false` 或 `edit: false`；
   - **高危/敏感动作**：在目标角色的 `unableCustomButtons: [ "actionId" ]` 中填入禁用的动作 ID 列表；
   - **敏感打印模板**：在目标角色的 `unablePrintTemplates: [ "templateId" ]` 中填入禁用的模板 ID 列表，或通过模板自身配置限制下载（`downloadPermission: "managers"`）与绑定指定视图（`specificViews`）。

### 7.2 工作表、页面、机器人与新视图采用“默认无、显式授权”

1. **工作表**：新增表后，必须为各目标角色显式赋予 `worksheetPermissions` 并绑定 `recordPermissionInViews`；
2. **自定义页面与 AI 助手**：新增页面或机器人后，必须在目标角色的 `pagePermissions` / `chatbotPermissions` 中开启 `enable: true`；
3. **新视图**：新增视图后，只向明确需要使用该视图的角色追加 `viewId`。

权限写接口及参数以当前运行时 MCP 定义为准。当前环境缺少现有角色权限更新接口时，必须保留必要性结论并转为结构化人工待办，不得把未执行的权限调整标记为完成。
