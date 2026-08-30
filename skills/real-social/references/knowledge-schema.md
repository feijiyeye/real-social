# 知识单元格式

每条单元必须能回到原始素材的文件、页码、行号或时间戳。建议使用独立 Markdown 文件，并在开头放 YAML frontmatter。

```yaml
id: STG-001
type: stage # policy|stage|signal|rule|direction|case|boundary|viewpoint|conflict
title: "阶段名称"
status: candidate # candidate|canonical|superseded|rejected|conflict
canonical: false
version: 1
scope:
  relationship_context: []
  stage: ""
claim: "一条可检验的主张"
trigger_signals: []
disconfirming_signals: []
allowed_directions: []
forbidden_moves: []
case_refs: []
source_refs:
  - file: "来源文件"
    locator: "时间戳/页码/行号"
    quote: "必要的短引文"
authority: source_only # source_only|developer_approved
confidence: 0.0
conflicts_with: []
developer_decision: pending
chain_id: ""
chain_role: "node|candidate_branch|canonical_branch"
```

## 历史元数据兼容

迁移前已经存在的旧单元可能使用 `status: active` 并缺少 `type` 或 `version`。这类单元只能在 Dragon 知识库的 `04-系统/知识单元元数据兼容清单.json` 中逐条登记，并同时保留 `canonical: true`；校验器默认将其标为兼容警告，`--strict` 模式会将警告升级为错误。新建或新版本单元不得依赖该例外。

讲解型经典案例可增加以下字段：

```yaml
source_kind: narrated_classic_case
chapters: []
evidence_layers: [source_dialogue, source_interpretation, source_move, source_feedback, source_principle, source_outcome]
source_logic: []
source_operation_mappings: []
outcome_status: source_reported # source_reported|partially_shown|verified
callability: source_preserved # source_preserved|candidate_callable|boundary_only|not_default_direction
chain_refs: []
```

## 单元边界

- `stage` 描述状态，不描述一句具体话术。
- `signal` 只记录可观察或用户明确报告的信号。
- `rule` 写条件、判断和边界。
- `direction` 写意图和策略方向，不写默认可复制回复。
- `case` 必须包含上下文、阶段证据、使用方向、结果和限制，并完成脱敏。
- `case` 来自讲解稿时，保留讲解者的完整逻辑链；缺少原始聊天不阻断建单元，但必须标注 `source_kind`、证据层和结果状态。
- `stage` 和 `case` 可以记录 `chain_id` 或 `chain_refs`。阶段节点是可复用的状态，分链记录节点顺序和转移条件；不设唯一主链，相同节点合并、不同路径并存。
- `case` 的 `candidate_callable` 只允许作为标注清楚的相似案例参考召回，不允许把候选案例单独当作正式规则或价值观。
- `viewpoint` 记录来源方的看法、概括、经验判断或立场；必须注明表达者、依据、适用范围和未经证实之处，不能直接作为事实、价值观或规则。
- `conflict` 必须同时保留双方主张和来源，不能只保留“最新版本”。

## 运行时索引

`runtime/unit-index.json`、`runtime/route-index.json`、`runtime/navigation-index.json` 和 `runtime/phrase-route-index.json` 都是从本 Schema 和来源清单派生的检索索引，不是知识单元。索引可以增加 `route_ids`、包内路径和候选入口，但不得删除或改写原单元的 `status`、`canonical`、`authority`、`version` 或来源定位。路由命中只决定先读哪些文件，不能把 `candidate` 变成正式规则。
