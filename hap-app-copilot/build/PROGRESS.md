# Progress 状态机与原子子任务生命周期 (PROGRESS)

本文档定义 HAP App Builder 的**全局阶段状态机 (Global Stage FSM)** 与 **原子子任务生命周期状态**。

---

## 一、 全局阶段状态机 (`hap-context.json.progress`)

所有阶段推进均由 `scripts/build_runtime.py advance` 在 `finalize` 生成的 `.build/phase-report.json` 放行（`canAdvance: true`）后独占原子写入。

| 状态值 | 含义 | 前置状态 | 阶段包含任务 |
|---|---|---|---|
| _(空/不存在)_ | 初始状态 | — | `build_runtime.py init` |
| `app_created` | 应用、导航分组、页面空壳与使用手册已就绪 | _(空)_ | Step 1 + Step 1b（主调度器内联完成） |
| `step2a_done` | 基础工作表已创建，待回填跨表关联 | `app_created` | Step 2a（存在 `relationLayout` 时进入） |
| `worksheets_created` | 所有工作表及跨表关联/子表均已落定 | `app_created` / `step2a_done` | Step 2b 完成（或无跨表关联直接由 Step 2a 跃迁） |
| `fields_refreshed` | 字段分片强校验合并完成，动作/视图/规则/助手空壳已就绪 | `worksheets_created` | Step 3（单表全要素）+ Step 4a（AI 助手创建） |
| `config_completed` | 导航内联排序及助手节点、页面、角色并发完成（`Step 5` 后台灌数非阻塞并行） | `fields_refreshed` | Step 7（内联）+ Step 4b + Step 6 + Step 8（`Step 5` 后台不阻塞推进） |
| `completed` | 系统流与动作流设计创建发布完成（`Step 5` 后台软收口不阻断终态） | `config_completed` | Step 10 + Step 11（无工作流时直接放行终结） |
| `failed` / `blocked` | 重试耗尽或宿主不支持 Subagent | _(任意)_ | 异常终止或前置门禁阻断 |

---

## 二、 原子子任务状态与推进铁律

1. **子任务生命周期**：`planned` ➔ `ready` ➔ `dispatching` ➔ `running`（容量满则暂置 `pending_capacity`，不计入失败次数，空槽即时补位）➔ `succeeded`（临时失败入 `retry_pending` 重新派发新 Subagent，耗尽入 `failed`）。
2. **单向原子推进**：`progress` 严禁手工涂改或跳步，一律以 `.build/receipts/` 下的真实校验回执为准。
3. **轻重职责严明**：Step 1、Step 1b、Step 7 轻量全局动作由主调度器内联完成；Step 2a ～ Step 6、Step 8、Step 10 ～ Step 11 重资产任务必须由独立 Subagent 执行，子任务失败时只允许重新派发独立 Subagent 重试。
