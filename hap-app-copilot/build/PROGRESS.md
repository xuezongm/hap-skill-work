# Progress 状态机与原子子任务生命周期 (PROGRESS)

本文档定义 HAP App Builder 的**全局阶段状态机 (Global Stage FSM)** 与 **原子子任务生命周期状态 (Subagent Task States)**。

---

## 一、 全局阶段状态机 (Global Stage FSM)

`hap-context.json` 中的 `progress` 字段记录全局搭建进度。**所有 progress 推进均由确定性脚本 `build_runtime.py advance` 在 `build_runtime.py finalize` 阶段报告放行（`canAdvance: true`）后独占原子写入**。

| 状态值 | 含义 | 前置状态 | 机器门禁检验命令 |
|---|---|---|---|
| _(空/不存在)_ | 初始状态 | — | `build_runtime.py init` |
| `app_created` | 应用、导航分组与页面空壳已创建 | _(空)_ | Step 1 (主调度器极速内联创建) |
| `worksheets_created` | 所有工作表与跨表关联已创建 | `app_created` | Step 2a + Step 2b (`phase1_5`) |
| `fields_refreshed` | 字段结构已刷新，业务规则、视图、自定义动作与 AI 助手已就绪 | `worksheets_created` | Step 3 + Step 4 单表与 AI 助手 (`phase2`) |
| `config_completed` | 示例数据 + 页面组件 + 项排序 + 角色权限 + 工作流设计完成 | `fields_refreshed` | Step 5/6/7/8/9 全局跨表配置 (`phase3`) |
| `completed` | 工作流全部发布且所有异步交付物核验通过 | `config_completed` | Step 10~11 部署 (`phase4` / 空阶段直接放行) |
| `failed` | 达到重试上限或发生不可恢复错误 | _(任意)_ | 任何任务重试耗尽 |
| `blocked` | 宿主不支持或禁用了 subagent 能力 | _(任意)_ | 前置环境检查失败 |

---

## 二、 原子子任务生命周期状态 (Subagent Task States)

在调度循环中，每个 Subagent 任务严格遵循以下 9 种生命周期状态：

| 状态 | 含义 | 下一步转移 | 说明 |
| :--- | :--- | :--- | :--- |
| **`planned`** | 任务已生成，但依赖的前置资源尚未就绪 | ➔ `ready` | 等待前置阶段完成（如 Step 7 等待 ViewId） |
| **`ready`** | 依赖全部满足，等待派发 | ➔ `dispatching` | 放入当前调度轮次的待提交集合 |
| **`dispatching`** | 正在调用 subagent 派发工具 | ➔ `running` / `pending_capacity` | 调用宿主派发接口 |
| **`pending_capacity`** | 宿主并发容量不足，排队等待 | ➔ `ready` | **⚠️ 不计入失败次数**，一旦有任务释放空槽立即自动补位 |
| **`running`** | Subagent 正在沙箱中执行 | ➔ `succeeded` / `retry_pending` | 等待异步回执或退出通知 |
| **`retry_pending`** | Subagent 临时执行失败，等待重试 | ➔ `ready` | **只允许使用新 Subagent 重试**，严禁主调度器接管 |
| **`succeeded`** | 执行成功且回读验证通过 | ➔ _(终态)_ | 回执写入 `.build/receipts/{taskId}.json` |
| **`failed`** | 达到最大重试次数仍失败 | ➔ `failed` | 终止 Build 并报告阻断问题 |
| **`blocked`** | 宿主不支持或禁用了 subagent | ➔ `blocked` | 立即停止 Build，要求用户启用 Subagent |

---

## 三、 推进铁律

1. **单向不可逆**：`progress` 只能前进不能后退，不能跳跃。
2. **机器化门禁阻断**：必须由 `build_runtime.py advance` 独占更新 `progress`，主调度器与 Subagent 严禁擅自修改。
3. **容量背压与空槽即时补位**：遇到容量不足时保持 `pending_capacity`，任意子任务完成即刻触发下一批就绪任务提交。
4. **禁止内联接管**：任务无论遭遇何种失败，只能在 `retry_pending` 下重新派发 Subagent，严禁主调度器擅自内联接管业务执行。
