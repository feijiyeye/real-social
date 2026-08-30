#!/usr/bin/env python3
"""Route a real-social request through the compact runtime route index."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
ROUTE_INDEX = SKILL_ROOT / "runtime" / "route-index.json"
NAVIGATION_INDEX = SKILL_ROOT / "runtime" / "navigation-index.json"

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


def route_request(
    text: str,
    task_route: str | None = None,
    state_route: str | None = None,
    risk: list[str] | None = None,
    stage: str | None = None,
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
) -> dict[str, Any]:
    index = load_json(ROUTE_INDEX)
    task_routes = [item for item in index.get("task_routes", []) if isinstance(item, dict)]
    state_routes = [item for item in index.get("state_routes", []) if isinstance(item, dict)]
    risk = risk or []
    task, task_hits = route_by_task(text, task_routes, task_route, str(index.get("default_task_route", "analyze_chat")))
    state, state_hits = route_by_state(text, state_routes, state_route, risk, str(index.get("default_state_route", "unknown_stage")))

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
    phrase_policy = str(state.get("phrase_retrieval", "enabled_after_context_review"))
    # Stage navigation precedes any sendable example.  Case lookup may still
    # read candidate case metadata, while phrase retrieval stays gated until a
    # reply request has both a usable stage and a direction.
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
    example_gate = {
        "stage_clear": state_id != "unknown_stage",
        "direction_clear": direction_clear,
        "explicit_sendable_request": task_id == "reply_request",
        "boundaries_satisfied": boundaries_satisfied,
        "allowed": bool(
            state_id != "unknown_stage"
            and direction_clear
            and task_id == "reply_request"
            and boundaries_satisfied
            and phrase_policy == "enabled_after_context_review"
        ),
    }

    return {
        "schema_version": 1,
        "package_id": "real-social",
        "input": {
            "text": text,
            "stage": stage,
            "direction": direction,
            "risk": risk,
            "affect": affect,
            "engagement": engagement,
            "intent_alignment": intent_alignment,
            "comfort": comfort,
            "false_evaluation_stage": false_evaluation_stage,
            "previous_direction": previous_direction,
            "post_push_feedback": post_push_feedback,
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
        "stage_navigation": stage_navigation,
        "example_gate": example_gate,
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
            "example_gate": example_gate,
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
    args = parser.parse_args()
    result = route_request(
        args.text,
        task_route=args.task_route,
        state_route=args.state_route,
        risk=args.risk,
        stage=args.stage,
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
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
