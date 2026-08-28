# 示例数据与记录填充完整平台规格 (spec-sample-data)

本文档是 HAP（明道云）平台关于 **高仿真示例数据生成（batch_create_records）**、**字段类型值映射规范**、**内置虚拟用户库**、**分类预设附件资源库** 与 **主子关联拓扑填报** 的唯一权威事实源（SSOT），1:1 对齐官方生产级设计规范。

---

## 目录

1. [字段 ID 取值与调用约束](#一-字段-id-取值与调用约束)
2. [按工作表场景分层生成条数规则](#二-按工作表场景分层生成条数规则)
3. [字段类型填值格式对照全表](#三-字段类型填值格式对照全表)
4. [系统内置虚拟用户列表 (Collaborator)](#四-系统内置虚拟用户列表-collaborator)
5. [系统内置预设分类附件资源库 (Attachment)](#五-系统内置预设分类附件资源库-attachment)
6. [核心关系关联处理流程 (Relation)](#六-核心关系关联处理流程-relation)
7. [自关联字段两阶段创建规范](#七-自关联字段两阶段创建规范)
8. [明细子表 (SubTable) 示例数据创建规范](#八-明细子表-subtable-示例数据创建规范)
9. [数据拟真度与真实偏态分布要求](#九-数据拟真度与真实偏态分布要求)
10. [Payload 提交前自检清单](#十-payload-提交前自检清单)

---

## 一、 字段 ID 取值与调用约束

记录填值时字段标识 **必须使用真实的 24 字符 hex 字段物理 ID (fieldId / controlId)**，不能使用 alias 或字段中文名：
- **纯粹字段对象**：每个字段对象只传 `id` 和 `value`，不要传 `type`（MCP schema 中的 `type` 是控制标志，传 `"Attachment"` 会报错）；
- **工作流静默**：批量创建示例数据时 `triggerWorkflow` 固定传 `false`，避免示例数据触发自动化工作流产生垃圾通知；
- **跳过不可写字段**：系统字段、Divider、Formula、DateFormula、AutoNumber、Lookup、Rollup、Signature 等计算/系统/布局字段直接跳过不传值。

---

## 二、 按工作表场景分层生成条数规则

| 工作表场景 | 物理生成条数 | 判定依据与场景示例 |
|:---|:---|:---|
| **参数配置表 / 全局设置表** | **1 条** | 表名含 `设置`、`配置`、`参数`、`系统`，多为全局单值配置 |
| **字典 / 分类 / 标签表** | **3 条** | 作为关联基础数据的辅助表，如 `图书类型`、`任务状态`、`客户级别` |
| **核心业务表** | **8-10 条** | 系统的业务实体，如 `订单`、`合同`、`工单`、`项目`、`客户` |
| **子表（subTable）** | **每条主表记录 2~3 条明细** | plan 中 `worksheetType: "subTable"` 的表，紧随主表记录生成 |
| **自关联层级表** | **2 条根记录 + 5 条子记录** | 存在自关联 Relation 字段的层级表 |

---

## 三、 字段类型填值格式对照全表

| 字段类型 | 物理传值格式 | 规范要求与示例 |
|---|---|---|
| **Text / RichText** | `string` | 传真实内容字符串（如 `"北京朝阳研发中心"`） |
| **PhoneNumber / LandlinePhone** | `string` | 真实格式电话（`"13800138000"` 或 `"021-88888888"`） |
| **Email** | `string` | 真实格式邮箱（`"zhang.san@example.com"`） |
| **Number / Currency** | `number` | 纯数值，不带单位（`150`、`99.5`） |
| **SingleSelect / Dropdown** | `string[]` | **单个选项值放入数组**：`["进行中"]`（必须来自真实 options） |
| **MultipleSelect** | `string[]` | 多个选项值数组：`["电子产品", "办公耗材"]` |
| **Date / DateTime** | `string` | `"YYYY-MM-DD"` 或 `"YYYY-MM-DD HH:mm"`（集中在当前前后 3 个月） |
| **Time** | `string` | `"HH:mm:ss"`（如 `"14:30:00"`） |
| **Checkbox** | `number` | `1` 勾选，`0` 未勾选 |
| **Rating** | `string` | 纯数字字符串，如 `"4"`、`"5"` |
| **Location** | `string` | JSON 字符串：`"{\"x\":116.397428,\"y\":39.904989,\"address\":\"天安门广场\",\"title\":\"北京天安门\"}"` |
| **Region** | `string` | 行政区划代码，如 `"110100"`（北京市）、`"310000"`（上海市） |
| **Collaborator** | `string[]` | 至少 1 条用当前用户 `accountId`，其余从虚拟用户列表选取 |
| **Attachment** | `object[]` | `[{"name":"业务合同.pdf", "url":"https://..."}]` |
| **Relation** | `string[]` | 传入目标表的真实 `rowId` 数组 |
| **不可写类型** | **直接跳过** | Signature, AutoNumber, Formula, DateFormula, Lookup, Rollup, Divider |

---

## 四、 系统内置虚拟用户列表 (Collaborator)

填充 `Collaborator` 字段时：
- **至少 1 条记录**使用当前用户的 `accountId`；
- **其余记录**从以下内置虚拟用户打散选取：

| userId | 姓名 (中文系统) | userId | 姓名 (英文系统) |
|---|---|---|---|
| `virtualuser-cn-1` | 赵子轩 | `virtualuser-en-1` | Michael Brown |
| `virtualuser-cn-2` | 刘思涵 | `virtualuser-en-2` | Emma White |
| `virtualuser-cn-3` | 周睿哲 | `virtualuser-en-3` | Robert Lee |
| `virtualuser-cn-4` | 林雨欣 | `virtualuser-en-4` | Emily Davis |
| `virtualuser-cn-5` | 孙泽宇 | `virtualuser-en-5` | John Smith |
| `virtualuser-cn-6` | 陈嘉怡 | `virtualuser-en-6` | David Wilson |
| `virtualuser-cn-7` | 王强 | `virtualuser-en-7` | Sophia Johnson |
| `virtualuser-cn-8` | 张丽莉 | `virtualuser-en-8` | James Miller |
| `virtualuser-cn-9` | 李浩宇 | `virtualuser-en-9` | Olivia Taylor |
| `virtualuser-cn-10` | 吴勇 | `virtualuser-en-10` | David Anderson |

---

## 五、 系统内置预设分类附件资源库 (Attachment)

填充 `Attachment` 字段时，必须根据字段语义从下方资源库中精准选型，且传入时必须重命名为契合当前记录的业务文件名：
- **文档类字段**（合同/协议/报告/方案/清单/台账/附件等）➔ **必须使用【文档类资源】**（PDF/DOCX/XLSX 直链）；
- **图片类字段**（照片/封面/主图/实拍/头像/现场等）➔ **必须从 [`references/resource-sample-images.md`](./resource-sample-images.md) 中获取直链**，按实体类型从对应分类中精准挑选；
- **全量填充铁律**：所有附件字段必须填充数据，不得留空；无 100% 契合图片时从所属类目挑选最接近/最不违和的图片。

*传值示例*：`{ "id": "contract_file", "value": [{"name": "2025年度框架采购协议.pdf", "url": "https://p2.mingdaoyun.cn/sampledocument/74005043-A19F-4704-942B-DC63C13986DA.pdf"}] }`

### 1. 文档类静态资源
| 文件类型 | 静态资源 URL | 适用场景 |
|---|---|---|
| **PDF** | `https://p2.mingdaoyun.cn/sampledocument/74005043-A19F-4704-942B-DC63C13986DA.pdf` | 合同、协议、报告、规格书、制度 |
| **DOCX** | `https://p2.mingdaoyun.cn/sampledocument/FF4297A4-7C5F-45CC-982A-CAA5DEE6EFEB.docx` | 方案、总结、通知、申请草案 |
| **XLSX** | `https://p2.mingdaoyun.cn/sampledocument/50E3CEC4-1CA6-4633-9248-4266E1AF685F.xlsx` | 台账、清单、明细表、数据底表 |

### 三、 全量高可用静态图片资源库（8 大分类）

> 📖 **全量图片直链清单**：详见 **[`references/resource-sample-images.md`](./resource-sample-images.md)**

遇到图片/封面/照片等字段时，必须读取 `resource-sample-images.md` 并根据以下 8 大类目按需选型：

| 分类类目 | 涵盖关键词与典型场景 | 选型指引与数据要求 |
|---|---|---|
| **商品/物品 (Product)** | 订书机、笔、零件、耗材、家电、图书、鲜花、食物、鞋、服饰、美妆、数码、办公等 | 用于商品档案、物料清单、库存主数据、采购品项等实体物品展示 |
| **资产/设备 (Asset)** | 生产设备、IT设备、工具、车辆、货车、巡检仪器、维修备件等 | 用于固定资产台账、设备档案、工具领用、车辆调度等 |
| **空间/位置 (Location)** | 货架、库位、仓库、门店、酒店、浴室、会议室、房间、公共区域等 | 用于仓储库位管理、门店巡店、不动产房源、场地预订等 |
| **凭证/现场 (Proof)** | 物流、码头、轮船、施工现场、巡检记录、培训、安装、验收、拜访、加工等 | 用于工单现场拍照、履约交付凭据、巡检签到证据等 |
| **问题/故障 (Issue)** | 故障维修、安全隐患、货损货差、包装破损、质量异常、图纸缺陷等 | 用于报修工单、质检瑕疵、缺陷跟踪、事故定损等 |
| **运营/推广 (Marketing)** | 宣传海报、活动横幅、运营推广图、展板等 | 用于营销活动、公告通知、Banner 封面等 |
| **截图说明 (Screenshot)** | 软件界面截图、系统操作说明图等 | 用于知识库说明、操作手册、Bug 提报截图等 |
| **用户头像 (Avatar)** | 男士头像、女士头像 | 用于员工档案、客户联系人名片、用户主页头像等 |

---

## 六、 核心关系关联处理流程 (Relation)

1. **内存绑定**：按拓扑顺序逐表处理（基础表先、业务表后），上游表调用 `batch_create_records` 返回的 `rowId` 当场缓存，创建下游表时直接映射填入 Relation 字段；
2. **缺失跳过**：若目标关联表尚未创建导致无可用 rowId，在本次写入中直接跳过该 Relation 字段。

---

## 七、 自关联字段两阶段创建规范

当 Relation 关联本表自身时：
- **阶段一**：调用 `batch_create_records` 插入 2 条根记录，不传自关联字段，捕获 2 条根 rowId；
- **阶段二**：再次调用 `batch_create_records` 插入 5 条子记录，在自关联字段中填入阶段一的根 rowId。

---

## 八、 明细子表 (SubTable) 示例数据创建规范

- **创建时机**：主表记录创建成功之后；
- **按主表分批**：为主表的每条记录分别生成 2~3 条明细行；
- **绑定主表关联字段（必须执行）**：在子表的 `fields` 中找到指向主表的 `Relation` 关联字段（`dataSource` 为主表 `id`），在生成的每条子表记录中，**必须给该关联字段填入对应主表记录的 `rowId`**（传格式如 `["主表真rowId"]`）。若不传主表 `rowId`，子表记录将成为孤儿数据，无法在主表详情页内嵌显示！

---

## 九、 数据拟真度与真实偏态分布要求

- **拟真**：用真实业务用语，不用"测试 1 / 示例 A / 占位"。例如图书表使用真实中外书名，HR 模块使用真实岗位和部门层级
- **多样**：覆盖不同状态 / 不同分类（如待处理 / 处理中 / 已完成 / 已取消）
- **关联**：Relation 字段引用上一批 batch_create_records 返回的真 rowId（按表名映射）
- **条数按场景**：参数配置表 1 条、字典/分类表 3 条、核心业务表 8-10 条（详见第 1 节）
- **偏态分布**：分配状态、单选选项或关联记录时，**禁止按均等概率分配**。应模拟真实业务形态（例如：大部分订单处于"已完成"或"履行中"，极少数处于"退款中"；某些类型数据应呈现集中趋势），使统计看板产生真实的可视化效果
- **严格选项匹配**：选项字段填充的值必须一字不差地匹配 `fieldOptionsContext` 中的选项，严禁凭空构思不存在的选项文字

---

## 十、 Payload 提交前自检清单

1. ✅ 每个 `fields[].id` 均为目标工作表的真实 24 字符 hex 物理字段 ID；
2. ✅ 标题字段在每条记录中均有明确业务值；
3. ✅ 选项字段的值在对应的 options 选项集中严格存在；
4. ✅ Relation 字段的值为真实存在的目标表记录 `rowId`（非虚构编造）；
5. ✅ `worksheet_id` / `worksheetId` 与目标工作表物理 ID 完全一致。
