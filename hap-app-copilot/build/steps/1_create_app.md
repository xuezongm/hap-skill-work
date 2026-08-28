# Step 1: 创建应用与导航分组 SOP (1_create_app)

本文档是 Build 阶段 **Step 1（创建应用外壳、导航分组与自定义页面空壳）** 的专属作业指导书。由主调度器极速内联执行，为后续全量并发搭建奠定全局物理实体基础。

---

## 目录

1. [执行定位与输入契约](#一-执行定位与输入契约)
2. [引用的平台规格 (SSOT)](#二-引用的平台规格-ssot)
3. [参数规则与选型规范](#三-参数规则与选型规范)
4. [执行 SOP 流水线](#四-执行-sop-流水线)
5. [写入应用访问链接](#五-写入应用访问链接)
6. [输出交付物契约](#六-输出交付物契约)
7. [⛔ 验证断言与错误自愈](#七-⛔-验证断言与错误自愈)

---

## 一、 执行定位与输入契约

- **执行方式**：主调度器内联 1 步极速执行；
- **任务目标**：根据 `hap-plan.json` 创建应用实体外壳、所有导航分组（Section）以及自定义页面空壳，并写入应用访问链接；
- **核心输入契约**：
  - `org_id`：组织 ID（来自 `hap-plan.json` 或 `hap-context.json`）；
  - `appName`：应用名称；
  - `appIcon`：应用图标；
  - `appColor`：应用主题配色；
  - `navLayout`（可选）：导航布局形态；
  - `navColor`（可选）：导航栏背景配色；
  - `enableExternalPortal`（可选）：是否启用外部门户；
  - `navGroups`（或 `sections`）：导航分组列表；
  - `customPages`：自定义页面规划列表。

> 💡 **说明**：本步骤无需处理 `remark` 和 `desc`。应用的详细描述和使用手册会作为独立的后台任务（Step 1b）并发配置。创建应用时无需传这两个参数（或传空）。

---

## 二、 引用的平台规格 (SSOT)

> [!IMPORTANT]
> **Primary Reference (平台规格 SSOT)**：
> 📖 [references/spec-app-styles.md](../../references/spec-app-styles.md)（官方受控图标库、9种主题色盘、navLayout布局与navColor配色）

---

## 三、 参数规则与选型规范

- **`icon` / `iconColor`**：必须遵循 `spec-app-styles.md`，使用官方 9 色板 Hex 与受控图标；
- **`navLayout` / `navColor`**：按 `spec-app-styles.md §2, §3` 选型（常规推荐 `group` + `appColor`）；
- **`enableExternalPortal` (外部门户)**：若 `hap-plan.json` 中规划了外部门户角色（`roleScope: "externalPortal"`），创建应用时 `enableExternalPortal` 必须传 `true`。

---

## 四、 执行 SOP 流水线

1. **创建应用外壳实体**：
   调用 `create_app`：
   ```json
   {
     "projectId": "<org_id>",
     "name": "<appName>",
     "icon": "<appIcon>",
     "iconColor": "<appColor>",
     "navColor": "<navColor, 默认 appColor>",
     "navLayout": "<navLayout, 默认 group>",
     "enableExternalPortal": <true/false>
   }
   ```
   获取返回的 `appId`。

2. **批量创建导航分组 (Sections)**：
   若 Plan 中规划了导航分组，调用 `create_app_sections`：
   ```json
   {
     "appId": "<appId>",
     "sections": [ ...navGroups 或 sections 数组... ]
   }
   ```
   获取各分组的 `sectionId` 并建立名称映射字典 `sectionIdByName`。

3. **批量创建自定义页面空壳 (Custom Pages)**：
   遍历 `customPages` 规划列表，对每个页面调用 `create_app_items` 创建空白页面项：
   - `type`: `1` (自定义页面)
   - `name`: 页面名称
   - `icon`: 依据页面类型规范设定：
     - **仪表盘/数据看板 (`dashboard`)**：固定传 `"sys_control-panel_traffic"`
     - **业务工作台 (`workspace`)**：固定传 `"2_3_statistics"`
   - `sectionId`: 从刚刚建立的 `sectionIdByName` 中查找所在导航分组 ID
   - `remark`: 阐明该页面的业务定位与核心价值
   - 记录 `"页面名称" → pageId` 的映射到字典 `customPageIdByName` 中。

4. **写入应用访问链接**：
   执行下方【五、写入应用访问链接】规范，将直达 URL 写入 `overview.md` 首行。

5. **落盘更新 `hap-context.json`**：
   将 `appId`、`sectionIdByName`、`customPageIdByName` 写入 `hap-context.json`，并写入 `progress="app_created"`。

---

## 五、 写入应用访问链接

根据当前使用的 MCP 服务地址，确定前端访问域名：

| MCP 服务地址 | 前端域名 |
|:---|:---|
| `api.mingdao.com/mcp` | `www.mingdao.com` |
| `api2.mingdao.com/mcp` | `meihua.mingdao.com` |
| `api3.mingdao.com/mcp` | `sandbox.mingdao.com` |

拼接应用访问链接：`https://{前端域名}/app/{appId}`，并在 `{PROJECT_ROOT}/apps/{appName}/overview.md` 文件的最顶端（第 1 行）追加写入链接卡片：

```markdown
> [!TIP]
> **🎉 应用已物理创建成功！**
> **访问链接**：[点击此处立即进入系统 ➔](https://{前端域名}/app/{appId})

---
```

---

## 六、 输出交付物契约

主调度器直接将物理 ID 映射写入 `{PROJECT_ROOT}/apps/{appName}/hap-context.json`：
```json
{
  "appName": "<appName>",
  "appId": "app_xxxxxx",
  "org_id": "<org_id>",
  "progress": "app_created",
  "sectionIdByName": {
    "业务大厅": "sec_1",
    "系统配置": "sec_2"
  },
  "customPageIdByName": {
    "运营大盘": "page_1"
  }
}
```

---

## 七、 ⛔ 验证断言与错误自愈

1. **断言 1 (应用存在)**：`appId` 必须非空且有效；
2. **断言 2 (分组完整)**：返回的 `sectionIdByName` 数量必须等于 Plan 中的 `navGroups` 数量；
3. **断言 3 (页面完整)**：`customPageIdByName` 数量必须等于 Plan 中的 `customPages` 数量；
4. **自愈机制**：若某分组或页面创建失败，立即针对性重试调用 `create_app_sections` 或 `create_app_items` 补齐；
5. **推进阶段**：写入 `progress="app_created"` 后，立即进入 Phase 1.5（并发派发 Step 1b 与 Step 2a Subagents）。
