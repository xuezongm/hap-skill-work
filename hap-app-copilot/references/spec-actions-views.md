# 视图与自定义动作完整平台规格 (spec-actions-views)

本文档是 HAP（明道云）平台关于 **自定义动作创建（create_custom_actions）**、**9 种视图类型配置（create_view）**、**图标颜色规范** 与 **视图高级交互（quickFilters / filterList / group / card / color）** 的唯一权威事实源（SSOT），1:1 对齐官方生产级设计规范。

---

## 目录

1. [执行顺序与依赖硬约束](#一-执行顺序与依赖硬约束)
2. [自定义动作搭建规范 (create_custom_actions)](#二-自定义动作搭建规范-create_custom_actions)
3. [自定义动作图标 (_svg) 与颜色规范](#三-自定义动作图标-_svg-与颜色规范)
4. [enableWhen 触发条件规范 (in 数组铁律)](#四-enablewhen-触发条件规范-in-数组铁律)
5. [9 种视图类型配置规范](#五-9-种视图类型配置规范)
6. [视图 7 级业务排序优先级](#六-视图-7-级业务排序优先级)
7. [视图预设筛选 (filter 与动态时间/人员值)](#七-视图预设筛选-filter-与动态时间人员值)
8. [三大交互入口字段互斥约束 (quickFilters / filterList / group)](#八-三大交互入口字段互斥约束-quickfilters--filterlist--group)
9. [记录卡片摘要规范 (card)](#九-记录卡片摘要规范-card)
10. [操作按钮挂载规范 (actions: detailActions / quickActions)](#十-操作按钮挂载规范-actions-detailactions--quickactions)
11. [SingleSelect 记录着色规范 (color)](#十一-singleselect-记录着色规范-color)

---

## 一、 执行顺序与依赖硬约束

在针对单表进行全要素配置时，必须严格遵守依赖顺序：
1. **若包含自定义动作** → 先调用 `create_custom_actions`，拿到返回的 `actionIdByName` 映射；
2. **然后创建视图** → 调用 `create_view` 按规划顺序一次性批量创建视图（视图中的 `quickActions` / `detailActions` 引用生成的 `actionId`）；
3. **若无自定义动作** → 直接调用 `create_view`。

---

## 二、 自定义动作搭建规范 (create_custom_actions)

| type | 说明 | 必填额外参数 |
|---|---|---|
| `updateCurrentRecord` | 允许用户填写当前记录的指定字段 | `updateFields`（字段 alias 或 ID 列表） |
| `createRelatedRecord` | 在关联表中新建一条关联记录 | `relationField`（关联字段 alias 或 ID） |
| `triggerWorkflow` | 直接触发绑定的工作流 | 无 |

- **`updateFields` 推断**：根据动作描述中“用户填什么”，挑选对应字段的 alias 列表；
- **`relationField` 推断**：根据动作目标表，挑选本表中指向该目标表的 Relation 字段 alias。

---

## 三、 自定义动作图标 (_svg) 与颜色规范

### 1. 推荐动作图标库 (`icon`)
在配置自定义动作 `icon` 字段时，**必须且统一使用带 `_svg` 后缀的标准名称**：

| 业务场景 | 推荐图标名称（统一带 `_svg` 后缀） | 适用操作示例 |
|---|---|---|
| **审批 / 通过 / 确认** | `sys_16_1_checked_svg` | 审批通过、核验签收、确认完成、验收通过 |
| **驳回 / 拒绝 / 撤销** | `sys_10_3_security_checked_svg` / `sys_10_2_lock_svg` | 审批驳回、拒绝申请、撤销流程、锁定账号 |
| **新建 / 登记 / 补录** | `sys_1_5_create_new_svg` / `sys_1_6_document_svg` / `sys_notes_object_svg` | 登记异常、新建关联单据、录入明细、添加备注 |
| **借阅 / 领用 / 调拨** | `sys_12_2_book_svg` / `sys_11_1_tool_storage_box_svg` / `sys_3_2_money_box_svg` | 借出图书、领用物料、资产调拨、领用申请 |
| **发货 / 配送 / 物流** | `sys_delivery1_traffic_svg` / `sys_7_1_truck_svg` | 仓库发货、安排配送、快递发揽、现场派送 |
| **归还 / 入库 / 归档** | `sys_18_5_warehouse_svg` / `sys_cabinet_object_svg` / `sys_8_4_folder_svg` | 归还图书、入库上架、归档卷宗、物资回库 |
| **编辑 / 更新 / 填报** | `sys_form_symbol_svg` / `sys_progress_symbol_svg` | 填写反馈、更新进度、补充说明、修改参数 |
| **分配 / 指派 / 派单** | `sys_6_3_user_male_svg` / `sys_contacts_office_svg` | 派单给工程师、指派负责人、转交处理 |
| **支付 / 结算 / 扣费** | `sys_money_finance_svg` / `sys_bill_finance_svg` / `sys_wallet_finance_svg` | 支付费用、确认结算、发起退款、产生账单 |
| **提醒 / 催办 / 通知** | `sys_4_3_alarm_clock_svg` / `sys_10_7_bell_svg` | 一键催办、到期提醒、发送通知、邮件告警 |
| **扫码 / 条码 / 盘点** | `sys_15_10_barcode_svg` / `sys_15_11_qr_code_svg` | 扫码出库、扫描盘点、生成二维码 |
| **报损 / 作废 / 挂失** | `sys_notes_object_svg` / `sys_certificate_object_svg` | 损坏报废、单据作废、遗失挂失 |

### 2. 按钮颜色 (`color`) 选型
| 动作语义 | 推荐 Hex 颜色值 | 适用按钮示例 |
|---|---|---|
| **无色 / 透明 / 辅助次级** | `"transparent"`（或不传） | 查看历史、添加备注、辅助次级操作 |
| **正面 / 完成 / 审核通过** | `#4CAF50`（清新绿） | 确认归还、审核通过、完成签到 |
| **常规 / 业务流转** | `#3054EB`（科技蓝） | 发起借阅、登记明细、提交申请 |
| **预警 / 催办 / 变动** | `#FC532E`（温暖橙） | 一键催办、申请延期、变更调整 |
| **高风险 / 驳回 / 报损** | `#A00416`（典雅红） | 报损报废、审批驳回、冻结账号 |
| **智能化 / 特殊功能** | `#732ED1`（睿智紫） | 智能诊断、生成分析 |

---

## 四、 enableWhen 触发条件规范 (in 数组铁律)

若按钮有前置状态要求，必须设置 `enableWhen`（最外层必须是 group）：
```json
"enableWhen": {
  "type": "group",
  "logic": "AND",
  "children": [
    { "type": "condition", "field": "biz_status", "operator": "in", "value": ["在借中", "已超期"] }
  ]
}
```
> [!CAUTION]
> **同一字段匹配多个值 = 单个 `in` condition + value 数组。严禁拆成多个 condition 用 AND 组合（逻辑上永远不成立）。**

---

## 五、 9 种视图类型配置规范

| 视图类型 (`type`) | 必填/核心配置参数 | 适用业务场景 |
|---|---|---|
| `table` | `tableFields`（列字段） | 明细浏览、快速判断、批量处理 |
| `kanban` | `config.groupField`（分组字段，如状态/阶段）、`card` | 流程推进、状态流转看板 |
| `gallery` | `card`（必须设 `coverField`） | 画廊浏览、商品图册、房源图册 |
| `calendar` | `config.dates = [{ startField, endField }]`、`card` | 日程排班、活动排期、到期日历 |
| `gantt` | `config.startField`、`config.endField` | 项目计划、进度里程碑 |
| `hierarchy` | `config.relationField`（树形自关联字段）、`card` | 组织架构、物料分类层级 |
| `resource` | `config.startField`、`config.endField`、`config.resourceField` | 车辆/会议室占用排班 |
| `map` | `config.locationField`（定位字段） | 门店分布、巡检点位地图 |
| `detail` | `config.mode`（`"all"` 或 `"first"`）、`card` | 单记录详情或参数配置 |

---

## 六、 视图 7 级业务排序优先级

1. **主工作入口视图** — 用户打开工作表后最先使用的视图（若是 Kanban/Gallery/Calendar/Gantt 承担主入口，直接排第一）；
2. **待处理 / 高频操作视图** — 如 `我的待办`、`待审批`；
3. **核心业务推进视图** — 如状态看板、项目甘特图；
4. **重要浏览辅助视图** — 如画廊、日历、地图；
5. **管理分析视图** — 如按部门分组、按月统计；
6. **`全部` 视图** — 兜底管理视图；
7. **归档 / 取消 / 日志视图** — 低频查阅。

---

## 七、 视图预设筛选 (filter 与动态时间/人员值)

视图名称暗示数据子集时必须设置 `filter`：
- **日期动态值**（`eq` 操作符）：`today`, `yesterday`, `tomorrow`, `last7Day`, `last30Day`, `thisMonth`, `lastMonth`, `nextMonth`, `thisYear`, `lastYear`；
- **人员动态值**（`eq` 操作符）：`user-self`（当前用户）。

```json
// 筛选本月我的工单
{
  "type": "group",
  "logic": "AND",
  "children": [
    { "type": "condition", "field": "biz_owner", "operator": "eq", "value": "user-self" },
    { "type": "condition", "field": "biz_create_time", "operator": "eq", "value": "thisMonth" }
  ]
}
```

---

## 八、 三大交互入口字段互斥约束 (quickFilters / filterList / group)

> [!CAUTION]
> **`quickFilters`、`filterList`、`group` 三者之间不能有重复字段。**

1. **`quickFilters`（快捷筛选栏，必配）**：每个视图必须配置 3~5 个高频字段（状态/负责人/优先级/分类/日期）；
2. **`filterList`（左侧分类导航）**："全部"类表格视图必须设置 `filterList`，选取分类/类型/状态（选项 ≥ 5）或关联分类表；
3. **`group`（分组展示）**：按人/按部门对比工作量时配置 `group`（枚举值 ≤ 10，禁止文本字段）。

---

## 九、 记录卡片摘要规范 (card)

- `titleField`：**必传**最能识别记录的主标题字段；
- `summaryField`：描述性文本，可选；
- `displayFields`：1～4 个关键字段；
- `coverField`：封面字段；
- `coverDirection`：`top` / `left` / `right`；
- `coverDisplayMode`：`full`（铺满） / `square`（方形） / `circle`（圆形）。
  - Gallery 视图优先 `top` + `full`；人员类数据 `left`/`top` + `circle`；其他优先 `right` + `square`。

---

## 十、 操作按钮挂载规范 (actions: detailActions / quickActions)

- `detailActions`：详情页右上角按钮（`["actionId_1", "actionId_2"]`）；
- `quickActions`：表格行/卡片快捷按钮（建议 ≤ 3 个）：
  - 系统操作：`{ "type": "print" }` / `{ "type": "delete" }` / `{ "type": "share" }`；
  - 自定义动作：`{ "type": "action", "id": "<actionId>" }`。

自定义动作与视图的关系遵守以下强制顺序：

1. 调用 `create_custom_actions` 创建动作并取得真实 `actionId`；
2. 明确动作需要出现在哪些视图，以及使用 `detailActions` 还是 `quickActions`；
3. 更新每个必要视图，将 `actionId` 挂载到正确位置；未明确需要的视图不得自动添加；
4. 回读视图确认挂载结果，同时核对目标角色能够访问该视图，并具备动作所需字段和记录操作权限。

仅创建动作不会使动作自动出现在任何视图中，也不能证明目标角色已经可以使用。

---

## 十一、 SingleSelect 记录着色规范 (color)

> ⚠️ **当工作表存在表示状态、阶段或优先级的 SingleSelect 字段时，table 和 kanban 视图必须设置 `color`，将该字段用作着色依据。**
