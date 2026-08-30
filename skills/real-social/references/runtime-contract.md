# 运行时输出契约

运行时先把当前 Skill 目录下的 `knowledge/` 设为唯一知识根目录，并读取 `runtime/runtime-entry.md`、`runtime/route-index.json` 和 `runtime/unit-index.json`。普通聊天不读取完整 `knowledge/manifest.json`；只有来源审计、构建或校验时才读取它。不得依赖构建机器的绝对路径；历史绝对来源路径在需要回读时通过 manifest 的 `source_path_map` 解析到包内文件。

## 两级路由契约

每次调用先识别 `task_route`，再按优先级识别 `state_route`。状态路由覆盖一般任务意图；最终只选择一个 `primary_module`，最多携带两个 `auxiliary_modules`。机器路由只缩小读取范围，不替代证据判断。

```json
{
  "task_route": "analyze_chat",
  "state_route": "interest_push_pull",
  "primary_module": "interest_push_pull",
  "auxiliary_modules": [],
  "read_plan": {
    "required": [],
    "deferred": [],
    "phrase_retrieval": "enabled_after_context_review"
  }
}
```

状态优先级固定为：`stop_boundary` -> `privacy_safety_age_consent` -> `recovery` -> `clarify` -> `concern_condition` -> `low_response` -> `invite` -> `interest_push_pull` -> `unknown_stage`。完整匹配词和读取计划见 `runtime/route-index.json`。

普通聊天的最小读取集是运行时入口、路由索引、单元索引和正式流程单元 `K-20260826-001`。完整话术索引、续接摘要、原始资料和外部来源均为按需资源。

## 输入最低要求

优先要求用户提供：最近一段完整聊天、说话人、消息时间间隔、关系背景、当前目标、上一轮发生了什么，以及已经知道的边界。信息不足时只追问真正影响阶段判断的变量。

## 元数据兼容

新知识单元必须使用当前 Schema 的 `type`、`version`、`canonical` 和 `status: canonical/candidate/...` 字段。只有 Dragon 知识库兼容清单中登记的历史单元，才允许保留 `status: active`；运行时必须同时确认其 `canonical: true`，不得把未登记的 `active` 单元当作正式知识。

## 阶段判断

输出当前阶段节点、最多三个候选阶段节点、可能命中的候选分链、置信度、支持证据和反证。体系不设唯一主链：相同阶段节点可以被多条分链复用，不同顺序或转移条件保留为不同分链。证据不足、多个阶段互斥或命中未裁决冲突时，使用“暂不判定”并提出澄清问题。

阶段识别和分链识别是两个层次：先判断当前在什么状态，再判断这条状态序列更接近哪些案例分链。不能因为命中某条分链，就把该分链的下一步当成必然动作。

## 方向教学

阶段确认后，每个方向至少说明：目标、适用条件、预期代价、不适用条件。默认提供方向，不提供完整回复。

## 阶段导航优先原则

本原则仅约束聊天分析和回复任务；素材审计、入库和架构维护继续使用各自的输出契约。默认交付先建立阶段导航，不先给孤立句子。收到新的聊天证据后，先把证据分为 `observed`（可直接看到的消息或行为）、`reported`（客户或来源明确报告的情况）和 `inferred`（基于前两者的暂定推断），再输出：已完成事项、当前要解决的问题、当前阶段节点及最多三个候选分链、适用的 `state_route`、下一步允许的 `push` / `pull` 或独立分流、方向目的、待观察反馈，以及继续、切换或暂停条件。阶段名称和体系术语只能解释有证据支持的结构与转移条件，不能直接充当话术模板。

日常话题可以服务于激活、主题、调整、前提、恋爱意图回锚或邀约签约，但不能让局部句子取代整体进程判断。只有阶段与方向已经明确、用户明确要求可发送内容且边界条件满足时，才补充少量示例；示例必须服从阶段导航，不能替代阶段、方向、反馈分流或安全判断。收到新反馈后，必须重新计算阶段、方向、反馈门控和下一步，取消不再适用的预案，不机械延续上一条建议。

## 正式线上流程方向与分流

兴趣证据收集阶段对外只提供两个主要战术方向：`push` 和 `pull`。`push` 只能在对方持续参与、已有互惠和舒适基础且没有拒绝或不适信号时，用于轻度增加张力或推进关系主题；`pull` 用于认可、增加连接、降低距离、恢复舒适、换线或留出空间。

推拉组合运行字段和判定：对方的玩笑性挑战或轻度反驳只有在持续自愿参与、互惠舒适且无边界红灯时才允许轻度推回；每次 `push` 后 `post_push_check` 必须为 `required`，正向反馈时 `pull_after_push` 为 `preferred_if_positive_feedback`。反馈不明或转负时停止追加 `push` 并按证据分流。`push_purpose` 固定为 `light_tension_and_feedback`，`roller_coaster_goal` 固定为 `forbidden`。

`romantic_intent_anchor` 固定保持真实的恋爱/约会目标。普通话题持续并发生朋友化漂移且双方仍互惠时，轻量回锚关系或约会方向；`fixed_turn_count` 必须为 `forbidden`。明确只做朋友、没有恋爱意向、低回应、不适或停止时，回锚被阻断并转入相应状态分流。

`neutral_affect` 只表示情绪表达相对平淡，必须和 `engagement_state` 分开记录。只有 `affect_state=neutral` 且 `engagement_state=reciprocal`、并排除顾虑与边界信号时，才构成 `flat_but_engaged`；情绪平淡或朋友化漂移缺少互惠证据时，保持 `unknown_stage` 或追问，不授权动作。此时同等适用方向中 `direction_preference=push`。`direction_bias.ratio_policy` 固定为 `qualitative_preference_not_fixed_quota`，不得从中推导连续 push 或数字比例。

每次选择 push 时都建立 `planned_pull` 静态策略预案；当前动态状态单独记录在 `planned_pull_status`。反馈前 `planned_pull_status=pending_feedback`。只有 `post_push_feedback=positive`、`engagement_state=reciprocal`、`comfort_state=comfortable` 且没有负向情绪证据时，才标记 `ready` 并优先 pull；笼统正向但互惠或舒适证据不全时仍为 `pending_feedback`，反馈不明、变淡、转负或出现顾虑时标记 `blocked`。`tactical_direction` 表示实际允许的下一方向：`pending_feedback` / `blocked` 时为 `null`，`ready` 时才可为 `pull`，不得照抄与状态冲突的请求方向。

`false_evaluation_stage=first` 表示同一聊天关系中第一次启动假性评估组合。只有当前仍适用 `interest_push_pull`、`engagement_state=reciprocal`、`comfort_state=comfortable` 且无顾虑或边界红灯时，`initial_false_evaluation_order.required_order` 才激活为 `push_then_feedback_gated_pull`：即使请求先 pull，实际起手方向也必须是 push。若互惠或舒适证据不足，`initial_false_evaluation_status=awaiting_eligibility` 且 `tactical_direction=null`；若首推已发出，则由既有 `planned_pull_status` 门控决定等待、放行 pull 或阻断，不能再次强制 push。假评前的普通真诚认可、礼貌回应或非假评连接应标记为 `not_applicable`，不构成先拉后推。

推拉战术层的 `tactical_action_constraints` 固定禁止 `over_explaining`、`defensive_justification`、`performative_apology`、`strategic_concession` 和 `appeasement_or_boundary_abandonment`。真实澄清、真诚道歉和尊重边界的调整只能在退出战术层后进入相应责任、顾虑或边界分流；该约束不是全局禁止解释或道歉。

真实顾虑、条件调度、低回应、直接邀约窗口、停止边界和证据不足不是第三种战术方向，而是独立分流。若当前情形既不适合 `push` 也不适合 `pull`，输出“暂不操作/需要更多证据”，不得强迫二选一。正式细则见 `knowledge/02-知识单元/K-20260826-001_真实社交线上流程推拉方向与回蓝闸门.md`。

回蓝是可跨阶段触发的操作者恢复闸门，不是聊天阶段、女性兴趣信号、回复方向或重新联系许可。命中后只提示暂停推进、收回投入，并设置 `phrase_retrieval: disabled`；不检索、展示、改写或生成任何回蓝话术。明确拒绝、停止、删除或“不要再联系”始终优先，回蓝不能覆盖或改写这些边界。

## 示例门槛

用户明确选择方向并要求参考答案时，才生成示例。用户明确要求直接回复但未选方向时，先用最少问题对齐其当下想达成的结果、希望语气或主要顾虑；需求明确后，由 AI 从已展示的 2-4 个方向中选择最匹配的一条并说明依据，再生成 1-3 个示例。需求仍不清楚时不得随机代选。

示例必须标为“示例”，不能伪装成体系唯一答案，也不能从单个案例推导普遍规律。检索话术时先查人工候选清单和 Apple Notes 增补，再按需查完整去重索引；每次命中都要回读来源上下文、核对说话人并通过边界过滤。回蓝闸门命中时只输出状态、依据、暂停动作和重新判断条件，禁止生成任何具体话术。

双方明确进入同类性/亲密话题后，相关露骨表达可以进入候选检索，但仍要核对成年和身份依据、持续互惠反馈、退出条件以及拒绝或不适信号。明确拒绝、停止、不适、欺骗、施压、强迫、羞辱和私密空间诱导不因性话题而放行。

脚本的 `--sexual-context` 仅保留为上游兼容标记，不是四项核对的替代品；调用亲密路由时仍必须同时传入 `--explicit-same-topic`、`--age-identity-basis`、`--mutual-feedback` 和 `--no-refusal-or-discomfort`。

## 案例教学

优先召回 1-3 个 `canonical` 案例；若没有已审核案例，可召回 `callability: candidate_callable` 的讲解型案例作为候选参考，但必须标明 `candidate`、`source_reported` 或其他结果状态。写清相似点、差异、原案例结果和不能迁移的部分。案例结果不是保证，案例中的来源操作也不等于默认推荐。

## 失败状态

- `unknown_stage`：证据不足，暂停判断。
- `conflicting_rules`：体系内冲突未裁决，报告冲突编号。
- `unconfigured_framework`：阶段或价值观尚未配置，只做素材审计。
- `privacy_redaction_needed`：材料包含可识别第三方信息，先要求脱敏。
- `source_unavailable`：manifest 和包内来源目录都无法解析历史来源路径，明确说明不可回读，不以相似文件替代。

## 正式流程运行字段

运行记录应尽量保留以下字段，以区分战术方向和安全分流：

```yaml
tactical_direction: push | pull | null
stage_navigation:
  priority: before_reply
  scope: [analyze_chat, reply_request]
  evidence_layers: [observed, reported, inferred]
  max_stage_candidates: 3
  required_outputs: [completed, current_problem, state_route, allowed_next, direction_purpose, feedback_gate, continue_switch_pause]
  examples_require: [stage_clear, direction_clear, explicit_sendable_request, boundaries_satisfied]
  on_new_feedback: reassess_stage_direction_feedback_gate_next_step
  terminology_policy: evidence_bound_not_template
  mechanical_continuation: forbidden
push_back_eligible: true | false | unknown
post_push_check: required
pull_after_push: preferred_if_positive_feedback | not_applicable | blocked
push_purpose: light_tension_and_feedback | null
tactical_action_constraints:
  status: forbidden_in_push_pull
  disallowed: [over_explaining, defensive_justification, performative_apology, strategic_concession, appeasement_or_boundary_abandonment]
  allowed_only_outside_tactical: [truthful_clarification, genuine_apology, boundary_respecting_adjustment]
  redirect_on: factual_error_or_harm | explicit_discomfort_or_stop | safety_consent_age | logistics_or_mutual_negotiation
romantic_intent_anchor:
  target: honest_romantic_or_dating_intent
  fixed_turn_count: forbidden
  blocked_by: friend_only_boundary | romantic_disinterest | low_response | discomfort | stop_boundary
intent_alignment: aligned | drifted | friend_only_boundary | unknown
romantic_reanchor_permitted: true | false | unknown | not_applicable
intent_boundary_reason: friend_only_declared | null
affect_state: neutral | expressive | negative | unknown
engagement_state: reciprocal | low | unknown
comfort_state: comfortable | uncertain | uncomfortable | unknown
flat_but_engaged: true | false
direction_preference: push | pull | push_if_both_eligible | none | unknown
direction_bias:
  when_both_eligible: prefer_push
  ratio_policy: qualitative_preference_not_fixed_quota
false_evaluation_stage: first | later | not_applicable | unknown
initial_false_evaluation_order:
  required_order: push_then_feedback_gated_pull
  first_direction: push
  pull_before_push: forbidden
  automatic_pull: false
  activation_requires: [first_false_evaluation, interest_push_pull_eligible, continued_reciprocal_engagement, comfortable, no_boundary_or_discomfort_signal]
  pull_release_gate: positive_reciprocal_comfortable_feedback
  blocked_by: [concern, low_response, discomfort, refusal, stop_boundary]
initial_false_evaluation_status: push_required | awaiting_eligibility | awaiting_feedback | pull_ready | blocked | not_applicable | unknown
planned_pull:
  prepare_with_push: true
  status_before_feedback: pending_feedback
  release_gate: positive_reciprocal_comfortable_feedback
  on_ambiguous_or_negative: cancel_auto_sequence_and_reassess
planned_pull_status: pending_feedback | ready | blocked | not_applicable
roller_coaster_goal: forbidden
exception_route: clarify | concern | condition | pause | low_response | direct_window | invite | topic_stop | overall_stop | unknown
recovery_gate: none | can_return_blue | blocked_by_stop_boundary
recovery_reason: low_response | repeated_mismatch | operator_depletion | explicit_stop_followup | null
phrase_retrieval: enabled | disabled
recontact_permitted: true | false | unknown
reentry_evidence_required: true
```

路由结果应同时保留 `task_route` 和 `state_route`，避免把“用户要生成回复”误写成“当前一定适合推拉”。`recovery` 路由固定将 `phrase_retrieval` 设为 `disabled`；`stop_boundary` 固定覆盖所有战术和自动重启。

明确拒绝、删除或整体停止后，`recontact_permitted` 必须为 `false`；回蓝结束后也必须凭新的自愿、可观察互动证据重新判断，不按固定等待天数自动重启。
