# HAP 应用视觉主题、导航与图标挑选规范 (spec-app-styles)

本文档是 HAP 应用外观视觉、主题配色、导航布局与图标挑选的**唯一规范与事实源 (SSOT)**。在规划方案（Plan）、创建应用（Build）、调整样式（Modify）以及交互审查（Audit）阶段均以此为准。

---

## 一、 黄金 9 色板主题配色方案

**推荐使用以下 9 种精选的 HAP 高端主题颜色**，拥有极佳的色彩质感，并可以保证反白文字的最佳可读性。严禁在系统配置中传入纯红、纯绿等低质感 Hex 色值：

| Hex 色值 | 配色名称 | 视觉感知与推荐业务场景 |
| :--- | :--- | :--- |
| **`#A00416`** | **典雅红** | 风险控制、警报、高优先级的核心金融或生命科学模块。 |
| **`#F21B65`** | **活力粉** | 时尚、零售、社交娱乐、以客户体验为核心的协同板块。 |
| **`#FC532E`** | **温暖橙** | 物流配送、现场服务、警示提醒、以及敏捷运营看板。 |
| **`#8E481B`** | **质感棕** | 历史档案、物资仓储、重型设备管理、公共资源归档等。 |
| **`#732ED1`** | **睿智紫** | 人工智能、高新技术、战略规划、创意设计、前瞻性业务系统。 |
| **`#3054EB`** | **科技蓝** | 通用且稳重的主力配色。推荐用于核心业务流水、综合看板、工作量统计（**默认推荐**）。 |
| **`#21710F`** | **生态绿** | 环境保护、供应链、农业技术、企业健康度等。 |
| **`#4CAF50`** | **清新绿** | 敏捷任务状态（如“正常/已完成”）、日常审批、用户自助服务。 |
| **`#4051B6`** | **商务深蓝** | 严谨的 HR 组织架构、合同档案、系统配置表、权限后台。 |

---

## 二、 导航栏配色方案 (navColor)

只能从以下三个官方枚举值中选择（**严禁自定义 HEX 色值，系统不支持**）：

| 枚举值 | 说明 | 适用场景 |
| :--- | :--- | :--- |
| **`appColor`** | 导航栏使用应用主题色（暗色系） | 蓝、绿、紫等深色主题应用（**默认推荐**） |
| **`white`** | 导航栏白色背景 | 红、橙、黄等亮色暖色系主题应用 |
| **`black`** | 导航栏纯黑背景 | 重工制造、监控中心、品牌工作台等少数场景 |

---

## 三、 导航布局形态 (navLayout)

根据应用的业务场景和复杂度选择：

| 场景 | 取值 | 适用业务类型 |
| :--- | :--- | :--- |
| **默认（大多数业务系统）** | `group` | ERP、CRM、WMS、OA 等典型业务流应用（**默认推荐**） |
| **结构复杂、层级深** | `tree` | 多级组织架构、多级科目/分类、复杂设备台账 |
| **多业务域并列** | `top` | 门户型大屏看板、表单数量极少（≤ 4 个）的轻量工具 |
| **门户/工作台型** | `card` | 首页入口导流型工作台应用 |

---

## 四、 预设受控图标库 (Icon Selector)

在配置应用、工作表、自定义动作、导航项或页面的 `icon` 字段时，**推荐**从下述经过官方精选的 HAP 图标 `font_class` 库中挑选最贴切的一个。**严禁凭空捏造图标名称**：

### 1. 基础资料 / 档案 / 文档
- `sys_1_6_document` — 文档/资料
- `sys_8_4_folder` — 文件夹/归档
- `sys_table` — 数据表/台账
- `sys_12_2_book` — 书籍/图书
- `sys_certificate_object` — 证书/认证
- `sys_8_3_briefcase` — 业务/公文
- `sys_notes_object` — 备注/记录
- `sys_8_2_bookmark_ribbon` — 书签/收藏

### 2. 人员 / 客户 / 团队
- `sys_6_3_user_male` — 用户/人员
- `sys_6_2_female_user` — 用户
- `sys_1_10_people` — 团队
- `sys_6_1_user_group` — 用户组/群组
- `sys_contacts_office` — 联系人/通讯录
- `sys_1_9_address_book` — 通讯录
- `sys_5_4_contact_card` — 名片/档案
- `sys_badge2_office` — 员工/工牌
- `sys_1_8_online_support` — 客户/客服

### 3. 财务 / 资金 / 支付 / 订单
- `sys_bill_finance` — 账单/费用
- `sys_money_finance` — 资金/支付
- `sys_3_2_money_box` — 资产
- `sys_3_1_coins` — 积分/硬币
- `sys_wallet_finance` — 钱包
- `sys_credit-card_finance` — 信用卡/支付
- `sys_bank-statement_finance` — 对账/银行
- `sys_money-transfer_finance` — 资金转账
- `sys_1_2_order` — 订单
- `sys_1_3_us_dollar` — 交易/金额
- `sys_coupon_finance` — 优惠券
- `sys_chart-growth_finance` — 营收趋势

### 4. 库存 / 仓储 / 物流
- `sys_18_5_warehouse` — 仓库
- `sys_7_1_truck` — 物流/运输
- `sys_delivery1_traffic` — 配送
- `sys_delivery-fast_traffic` — 快递
- `sys_15_10_barcode` — 条码/库存
- `sys_15_11_qr_code` — 二维码/扫描
- `sys_11_1_tool_storage_box` — 物料/工具
- `sys_cabinet_object` — 柜/存档

### 5. 商品 / 购物 / 门店
- `sys_13_1_shop` — 商店
- `sys_13_2_shopping_bag` — 购物袋
- `sys_13_3_shopping_cart_loaded` — 购物车
- `sys_store2_place` — 门店

### 6. 工单 / 服务 / 维保
- `sys_11_4_services` — 服务
- `sys_11_3_support` — 支持/帮助
- `sys_11_2_maintenance` — 维保/设备
- `sys_2_5_handshake` — 合作
- `sys_handshake_office` — 协作

### 7. 项目 / 任务 / 进度
- `sys_board2_object` — 看板/任务
- `sys_todo_office` — 待办
- `sys_bullet-list_office` — 列表/事项
- `sys_progress_symbol` — 进度
- `sys_timeline_symbol` — 时间线
- `sys_goal5_office` — 目标
- `sys_tactic_activity` — 计划
- `sys_medal2_object` — 荣誉/绩效

### 8. 审批 / 流程 / 安全 / 合规
- `sys_1_7_approval` — 审批/通过
- `sys_16_1_checked` — 确认/勾选
- `sys_10_3_security_checked` — 审核/安全
- `sys_10_2_lock` — 权限/锁
- `sys_decision-process_symbol` — 流程
- `sys_signature_symbol` — 签名

### 9. 时间 / 日程 / 提醒
- `sys_4_1_calendar` — 日历/排期
- `sys_4_2_clock` — 时间
- `sys_4_3_alarm_clock` — 提醒/闹钟
- `sys_10_7_bell` — 通知

### 10. 统计 / 看板 / 图表
- `sys_control-panel_traffic` — 仪表盘
- `sys_2_3_statistics` — 趋势分析
- `sys_2_1_bar_chart` — 柱状图
- `sys_2_2_pie_chart` — 饼图
- `sys_1_1_combo_chart` — 组合分析
- `sys_chart-pie_office` — 报告/占比
- `sys_chart-bar_finance` — 经营图表

### 11. 工作台 / 门户
- `sys_casino_place` — 公司/企业
- `sys_home1_place` — 首页/门户
- `sys_form_symbol` — 表单
- `sys_10_1_health_data` — 工作台
- `sys_app_symbol` — 应用/模块

### 12. AI 助手
- `sys_17_6_reddit` — 机器人
- `sys_16_3_about` — 咨询
- `sys_1_8_online_support` — 客服
- `sys_16_6_genius` — 智慧/大脑

### 13. 通信 / 消息 / 位置
- `sys_5_1_chat` — 聊天
- `sys_5_3_message` — 消息
- `sys_5_2_phone` — 电话
- `sys_notification_object` — 通知
- `sys_9_2_map` — 地图
- `sys_9_1_map_marker` — 定位
- `sys_9_3_marker` — 标记

### 14. 通用 / 工具 / 行业
- `sys_1_5_create_new` — 新建
- `sys_10_11_filter` — 筛选
- `sys_custom_actions` — 操作
- `sys_15_2_picture` — 图片
- `sys_15_1_camera` — 相机
- `sys_bulb_office` — 想法/方案
- `sys_2_4_training` — 培训
- `sys_12_1_graduation_cap` — 教育
- `sys_17_1_meeting` — 会议
- `sys_conference-room_object` — 会议室
- `sys_18_2_factory` — 工厂/制造

---

## 五、 样式与图标挑选黄金法则

1. **绝对语义匹配**：颜色和图标的设计表意必须能完美投射到实际工作表/页面的业务范畴。
2. **多表色彩打散**：如果应用内包含多张工作表，**应合理分配 9 种主题色，避免所有工作表均使用同一种颜色**。
3. **零图标雷同**：同一应用内，**不同的实体工作表或自定义页面应分配不同的图标**，避免默认同一图标产生认知混淆。
4. **严格受限**：绝对不要尝试猜测或合成任何非常规图标名称。
