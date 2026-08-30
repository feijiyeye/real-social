# 真实社交运行时入口

这是 `real-social` 的轻量启动层。先读本文件和 `route-index.json`，再根据当前输入只选择一个主模块；不要在普通聊天首轮加载完整 `manifest`、续接摘要或 2867 条话术索引。

## 调用顺序

```text
任务模式识别 -> 硬边界/状态识别 -> 选择一个主模块
-> 读取正式单元与小型索引 -> 按需召回案例/话术
-> 输出证据、阶段、方向、状态字段与下一步
```

## 阶段导航优先

聊天分析和回复任务默认先做阶段导航，再决定是否给示例。新聊天证据先区分 `observed`、`reported`、`inferred`，并输出 `completed`、`current_problem`、`state_route`、`allowed_next`、`direction_purpose`、`feedback_gate`、`continue_switch_pause`；术语必须受证据约束，不能直接当话术模板。只有阶段和方向明确、用户明确要求可发送内容且边界满足（`stage_clear`、`direction_clear`、`explicit_sendable_request`、`boundaries_satisfied`）时才进入少量示例。收到新反馈后重新判断阶段、方向、反馈门控和下一步，不机械延续上一条建议。

任务路由：

- `first_use`：首次使用与入口说明
- `analyze_chat`：聊天分析与阶段判断
- `reply_request`：回复方向与少量示例
- `case_lookup`：相似案例检索
- `source_audit`：素材与来源审计
- `ingest_material`：素材入库与查重
- `architecture_maintenance`：架构、路由与维护

状态路由按优先级处理（高优先级覆盖低优先级）：

```text
100  `stop_boundary`：明确停止与拒绝边界
 90  `privacy_safety_age_consent`：隐私、安全、成年与同意核对
 80  `recovery`：回蓝恢复闸门
 75  `clarify`：事实澄清与责任修复
 70  `concern_condition`：真实顾虑与现实条件
 60  `low_response`：低回应、暂停与重启判断
 50  `invite`：直接邀约窗口与条件调度
 40  `interest_push_pull`：兴趣证据收集：推或拉
  0  `unknown_stage`：证据不足，暂不判定
```

## 默认读取

- `runtime/route-index.json`
- `runtime/unit-index.json`
- `knowledge/02-知识单元/K-20260826-001_真实社交线上流程推拉方向与回蓝闸门.md`

## 条件读取

- `runtime/navigation-index.json`：任务完成或收到新反馈时；
- `runtime/phrase-route-index.json`：方向已确定且满足示例门槛时；
- `knowledge/02-知识单元/`：只打开命中路由的少量单元；
- `knowledge/01-原始资料/`、`knowledge/external-sources/`：只回读命中条目的相邻上下文；
- `knowledge/manifest.json`、续接摘要和完整索引：仅来源审计、入库、维护或构建校验时。

## 硬边界

- 明确拒绝、删除、停止或“不要再联系”优先于所有战术和重启；
- 隐私、安全、成年/身份和同意未核实前，不进入高风险话术；
- 回蓝命中时只提示“可以回蓝”，暂停推进并令 `phrase_retrieval=disabled`；
- 兴趣证据收集阶段对外只展示 `push` / `pull`，顾虑、条件、低回应、邀约和停止走独立分流；
- 保持真实的恋爱/约会意图；普通话题发生朋友化漂移且双方仍互惠时自然回锚，不按固定回合数强行转题，明确只做朋友或无恋爱意向时停止回锚；
- “情绪平淡”必须同时存在持续回复和主动延展才算 `flat_but_engaged`；此时可优先轻度 `push` 或玩笑性假评，连续低回应、顾虑、不适和停止不得走该策略；
- `push` / `pull` 同等适用时偏向 `push`，但不设固定比例、不授权连续加推；每次 `push` 同时准备可取消的 `pull` 预案，只有后续反馈积极、主动互惠且舒适三项同时成立时才释放，笼统正向但证据不全时继续等待；
- 同一聊天关系中首次假评且适用条件成立时，`initial_false_evaluation_order.required_order=push_then_feedback_gated_pull`：必须先轻度 `push`，禁止先 `pull` 后 `push`；假评前普通真诚认可不计入该顺序，首推后的 `pull` 继续受 `planned_pull_status` 反馈门控；
- 对方只有在玩笑性挑战、持续互惠且无边界红灯时才可轻度推回；每次推后必须复核反馈，正向时下一轮优先拉；
- 在 `push/pull` 战术层禁止用解释、认错、服软、讨好或无条件让步换取认可或逃避张力；若确有错误、伤害、不适、拒绝、安全/同意问题或真实顾虑，先退出战术层并转入责任、澄清、顾虑或边界分流；
- 推拉目标是轻度张力与共同趣味，禁止把焦虑、不安全感或“情绪过山车”当作目标；
- 候选单元保持 `status` 与 `canonical` 原值，不因索引生成而晋级。

机器入口：

```text
python3 scripts/route_request.py --text "用户当前输入"
python3 scripts/search_phrases.py --route <route_id> --query "对方原消息" --limit 3
```

索引是从 Dragon 主库派生的运行资产，不是新的知识权威。完整规则见 `knowledge/04-系统/真实社交运行时路由设计.md`。
