#!/usr/bin/env python3
"""Route a real-social request through the compact runtime route index."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
ROUTE_INDEX = SKILL_ROOT / "runtime" / "route-index.json"
NAVIGATION_INDEX = SKILL_ROOT / "runtime" / "navigation-index.json"

SESSION_SCHEMA_VERSION = 1
MAX_SESSION_TURNS = 12
SUMMARY_COMPACT_BATCH = 6

GROUNDING_REQUIRED_TASKS = {
    "analyze_chat",
    "reply_request",
    "case_lookup",
    "source_audit",
    "ingest_material",
    "architecture_maintenance",
}

RISK_ROUTE_ALIASES = {
    "stop": "stop_boundary",
    "refusal": "stop_boundary",
    "explicit_refusal": "stop_boundary",
    "deletion": "stop_boundary",
    "block": "stop_boundary",
    "blocked": "stop_boundary",
    "blacklist": "stop_boundary",
    "拉黑": "stop_boundary",
    "屏蔽": "stop_boundary",
    "stop_boundary": "stop_boundary",
    "privacy": "privacy_safety_age_consent",
    "safety": "privacy_safety_age_consent",
    "age": "privacy_safety_age_consent",
    "identity": "privacy_safety_age_consent",
    "consent": "privacy_safety_age_consent",
    "privacy_safety_age_consent": "privacy_safety_age_consent",
    "recovery": "recovery",
    "reengagement": "recovery",
    "operator_depletion": "recovery",
    "clarify": "clarify",
    "accountability": "clarify",
    "apology": "clarify",
    "low_response": "low_response",
    "concern": "concern_condition",
    "condition": "concern_condition",
    "invite": "invite",
    "direct_window": "invite",
    "interest": "interest_push_pull",
    "push": "interest_push_pull",
    "pull": "interest_push_pull",
    "interest_push_pull": "interest_push_pull",
}

ONE_CHAR_TERMS = {"推", "拉"}
NEGATION_PREFIXES = ("没有", "没", "未", "不要", "别", "不", "并未", "尚未")
NEGATED_STATEMENT_SUFFIXES = (
    "不是",
    "并非",
    "并不是",
    "不只是",
    "没有说",
    "没说",
    "并没有说",
    "并未说",
    "未说",
    "没有说过",
    "没说过",
    "没有表示",
    "没表示",
    "并没有表示",
    "没有明确说",
    "没明确说",
    "并没有明确说",
)
NEUTRAL_AFFECT_MARKERS = (
    "没有情绪",
    "没什么情绪",
    "情绪平淡",
    "语气平淡",
    "情绪很平",
)
NEGATIVE_AFFECT_MARKERS = (
    "情绪变差",
    "情绪很差",
    "生气",
    "反感",
    "不高兴",
    "被冒犯",
)
EXPRESSIVE_AFFECT_MARKERS = (
    "很兴奋",
    "很开心",
    "主动调情",
    "情绪明显",
    "情绪很足",
)
LOW_ENGAGEMENT_MARKERS = (
    "连续低回应",
    "多轮低回应",
    "没有主动延展",
    "没主动延展",
    "连续几轮只回",
    "只回嗯",
    "回复持续变少",
)
RECIPROCAL_ENGAGEMENT_MARKERS = (
    "主动提问",
    "仍主动提问",
    "仍然主动提问",
    "继续主动提问",
    "主动延展",
    "持续回复",
    "仍然回复",
    "继续接梗",
    "主动接梗",
    "双方仍主动",
)
FRIEND_ONLY_MARKERS = (
    "只想做朋友",
    "只愿意做朋友",
    "只做朋友",
    "不考虑恋爱",
    "没有恋爱意向",
    "不想谈恋爱",
    "朋友就好",
)
INTENT_DRIFT_MARKERS = (
    "偏成朋友",
    "聊成朋友",
    "变成朋友",
    "普通朋友话题",
    "朋友框架",
    "回归男女",
    "回到男女",
    "回到恋爱",
)
COMFORTABLE_MARKERS = (
    "很舒服",
    "感觉舒服",
    "看起来舒服",
    "互动舒服",
    "很自然",
    "很轻松",
)
UNCOMFORTABLE_MARKERS = (
    "不舒服",
    "不自在",
    "被冒犯",
    "反感",
    "有压力",
)
FIRST_FALSE_EVALUATION_MARKERS = (
    "首次假评",
    "第一次假评",
    "最开始假评",
    "还没假评过",
    "尚未假评过",
)
LATER_FALSE_EVALUATION_MARKERS = (
    "不是第一次假评",
    "已经假评过",
    "之前假评过",
    "后续假评",
    "再次假评",
)

FLOW_STEPS = (
    ("opening", "打开", "吸引力"),
    ("premise", "前提", "吸引力"),
    ("false_evaluation", "假性评估", "吸引力"),
    ("true_evaluation", "真性评估", "联系感"),
    ("self_narrative", "自我叙事", "联系感"),
    ("shared_narrative", "共同叙事", "联系感"),
    ("girlfriend", "女朋友", "延续性"),
    ("stage_close", "阶段收尾", "延续性"),
    ("game_rules", "游戏规则", "延续性"),
)
STAGE_ALIASES = {
    alias: stage_id
    for stage_id, label, _ in FLOW_STEPS
    for alias in (stage_id, label, label.replace("性", "性"))
}
STAGE_ALIASES.update({"假评": "false_evaluation", "真评": "true_evaluation"})


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"runtime index not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid runtime index: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"runtime index must be an object: {path}")
    return data


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def occurrence_is_negated(normalized: str, start: int) -> bool:
    prefix = normalized[max(0, start - 12) : start]
    for separator in "，。！？；,.!?;：:":
        prefix = prefix.rsplit(separator, 1)[-1]
    return any(prefix.endswith(marker) for marker in NEGATION_PREFIXES) or any(
        prefix.endswith(marker) for marker in NEGATED_STATEMENT_SUFFIXES
    )


def contains_unnegated(normalized: str, marker: str) -> bool:
    marker_norm = normalize(marker)
    start = normalized.find(marker_norm)
    while start >= 0:
        if not occurrence_is_negated(normalized, start):
            return True
        start = normalized.find(marker_norm, start + 1)
    return False


def contains_any_unnegated(normalized: str, markers: tuple[str, ...]) -> bool:
    return any(contains_unnegated(normalized, marker) for marker in markers)


def infer_evidence_dimensions(
    text: str,
    affect: str | None,
    engagement: str | None,
    intent_alignment: str | None,
    comfort: str | None,
    false_evaluation_stage: str | None,
) -> tuple[str, str, str, str, str]:
    """Infer compact evidence hints without replacing context review."""
    normalized = normalize(text)
    affect_value = affect or "unknown"
    engagement_value = engagement or "unknown"
    intent_value = intent_alignment or "unknown"
    comfort_value = comfort or "unknown"
    false_evaluation_value = false_evaluation_stage or "unknown"

    if affect_value == "unknown":
        if contains_any_unnegated(normalized, NEGATIVE_AFFECT_MARKERS):
            affect_value = "negative"
        elif contains_any_unnegated(normalized, EXPRESSIVE_AFFECT_MARKERS):
            affect_value = "expressive"
        elif contains_any_unnegated(normalized, NEUTRAL_AFFECT_MARKERS):
            affect_value = "neutral"

    low_engagement = contains_any_unnegated(normalized, LOW_ENGAGEMENT_MARKERS)
    reciprocal_engagement = contains_any_unnegated(
        normalized, RECIPROCAL_ENGAGEMENT_MARKERS
    )
    if engagement_value == "unknown":
        if low_engagement and not reciprocal_engagement:
            engagement_value = "low"
        elif reciprocal_engagement and not low_engagement:
            engagement_value = "reciprocal"

    if intent_value == "unknown" and contains_any_unnegated(
        normalized, FRIEND_ONLY_MARKERS
    ):
        intent_value = "friend_only_boundary"
    elif intent_value == "unknown" and contains_any_unnegated(
        normalized, INTENT_DRIFT_MARKERS
    ):
        intent_value = "drifted"
    elif intent_value == "unknown" and contains_any_unnegated(
        normalized, ("男女意图", "恋爱对象", "恋爱方向")
    ):
        intent_value = "aligned"

    if comfort_value == "unknown":
        if contains_any_unnegated(normalized, UNCOMFORTABLE_MARKERS):
            comfort_value = "uncomfortable"
        elif contains_any_unnegated(normalized, COMFORTABLE_MARKERS):
            comfort_value = "comfortable"

    if false_evaluation_value == "unknown":
        if contains_any_unnegated(normalized, LATER_FALSE_EVALUATION_MARKERS):
            false_evaluation_value = "later"
        elif contains_any_unnegated(normalized, FIRST_FALSE_EVALUATION_MARKERS):
            false_evaluation_value = "first"
    return (
        affect_value,
        engagement_value,
        intent_value,
        comfort_value,
        false_evaluation_value,
    )


def match_terms(text: str, terms: list[str]) -> list[str]:
    normalized = normalize(text)
    hits: list[str] = []
    for term in terms:
        term_norm = normalize(term)
        if not term_norm:
            continue
        if term_norm in ONE_CHAR_TERMS:
            # A lone character is too ambiguous for routing (for example,
            # "拉黑").  Accept it only in an explicit push/pull context.
            explicit_context = normalized in ONE_CHAR_TERMS or any(
                marker in normalized
                for marker in ("推拉", "推还是拉", "拉还是推", "选择推", "选择拉", "推方向", "拉方向", "push", "pull")
            )
            if not explicit_context:
                continue
        if contains_unnegated(normalized, term_norm):
            hits.append(term)
    return hits


def route_by_task(text: str, routes: list[dict[str, Any]], explicit: str | None, default: str) -> tuple[dict[str, Any], list[str]]:
    if explicit:
        for route in routes:
            if route.get("id") == explicit:
                return route, ["explicit_task_route"]
        raise SystemExit(f"unknown task route: {explicit}")

    scored: list[tuple[int, int, dict[str, Any], list[str]]] = []
    for route in routes:
        terms = [str(item) for item in route.get("match_any", [])]
        hits = match_terms(text, terms)
        if hits:
            # Longer terms win ties so "直接帮我回复" beats the generic
            # "回复"-style route if a future config adds one.
            score = sum(len(normalize(item)) for item in hits)
            scored.append((score, len(hits), route, hits))
    if scored:
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, route, hits = scored[0]
        return route, hits
    for route in routes:
        if route.get("id") == default:
            return route, ["default_task_route"]
    return {"id": default, "label": default}, ["fallback_task_route"]


def route_by_state(
    text: str,
    routes: list[dict[str, Any]],
    explicit: str | None,
    risk: list[str],
    default: str,
) -> tuple[dict[str, Any], list[str]]:
    route_by_id = {str(route.get("id")): route for route in routes}
    explicit_obj = route_by_id.get(explicit) if explicit else None
    if explicit and explicit_obj is None:
        raise SystemExit(f"unknown state route: {explicit}")

    risk_route_ids = {
        RISK_ROUTE_ALIASES.get(normalize(item), "")
        for item in risk
        if RISK_ROUTE_ALIASES.get(normalize(item), "")
    }
    risk_text = " ".join(risk) + " " + " ".join(risk_route_ids)
    candidates: list[tuple[int, int, dict[str, Any], list[str]]] = []
    for route in routes:
        terms = [str(item) for item in route.get("match_any", [])]
        hits = match_terms(text + " " + risk_text, terms)
        if hits:
            priority = int(route.get("priority", 0))
            candidates.append((priority, sum(len(normalize(item)) for item in hits), route, hits))

    # Structured risk labels are hard signals even when their human-language
    # match terms do not occur in the input text.
    for route_id in risk_route_ids:
        route = route_by_id.get(route_id)
        if route is not None:
            candidates.append((int(route.get("priority", 0)), 1000, route, [f"risk:{route_id}"]))

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    detected = candidates[0] if candidates else None
    if detected:
        detected_priority, _, detected_route, detected_hits = detected
        if explicit_obj is not None and int(explicit_obj.get("priority", 0)) > detected_priority:
            return explicit_obj, ["explicit_state_route"]
        if explicit_obj is not None and int(explicit_obj.get("priority", 0)) == detected_priority:
            return explicit_obj, ["explicit_state_route"] + detected_hits
        return detected_route, detected_hits
    if explicit_obj is not None:
        return explicit_obj, ["explicit_state_route"]
    for route in routes:
        if route.get("id") == default:
            return route, ["default_state_route"]
    return {"id": default, "label": default, "priority": 0}, ["fallback_state_route"]


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def normalize_flow_stage(value: str | None) -> str | None:
    if not value:
        return None
    return STAGE_ALIASES.get(normalize(value))


def resolve_flow_stage(model_stage: str | None, user_stage: str | None) -> dict[str, Any]:
    model = normalize_flow_stage(model_stage)
    user = normalize_flow_stage(user_stage)
    step_ids = [item[0] for item in FLOW_STEPS]
    labels = [item[1] for item in FLOW_STEPS]
    if model and user and model != user:
        status, current = "conflicted", None
    elif model:
        status, current = ("confirmed" if user == model else "model_assessed"), model
    elif user:
        status, current = "user_reported", user
    else:
        status, current = "unresolved", None
    position = step_ids.index(current) if current in step_ids else None
    return {
        "status": status,
        "model_assessed_stage": model,
        "user_reported_stage": user,
        "current_stage": current,
        "current_label": labels[position] if position is not None else None,
        "previous_stage": step_ids[position - 1] if position is not None and position > 0 else None,
        "next_stage": step_ids[position + 1] if position is not None and position + 1 < len(step_ids) else None,
        "ask_user": None if current else "我暂时无法从聊天中确认当前步骤。九个步骤是：打开、前提、假性评估、真性评估、自我叙事、共同叙事、女朋友、阶段收尾、游戏规则。你觉得现在处于哪一步？",
        "steps": [
            {"id": stage_id, "label": label, "phase": phase}
            for stage_id, label, phase in FLOW_STEPS
        ],
    }


def counter_status(name: str, count: int | None, pace: str) -> dict[str, Any]:
    if count is not None and count < 0:
        raise SystemExit("counter values must be non-negative")
    if name == "qualification":
        minimum, cautious_target, next_stage = 5, 6, "true_evaluation"
        label = "赋格"
    else:
        minimum, cautious_target, next_stage = 4, 5, "self_narrative"
        label = "女方真性评估"
    target = cautious_target if pace == "cautious" else minimum
    if count is None:
        status, recommendation = "unknown", "先从可观察聊天证据中去重计数"
    elif count >= target:
        status = "above_reference" if count > cautious_target else "minimum_met"
        recommendation = f"已达到{pace}节奏参考线，可以建议进入 {next_stage}；无需为刷数量继续停留"
    elif pace == "aggressive":
        status = "below_default_minimum"
        recommendation = f"尚未达到默认下限 {minimum}，但用户选择激进节奏，可在明确提示风险后提前建议进入 {next_stage}"
    else:
        status = "below_minimum"
        recommendation = f"目前 {count} 条，建议继续积累；{pace}节奏参考线为 {target}"
    return {
        "name": name,
        "label": label,
        "count": count,
        "reference_band": [minimum, cautious_target],
        "default_minimum": minimum,
        "effective_target": target,
        "status": status,
        "recommendation": recommendation,
        "counts_as": "去重后的独立可观察证据；不是消息条数",
        "proves": "仅支持转段建议，不证明兴趣、同意或成功",
    }


def resolve_narrative_purpose(stage: str | None, purpose: str | None) -> dict[str, Any]:
    if stage != "self_narrative":
        return {"status": "not_applicable", "purpose": None, "ask_user": None}
    labels = {
        "value_display": "展示自己的真实价值",
        "logistics_negotiation": "商量双方见面的时间与地点（物流）",
    }
    if purpose in labels:
        return {
            "status": "selected",
            "purpose": purpose,
            "label": labels[purpose],
            "ask_user": None,
            "logistics_check": "核对双方见面意愿、可用时间、地点、方便和安全；讨论不等于达成共识"
            if purpose == "logistics_negotiation" else None,
        }
    return {
        "status": "unclear",
        "purpose": None,
        "ask_user": "这轮自我叙事你想用于展示自己的真实价值，还是商量双方见面的时间和地点（物流）？",
    }


def navigation_hint(previous_route: str | None, outcome: str | None) -> dict[str, Any] | None:
    if not previous_route or not NAVIGATION_INDEX.is_file():
        return None
    data = load_json(NAVIGATION_INDEX)
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        return None
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("from") != previous_route:
            continue
        when = str(rule.get("when", ""))
        if outcome and outcome not in when and outcome not in {str(rule.get("next", "")), "*"}:
            continue
        return {key: rule[key] for key in ("from", "when", "next", "reason") if key in rule}
    return None


def _session_counter_value(state: dict[str, Any], key: str) -> int | None:
    """Read a counter from either the public or the compact session shape."""
    candidates = [
        state.get("counters"),
        state.get("conversation_ledger", {}).get("counters")
        if isinstance(state.get("conversation_ledger"), dict)
        else None,
    ]
    for counters in candidates:
        if not isinstance(counters, dict):
            continue
        value = counters.get(key)
        if isinstance(value, dict):
            value = value.get("count")
        if isinstance(value, int) and value >= 0:
            return value
    return None


def normalize_session_state(value: Any) -> dict[str, Any] | None:
    """Accept the returned session object on the next turn without trusting extra fields."""
    if not isinstance(value, dict):
        return None
    session = value.get("conversation_session") if isinstance(value.get("conversation_session"), dict) else value
    ledger = value.get("conversation_ledger") if isinstance(value.get("conversation_ledger"), dict) else {}
    if not isinstance(session, dict):
        return None
    turns = ledger.get("turns", value.get("turns", []))
    if not isinstance(turns, list):
        turns = []
    summary = ledger.get("conversation_summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return {
        "schema_version": SESSION_SCHEMA_VERSION,
        "conversation_session": {
            "session_id": str(session.get("session_id") or ""),
            "status": str(session.get("status") or "active"),
            "subject_key": str(session.get("subject_key") or "") or None,
            "turn_index": int(session.get("turn_index") or 0),
            "continuity_confidence": str(session.get("continuity_confidence") or "unknown"),
            "last_evidence_id": str(session.get("last_evidence_id") or "") or None,
        },
        "conversation_ledger": {
            "turns": [item for item in turns[-MAX_SESSION_TURNS:] if isinstance(item, dict)],
            "conversation_summary": {
                "covered_turn_start": summary.get("covered_turn_start"),
                "covered_turn_end": summary.get("covered_turn_end"),
                "turn_count": int(summary.get("turn_count") or 0),
                "evidence_refs": [str(item) for item in summary.get("evidence_refs", []) if item][:120],
                "stage_path": [item for item in summary.get("stage_path", []) if isinstance(item, dict)][-24:],
                "direction_feedback": [item for item in summary.get("direction_feedback", []) if isinstance(item, dict)][-24:],
            },
            "current_stage": ledger.get("current_stage"),
            "counters": ledger.get("counters", {}),
            "last_direction": ledger.get("last_direction"),
            "last_feedback": ledger.get("last_feedback"),
            "unresolved_questions": ledger.get("unresolved_questions", []),
        },
    }


def compact_turns(summary: dict[str, Any], turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold old turn metadata into a bounded, evidence-referenced summary."""
    result = {
        "covered_turn_start": summary.get("covered_turn_start"),
        "covered_turn_end": summary.get("covered_turn_end"),
        "turn_count": int(summary.get("turn_count") or 0),
        "evidence_refs": list(summary.get("evidence_refs", [])),
        "stage_path": list(summary.get("stage_path", [])),
        "direction_feedback": list(summary.get("direction_feedback", [])),
    }
    for turn in turns:
        index = turn.get("turn_index")
        if not isinstance(index, int):
            continue
        result["covered_turn_start"] = index if result["covered_turn_start"] is None else min(result["covered_turn_start"], index)
        result["covered_turn_end"] = index if result["covered_turn_end"] is None else max(result["covered_turn_end"], index)
        result["turn_count"] += 1
        evidence_id = turn.get("evidence_id")
        if evidence_id and evidence_id not in result["evidence_refs"]:
            result["evidence_refs"].append(evidence_id)
        stage = turn.get("stage")
        stage_value = stage.get("current_stage") if isinstance(stage, dict) else stage
        if stage_value:
            previous_stage = result["stage_path"][-1]["stage"] if result["stage_path"] else None
            if previous_stage != stage_value:
                result["stage_path"].append({"turn_index": index, "stage": stage_value})
        direction = turn.get("direction")
        feedback = turn.get("feedback")
        if direction or feedback:
            result["direction_feedback"].append({
                "turn_index": index,
                "direction": direction,
                "feedback": feedback,
            })
    result["evidence_refs"] = result["evidence_refs"][-120:]
    result["stage_path"] = result["stage_path"][-24:]
    result["direction_feedback"] = result["direction_feedback"][-24:]
    return result


def _required_knowledge_reads(reads: list[str]) -> list[str]:
    return [
        path for path in reads
        if path.startswith("knowledge/") and not path.endswith("/")
    ]


def _path_covered(required_path: str, consulted_paths: set[str], consulted_units: set[str]) -> bool:
    if required_path in consulted_paths:
        return True
    return any(unit_id and unit_id in required_path for unit_id in consulted_units)


def build_knowledge_grounding(
    task_id: str,
    state_id: str,
    required_reads: list[str],
    knowledge_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    """Require a fresh, inspectable knowledge receipt before substantive output."""
    required = task_id in GROUNDING_REQUIRED_TASKS or state_id != "unknown_stage"
    required_knowledge_reads = _required_knowledge_reads(required_reads)
    trace = knowledge_trace if isinstance(knowledge_trace, dict) else {}
    consulted_paths = {
        str(item) for item in trace.get("consulted_paths", [])
        if isinstance(item, str)
    }
    consulted_units = {
        str(item) for item in trace.get("consulted_units", [])
        if isinstance(item, str)
    }
    claims_used = [str(item) for item in trace.get("claims_used", []) if item]
    model_inference = [str(item) for item in trace.get("model_inference", []) if item]
    covered_reads = [
        path for path in required_knowledge_reads
        if _path_covered(path, consulted_paths, consulted_units)
    ]
    missing_reads = [path for path in required_knowledge_reads if path not in covered_reads]
    if not required:
        status = "not_required"
        permission = "allowed"
    elif not knowledge_trace:
        status = "not_provided"
        permission = "blocked_until_knowledge_trace"
    elif trace.get("retrieval_status") in {"failed", "blocked", "no_hit"}:
        status = str(trace.get("retrieval_status"))
        permission = "blocked_until_grounded"
    elif missing_reads or not claims_used:
        status = "insufficient"
        permission = "blocked_until_grounded"
    else:
        status = "grounded"
        permission = "allowed_after_grounding"
    source_refs = sorted(consulted_paths or set(covered_reads))
    return {
        "policy": "required" if required else "optional",
        "retrieval_status": status,
        "answer_permission": permission,
        "fresh_retrieval_required": required,
        "ai_only_answer_forbidden": required,
        "citation_required": required,
        "required_reads": required_knowledge_reads,
        "covered_reads": covered_reads,
        "missing_reads": missing_reads,
        "consulted_units": sorted(consulted_units),
        "source_refs": source_refs,
        "claims_used": claims_used,
        "model_inference": model_inference,
        "no_hit_reason": trace.get("no_hit_reason"),
        "instruction": (
            "先读取并核对 required_reads，再输出阶段与方向；将知识库依据和模型推断分开。"
            if required else "当前任务不要求推进性知识检索。"
        ),
    }


def build_session_state(
    prior: dict[str, Any] | None,
    *,
    session_id: str | None,
    subject_key: str | None,
    evidence_id: str | None,
    input_kind: str,
    text: str,
    main_flow: dict[str, Any],
    counters: dict[str, Any],
    effective_direction: str | None,
    requested_direction: str | None,
    post_push_feedback: str | None,
    continuity: str | None,
    reset_session: bool,
    knowledge_grounding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    prior_session = prior.get("conversation_session", {}) if prior else {}
    prior_ledger = prior.get("conversation_ledger", {}) if prior else {}
    prior_id = str(prior_session.get("session_id") or "")
    prior_subject = prior_session.get("subject_key")
    subject_conflict = bool(not reset_session and subject_key and prior_subject and subject_key != prior_subject)
    is_continuous = bool(prior and not reset_session and not subject_conflict and prior_session.get("status") != "reset")
    sid = session_id or (prior_id if is_continuous or subject_conflict else f"window-{uuid.uuid4().hex[:10]}")
    turn_index = int(prior_session.get("turn_index") or 0) + 1 if is_continuous else 1
    status = "ambiguous_subject" if subject_conflict else ("continuous" if is_continuous else ("reset" if reset_session else "new"))
    confidence = "low" if subject_conflict else (continuity or ("high" if is_continuous else "unknown"))
    current_evidence_id = evidence_id or f"turn-{turn_index}"
    previous_stage = prior_ledger.get("current_stage")
    previous_direction = prior_ledger.get("last_direction")
    previous_feedback = prior_ledger.get("last_feedback")
    compact_text = re.sub(r"\s+", " ", text).strip()
    if len(compact_text) > 500:
        compact_text = compact_text[:497] + "..."
    previous_stage_label = (
        previous_stage.get("current_stage") or previous_stage.get("model_assessed_stage")
        if isinstance(previous_stage, dict)
        else previous_stage
    )
    turns = list(prior_ledger.get("turns", [])) if is_continuous and isinstance(prior_ledger.get("turns"), list) else []
    summary = dict(prior_ledger.get("conversation_summary", {})) if is_continuous and isinstance(prior_ledger.get("conversation_summary"), dict) else {}
    compacted_turns: list[dict[str, Any]] = []
    if len(turns) >= MAX_SESSION_TURNS:
        compacted_turns = [item for item in turns[:SUMMARY_COMPACT_BATCH] if isinstance(item, dict)]
        turns = turns[SUMMARY_COMPACT_BATCH:]
        summary = compact_turns(summary, compacted_turns)
    turns.append({
        "turn_index": turn_index,
        "evidence_id": current_evidence_id,
        "input_kind": input_kind,
        "text_excerpt": compact_text,
        "stage": {
            "current_stage": main_flow.get("current_stage"),
            "model_assessed_stage": main_flow.get("model_assessed_stage"),
            "user_reported_stage": main_flow.get("user_reported_stage"),
        },
        "counter_snapshot": {
            "qualification": counters["qualification"].get("count"),
            "female_true_evaluation": counters["female_true_evaluation"].get("count"),
        },
        "direction": effective_direction or requested_direction,
        "feedback": post_push_feedback,
        "knowledge_status": knowledge_grounding.get("retrieval_status"),
        "knowledge_refs": knowledge_grounding.get("covered_reads", []),
    })
    turns = turns[-MAX_SESSION_TURNS:]
    next_direction = effective_direction or requested_direction or previous_direction
    next_state = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "conversation_session": {
            "session_id": sid,
            "status": "active" if status != "ambiguous_subject" else "ambiguous",
            "subject_key": subject_key or prior_subject,
            "turn_index": turn_index,
            "continuity_confidence": confidence,
            "last_evidence_id": current_evidence_id,
        },
        "conversation_ledger": {
            "turns": turns,
            "conversation_summary": summary,
            "current_stage": main_flow.get("current_stage"),
            "counters": counters,
            "last_direction": next_direction,
            "last_feedback": post_push_feedback,
            "last_knowledge_grounding": {
                "retrieval_status": knowledge_grounding.get("retrieval_status"),
                "covered_reads": knowledge_grounding.get("covered_reads", []),
                "claims_used": knowledge_grounding.get("claims_used", []),
            },
            "unresolved_questions": [],
        },
    }
    continuity_block = {
        "status": status,
        "title": "本窗口状态",
        "turn_label": f"第 {turn_index} 轮，{'已连续关联' if is_continuous else ('需要确认聊天对象' if subject_conflict else '新窗口')}" ,
        "previous_assessment": previous_stage_label or "暂无上一轮判断",
        "new_evidence": current_evidence_id,
        "previous_direction": previous_direction,
        "previous_feedback": previous_feedback,
        "current_stage": main_flow.get("current_stage"),
        "counters": {
            "qualification": counters["qualification"],
            "female_true_evaluation": counters["female_true_evaluation"],
        },
        "summary": {
            "covered_turn_start": summary.get("covered_turn_start"),
            "covered_turn_end": summary.get("covered_turn_end"),
            "turn_count": summary.get("turn_count", 0),
            "compacted_this_turn": bool(compacted_turns),
            "recent_detail_start": turns[0].get("turn_index") if turns else None,
            "recent_detail_end": turns[-1].get("turn_index") if turns else None,
        },
        "continuity_confidence": confidence,
        "reset_hint": "如需开始新的聊天对象，请传入 reset_session 或明确说‘新开一段聊天’。",
    }
    return next_state, continuity_block


def route_request(
    text: str,
    task_route: str | None = None,
    state_route: str | None = None,
    risk: list[str] | None = None,
    stage: str | None = None,
    user_stage: str | None = None,
    qualification_count: int | None = None,
    female_true_evaluation_count: int | None = None,
    pace: str = "standard",
    narrative_purpose: str | None = None,
    direction: str | None = None,
    previous_route: str | None = None,
    outcome: str | None = None,
    affect: str | None = None,
    engagement: str | None = None,
    intent_alignment: str | None = None,
    comfort: str | None = None,
    false_evaluation_stage: str | None = None,
    previous_direction: str | None = None,
    post_push_feedback: str | None = None,
    session_state: dict[str, Any] | None = None,
    session_id: str | None = None,
    subject_key: str | None = None,
    evidence_id: str | None = None,
    input_kind: str = "text_or_image_context",
    continuity: str | None = None,
    reset_session: bool = False,
    knowledge_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = load_json(ROUTE_INDEX)
    task_routes = [item for item in index.get("task_routes", []) if isinstance(item, dict)]
    state_routes = [item for item in index.get("state_routes", []) if isinstance(item, dict)]
    risk = risk or []
    normalized_session = normalize_session_state(session_state)
    prior_ledger = normalized_session.get("conversation_ledger", {}) if normalized_session else {}
    if qualification_count is None and normalized_session:
        qualification_count = _session_counter_value(normalized_session, "qualification")
    if female_true_evaluation_count is None and normalized_session:
        female_true_evaluation_count = _session_counter_value(normalized_session, "female_true_evaluation")
    if previous_direction is None and isinstance(prior_ledger, dict):
        carried_direction = prior_ledger.get("last_direction")
        if carried_direction in {"push", "pull", "none"}:
            previous_direction = carried_direction
    task, task_hits = route_by_task(text, task_routes, task_route, str(index.get("default_task_route", "analyze_chat")))
    state, state_hits = route_by_state(text, state_routes, state_route, risk, str(index.get("default_state_route", "unknown_stage")))
    main_flow = resolve_flow_stage(stage, user_stage)
    narrative = resolve_narrative_purpose(main_flow["current_stage"], narrative_purpose)
    counters = {
        "qualification": counter_status("qualification", qualification_count, pace),
        "female_true_evaluation": counter_status(
            "female_true_evaluation", female_true_evaluation_count, pace
        ),
    }

    affect, engagement, intent_alignment, comfort, false_evaluation_stage = infer_evidence_dimensions(
        text,
        affect,
        engagement,
        intent_alignment,
        comfort,
        false_evaluation_stage,
    )
    if post_push_feedback == "discomfort":
        comfort = "uncomfortable"
    state_by_id = {str(item.get("id")): item for item in state_routes}
    structured_route_id: str | None = None
    if comfort == "uncomfortable":
        structured_route_id = "stop_boundary"
    elif intent_alignment == "friend_only_boundary":
        structured_route_id = "clarify"
    elif engagement == "low":
        structured_route_id = "low_response"
    elif previous_direction == "push":
        structured_route_id = "interest_push_pull"
    elif false_evaluation_stage == "first" and engagement == "reciprocal":
        structured_route_id = "interest_push_pull"
    elif engagement == "reciprocal" and (
        affect == "neutral" or intent_alignment == "drifted"
    ):
        structured_route_id = "interest_push_pull"
    if structured_route_id:
        structured_state = state_by_id.get(structured_route_id)
        if structured_state is not None and int(structured_state.get("priority", 0)) >= int(state.get("priority", 0)):
            state = structured_state
            state_hits = unique(state_hits + [f"structured:{structured_route_id}"])

    # Emotion-flat and topic-drift phrases are observations, not sufficient
    # permission to act.  Without reciprocal engagement, keep gathering evidence
    # unless the caller explicitly selected the interest route or a tactic.
    evidence_only_terms = set(NEUTRAL_AFFECT_MARKERS + INTENT_DRIFT_MARKERS)
    evidence_only_hits = bool(state_hits) and all(
        hit in evidence_only_terms for hit in state_hits
    )
    insufficient_drift_evidence = (
        intent_alignment == "drifted" and engagement != "reciprocal"
    )
    insufficient_flat_evidence = (
        affect == "neutral"
        and engagement != "reciprocal"
        and evidence_only_hits
    )
    if (
        state.get("id") == "interest_push_pull"
        and state_route is None
        and direction not in {"push", "pull"}
        and previous_direction != "push"
        and (insufficient_drift_evidence or insufficient_flat_evidence)
    ):
        state = state_by_id.get("unknown_stage", state)
        state_hits = unique(state_hits + ["structured:reciprocal_engagement_required"])

    state_id = str(state.get("id", "unknown_stage"))
    task_id = str(task.get("id", "analyze_chat"))
    primary = state_id if state_id != "unknown_stage" else task_id
    auxiliary: list[str] = []
    if state_id != "unknown_stage" and task_id != "analyze_chat":
        auxiliary.append(task_id)
    if task_id == "reply_request" and state_id == "unknown_stage":
        auxiliary.append("analyze_chat")
    auxiliary = unique(auxiliary)[:2]

    required_reads = unique(
        [str(item) for item in task.get("load", [])]
        + [str(item) for item in state.get("required_reads", [])]
    )
    deferred_reads = unique(
        [str(item) for item in task.get("defer", [])]
        + [str(item) for item in state.get("defer", [])]
    )
    knowledge_grounding = build_knowledge_grounding(
        task_id,
        state_id,
        required_reads,
        knowledge_trace,
    )
    phrase_policy = str(state.get("phrase_retrieval", "enabled_after_context_review"))
    # Stage navigation precedes any phrase-library lookup. Case lookup may
    # still read candidate case metadata, while phrase retrieval stays gated
    # until a reply request has both a usable stage and a direction.
    if task_id not in {"reply_request", "case_lookup"}:
        phrase_policy = "disabled_until_reply_request"
    elif task_id == "reply_request" and state_id == "unknown_stage":
        phrase_policy = "disabled_until_context"
    if state_id == "recovery":
        phrase_policy = "disabled"
    if state_id == "privacy_safety_age_consent":
        phrase_policy = "disabled_until_verified"
    if state_id == "stop_boundary":
        phrase_policy = "boundary_only"
    if narrative["status"] == "unclear" and phrase_policy == "enabled_after_context_review":
        phrase_policy = "disabled_until_narrative_purpose"

    flags: list[str] = []
    if state_id == "stop_boundary":
        flags.append("stop_boundary_overrides_all_tactics")
    if state_id == "privacy_safety_age_consent":
        flags.append("verification_required_before_high_risk_retrieval")
    if state_id == "recovery":
        flags.append("recovery_notice_only")
    if state_id == "interest_push_pull":
        flags.append("directions_limited_to_push_or_pull")
        flags.append("tactical_explanation_apology_yielding_forbidden")
        flags.append("push_preferred_when_both_eligible_not_fixed_quota")
        if false_evaluation_stage == "first":
            flags.append("first_false_evaluation_push_before_pull")
            if direction == "pull" and previous_direction != "push":
                flags.append("first_false_evaluation_blocks_pull_first")
        if affect == "neutral" and engagement == "reciprocal":
            flags.append("flat_but_engaged_push_preferred")
        elif affect == "neutral":
            flags.append("neutral_affect_requires_reciprocal_engagement")
        if intent_alignment == "drifted" and engagement == "reciprocal":
            flags.append("romantic_intent_reanchor_without_fixed_turn_count")
    if intent_alignment == "friend_only_boundary":
        flags.append("friend_only_boundary_blocks_romantic_reanchor")
    if state_id == "unknown_stage":
        flags.append("evidence_or_context_insufficient")
    if main_flow["status"] == "unresolved":
        flags.append("nine_step_stage_requires_user_report")
    elif main_flow["status"] == "conflicted":
        flags.append("model_and_user_stage_conflict_requires_clarification")
    if narrative["status"] == "unclear":
        flags.append("self_narrative_purpose_required")

    recovery_gate = "none"
    recovery_reason = None
    recontact_permitted: bool | str = "unknown"
    if state_id == "recovery":
        recovery_gate = "can_return_blue"
        recovery_reason = "operator_depletion"
        recontact_permitted = False
    elif state_id == "stop_boundary":
        recovery_gate = "blocked_by_stop_boundary"
        recovery_reason = "explicit_stop_followup"
        recontact_permitted = False
    elif state_id == "low_response":
        recovery_reason = "low_response"
    elif state_id == "privacy_safety_age_consent":
        recontact_permitted = False

    romantic_reanchor_permitted: bool | str = "not_applicable"
    if intent_alignment == "friend_only_boundary":
        romantic_reanchor_permitted = False
    elif intent_alignment == "drifted":
        if state_id == "interest_push_pull" and engagement == "reciprocal":
            romantic_reanchor_permitted = True
        else:
            romantic_reanchor_permitted = "unknown"
    elif state_id in {
        "stop_boundary",
        "privacy_safety_age_consent",
        "recovery",
        "low_response",
    }:
        romantic_reanchor_permitted = False

    push_pull_logic = state.get("push_pull_logic") if state_id == "interest_push_pull" else None
    tactical_action_constraints = None
    romantic_intent_anchor = None
    affect_engagement_policy = None
    direction_bias = None
    initial_false_evaluation_order = None
    planned_pull = None
    if isinstance(push_pull_logic, dict):
        configured_constraints = push_pull_logic.get("tactical_action_constraints")
        if isinstance(configured_constraints, dict):
            tactical_action_constraints = configured_constraints
        romantic_intent_anchor = push_pull_logic.get("romantic_intent_anchor")
        affect_engagement_policy = push_pull_logic.get("affect_engagement_policy")
        direction_bias = push_pull_logic.get("direction_bias")
        initial_false_evaluation_order = push_pull_logic.get(
            "initial_false_evaluation_order"
        )
        planned_pull = push_pull_logic.get("planned_pull")

    direction_preference = "unknown"
    planned_pull_status = "not_applicable"
    initial_false_evaluation_status = "not_applicable"
    effective_direction: str | None = None
    if state_id == "interest_push_pull":
        direction_preference = "push_if_both_eligible"
        if false_evaluation_stage == "first":
            initial_false_evaluation_status = "awaiting_eligibility"
        elif false_evaluation_stage == "unknown":
            initial_false_evaluation_status = "unknown"
        if affect == "neutral":
            direction_preference = "push" if engagement == "reciprocal" else "none"
        if previous_direction == "push":
            effective_direction = None
            if post_push_feedback == "positive":
                if (
                    engagement == "reciprocal"
                    and comfort == "comfortable"
                    and affect != "negative"
                ):
                    direction_preference = "pull"
                    effective_direction = "pull"
                    planned_pull_status = "ready"
                    if false_evaluation_stage == "first":
                        initial_false_evaluation_status = "pull_ready"
                elif affect == "negative" or comfort == "uncomfortable":
                    direction_preference = "none"
                    planned_pull_status = "blocked"
                    if false_evaluation_stage == "first":
                        initial_false_evaluation_status = "blocked"
                else:
                    direction_preference = "none"
                    planned_pull_status = "pending_feedback"
                    if false_evaluation_stage == "first":
                        initial_false_evaluation_status = "awaiting_feedback"
            elif post_push_feedback in {"ambiguous", "negative", "discomfort"}:
                direction_preference = "none"
                planned_pull_status = "blocked"
                if false_evaluation_stage == "first":
                    initial_false_evaluation_status = "blocked"
            else:
                direction_preference = "none"
                planned_pull_status = "pending_feedback"
                if false_evaluation_stage == "first":
                    initial_false_evaluation_status = "awaiting_feedback"
        elif false_evaluation_stage == "first":
            direction_preference = "push"
            if (
                engagement == "reciprocal"
                and comfort == "comfortable"
                and affect != "negative"
            ):
                effective_direction = "push"
                planned_pull_status = "pending_feedback"
                initial_false_evaluation_status = "push_required"
            else:
                effective_direction = None
                initial_false_evaluation_status = "awaiting_eligibility"
        else:
            if direction in {"push", "pull"}:
                direction_preference = direction
                effective_direction = direction
            if direction == "push":
                planned_pull_status = "pending_feedback"

    stage_navigation = index.get("stage_navigation", {})
    if not isinstance(stage_navigation, dict):
        stage_navigation = {}
    direction_clear = state_id != "unknown_stage" and (
        (state_id != "interest_push_pull" and bool(state.get("exception_route")))
        or (state_id == "interest_push_pull" and effective_direction in {"push", "pull"})
    )
    boundaries_satisfied = state_id not in {
        "stop_boundary",
        "privacy_safety_age_consent",
        "recovery",
    }
    flow_stage_clear = main_flow["current_stage"] is not None
    if task_id == "reply_request" and not direction_clear and phrase_policy == "enabled_after_context_review":
        phrase_policy = "disabled_until_direction"

    phrase_library_gate = {
        "stage_clear": flow_stage_clear,
        "narrative_purpose_clear": narrative["status"] != "unclear",
        "direction_clear": direction_clear,
        "boundaries_satisfied": boundaries_satisfied,
        "allowed": bool(
            flow_stage_clear
            and narrative["status"] != "unclear"
            and direction_clear
            and boundaries_satisfied
            and phrase_policy == "enabled_after_context_review"
        ),
        "display_label": "话术库原句",
        "max_items": 2,
        "ai_composed_reply": False,
    }

    next_session_state, continuity_block = build_session_state(
        normalized_session,
        session_id=session_id,
        subject_key=subject_key,
        evidence_id=evidence_id,
        input_kind=input_kind,
        text=text,
        main_flow=main_flow,
        counters=counters,
        effective_direction=effective_direction,
        requested_direction=direction,
        post_push_feedback=post_push_feedback,
        continuity=continuity,
        reset_session=reset_session,
        knowledge_grounding=knowledge_grounding,
    )

    return {
        "schema_version": 1,
        "package_id": "real-social",
        "input": {
            "text": text,
            "stage": stage,
            "user_stage": user_stage,
            "qualification_count": qualification_count,
            "female_true_evaluation_count": female_true_evaluation_count,
            "pace": pace,
            "narrative_purpose": narrative_purpose,
            "direction": direction,
            "risk": risk,
            "affect": affect,
            "engagement": engagement,
            "intent_alignment": intent_alignment,
            "comfort": comfort,
            "false_evaluation_stage": false_evaluation_stage,
            "previous_direction": previous_direction,
            "post_push_feedback": post_push_feedback,
            "session_id": session_id,
            "subject_key": subject_key,
            "evidence_id": evidence_id,
            "input_kind": input_kind,
            "continuity": continuity,
            "reset_session": reset_session,
            "knowledge_trace": knowledge_trace,
        },
        "task_route": {
            "id": task_id,
            "label": task.get("label", task_id),
            "matched_terms": task_hits,
            "output_mode": task.get("output_mode"),
            "primary_units": task.get("primary_units", []),
        },
        "state_route": {
            "id": state_id,
            "label": state.get("label", state_id),
            "priority": state.get("priority", 0),
            "matched_terms": state_hits,
            "exception_route": state.get("exception_route"),
            "allowed_directions": state.get("allowed_directions", []),
            "push_pull_logic": push_pull_logic,
        },
        "primary_module": primary,
        "auxiliary_modules": auxiliary,
        "read_plan": {
            "required": required_reads,
            "deferred": deferred_reads,
            "phrase_retrieval": phrase_policy,
        },
        "knowledge_grounding": knowledge_grounding,
        "stage_navigation": stage_navigation,
        "main_flow": main_flow,
        "counters": counters,
        "continuity": continuity_block,
        "conversation_session": next_session_state["conversation_session"],
        "conversation_ledger": next_session_state["conversation_ledger"],
        "session_state": next_session_state,
        "narrative_purpose": narrative,
        "phrase_library_gate": phrase_library_gate,
        "safety_flags": flags,
        "runtime_fields": {
            "tactical_direction": effective_direction,
            "push_back_eligible": "unknown" if state_id == "interest_push_pull" else False,
            "post_push_check": "required" if state_id == "interest_push_pull" else "not_applicable",
            "pull_after_push": "preferred_if_positive_feedback" if state_id == "interest_push_pull" else "not_applicable",
            "push_purpose": "light_tension_and_feedback" if state_id == "interest_push_pull" else None,
            "tactical_concession_policy": "forbidden_in_push_pull" if state_id == "interest_push_pull" else "not_applicable",
            "accountability_exception_route": "exit_tactical_layer" if state_id == "interest_push_pull" else "not_applicable",
            "tactical_action_constraints": tactical_action_constraints if state_id == "interest_push_pull" else "not_applicable",
            "romantic_intent_anchor": romantic_intent_anchor if state_id == "interest_push_pull" else "not_applicable",
            "affect_engagement_policy": affect_engagement_policy if state_id == "interest_push_pull" else "not_applicable",
            "direction_bias": direction_bias if state_id == "interest_push_pull" else "not_applicable",
            "false_evaluation_stage": false_evaluation_stage,
            "initial_false_evaluation_order": initial_false_evaluation_order if state_id == "interest_push_pull" else "not_applicable",
            "initial_false_evaluation_status": initial_false_evaluation_status if state_id == "interest_push_pull" else "not_applicable",
            "planned_pull": planned_pull if state_id == "interest_push_pull" else "not_applicable",
            "intent_alignment": intent_alignment,
            "affect_state": affect,
            "engagement_state": engagement,
            "comfort_state": comfort,
            "flat_but_engaged": state_id == "interest_push_pull" and affect == "neutral" and engagement == "reciprocal",
            "romantic_reanchor_permitted": romantic_reanchor_permitted,
            "intent_boundary_reason": "friend_only_declared" if intent_alignment == "friend_only_boundary" else None,
            "direction_preference": direction_preference if state_id == "interest_push_pull" else "none",
            "planned_pull_status": planned_pull_status if state_id == "interest_push_pull" else "not_applicable",
            "roller_coaster_goal": "forbidden",
            "exception_route": state.get("exception_route"),
            "recovery_gate": recovery_gate,
            "recovery_reason": recovery_reason,
            "phrase_retrieval": phrase_policy,
            "recontact_permitted": recontact_permitted,
            "reentry_evidence_required": True,
            "stage_navigation": stage_navigation,
            "main_flow": main_flow,
            "counters": counters,
            "narrative_purpose": narrative,
            "pace": pace,
            "phrase_library_gate": phrase_library_gate,
        },
        "navigation_hint": navigation_hint(previous_route, outcome),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="", help="current user request or compact chat context")
    parser.add_argument("--task-route", default=None)
    parser.add_argument("--state-route", default=None)
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--stage", default=None)
    parser.add_argument("--user-stage", default=None)
    parser.add_argument("--qualification-count", type=int, default=None)
    parser.add_argument("--female-true-evaluation-count", type=int, default=None)
    parser.add_argument("--pace", choices=["standard", "aggressive", "cautious"], default="standard")
    parser.add_argument("--narrative-purpose", choices=["value_display", "logistics_negotiation"], default=None)
    parser.add_argument("--direction", default=None)
    parser.add_argument("--previous-route", default=None)
    parser.add_argument("--outcome", default=None)
    parser.add_argument("--affect", choices=["neutral", "expressive", "negative", "unknown"], default=None)
    parser.add_argument("--engagement", choices=["reciprocal", "low", "unknown"], default=None)
    parser.add_argument("--intent-alignment", choices=["aligned", "drifted", "friend_only_boundary", "unknown"], default=None)
    parser.add_argument("--comfort", choices=["comfortable", "uncertain", "uncomfortable", "unknown"], default=None)
    parser.add_argument("--false-evaluation-stage", choices=["first", "later", "not_applicable", "unknown"], default=None)
    parser.add_argument("--previous-direction", choices=["push", "pull", "none"], default=None)
    parser.add_argument("--post-push-feedback", choices=["positive", "ambiguous", "negative", "discomfort", "unknown"], default=None)
    parser.add_argument("--session-state-json", default=None, help="previous session_state JSON object")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--subject-key", default=None, help="stable label for the chat subject within this window")
    parser.add_argument("--evidence-id", default=None)
    parser.add_argument("--input-kind", choices=["text", "image", "text_or_image_context"], default="text_or_image_context")
    parser.add_argument("--continuity", choices=["high", "medium", "low", "unknown"], default=None)
    parser.add_argument("--reset-session", action="store_true")
    parser.add_argument("--knowledge-trace-json", default=None, help="current-turn knowledge retrieval receipt JSON")
    args = parser.parse_args()
    session_state = None
    if args.session_state_json:
        try:
            session_state = json.loads(args.session_state_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid --session-state-json: {exc}") from exc
    knowledge_trace = None
    if args.knowledge_trace_json:
        try:
            knowledge_trace = json.loads(args.knowledge_trace_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid --knowledge-trace-json: {exc}") from exc
    result = route_request(
        args.text,
        task_route=args.task_route,
        state_route=args.state_route,
        risk=args.risk,
        stage=args.stage,
        user_stage=args.user_stage,
        qualification_count=args.qualification_count,
        female_true_evaluation_count=args.female_true_evaluation_count,
        pace=args.pace,
        narrative_purpose=args.narrative_purpose,
        direction=args.direction,
        previous_route=args.previous_route,
        outcome=args.outcome,
        affect=args.affect,
        engagement=args.engagement,
        intent_alignment=args.intent_alignment,
        comfort=args.comfort,
        false_evaluation_stage=args.false_evaluation_stage,
        previous_direction=args.previous_direction,
        post_push_feedback=args.post_push_feedback,
        session_state=session_state,
        session_id=args.session_id,
        subject_key=args.subject_key,
        evidence_id=args.evidence_id,
        input_kind=args.input_kind,
        continuity=args.continuity,
        reset_session=args.reset_session,
        knowledge_trace=knowledge_trace,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
