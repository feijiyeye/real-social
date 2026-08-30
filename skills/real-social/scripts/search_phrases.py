#!/usr/bin/env python3
"""Search the routed phrase candidates without loading the full corpus by default."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
PHRASE_INDEX = SKILL_ROOT / "runtime" / "phrase-route-index.json"

STATE_ONLY_ROUTES = {
    "recovery": {
        "retrieval_status": "disabled",
        "reason": "\u56de\u84dd\u53ea\u8f93\u51fa\u72b6\u6001\u63d0\u793a\uff0c\u4e0d\u68c0\u7d22\u6216\u751f\u6210\u4efb\u4f55\u8bdd\u672f",
    },
    "privacy_safety_age_consent": {
        "retrieval_status": "disabled_until_verified",
        "reason": "\u9690\u79c1\u3001\u5b89\u5168\u3001\u6210\u5e74\u8eab\u4efd\u4e0e\u540c\u610f\u6761\u4ef6\u672a\u6838\u5b9e\u524d\u4e0d\u8fdb\u5165\u8bdd\u672f\u53ec\u56de",
    },
    "stop_boundary": {
        "retrieval_status": "boundary_only",
        "reason": "\u660e\u786e\u505c\u6b62\u3001\u62d2\u7edd\u6216\u5220\u9664\u65f6\u4e0d\u751f\u6210\u63a8\u8fdb\u8bdd\u672f",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"phrase route index not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"phrase index must be an object: {path}")
    return data


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def terms(text: str) -> set[str]:
    normalized = normalize(text)
    if not normalized:
        return set()
    result = {normalized}
    # Character n-grams work for Chinese without adding a tokenizer dependency.
    for size in (2, 3, 4):
        result.update(normalized[index : index + size] for index in range(len(normalized) - size + 1))
    return {item for item in result if item}


def score_entry(entry: dict[str, Any], query: str, section_terms: list[str], stage: str | None, direction: str | None) -> float:
    query_norm = normalize(query)
    text_norm = normalize(str(entry.get("text", entry.get("canonical_text", ""))))
    if not text_norm:
        return 0.0
    score = 0.0
    if query_norm and query_norm in text_norm:
        score += 100.0
    query_terms = terms(query)
    text_terms = terms(text_norm)
    score += min(40.0, 4.0 * len(query_terms & text_terms))
    sections = " ".join(str(item) for item in entry.get("sections", []))
    section_norm = normalize(sections)
    for hint in section_terms:
        hint_norm = normalize(hint)
        if hint_norm and (hint_norm in section_norm or hint_norm in text_norm):
            score += 5.0
    if stage and normalize(stage) in section_norm:
        score += 12.0
    if direction:
        direction_norm = normalize(direction)
        if direction_norm in text_norm or direction_norm in section_norm:
            score += 10.0
    # Prefer entries with a stable candidate key but do not use repetition as
    # evidence that a sentence is safe or effective.
    if entry.get("phrase_key"):
        score += 0.5
    return score


def allowed(entry: dict[str, Any], include_boundary: bool) -> tuple[bool, str | None]:
    callability = str(entry.get("callability", ""))
    if callability == "boundary_only" and not include_boundary:
        return False, "boundary_only"
    if callability in {"source_only_unreviewed", "source_preserved", "not_default_direction"}:
        return False, callability
    return True, None


def find_route(data: dict[str, Any], route_id: str) -> dict[str, Any]:
    for route in data.get("routes", []):
        if isinstance(route, dict) and route.get("id") == route_id:
            return route
    raise SystemExit(f"unknown phrase route: {route_id}")


def load_shard(route: dict[str, Any]) -> list[dict[str, Any]]:
    shard_value = route.get("shard")
    if isinstance(shard_value, str):
        path = SKILL_ROOT / shard_value
        if not path.is_file():
            raise SystemExit(f"phrase shard not found: {path}")
        data = load_json(path)
        entries = data.get("entries", [])
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        raise SystemExit(f"phrase shard entries must be a list: {path}")
    # Compatibility with pre-shard snapshots that have no shard declaration.
    entries = route.get("preferred_entries", [])
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


def load_full_entries(route: dict[str, Any]) -> list[dict[str, Any]]:
    full = route.get("full_index", {})
    path_value = full.get("path") if isinstance(full, dict) else None
    if not isinstance(path_value, str):
        raise SystemExit("phrase route has no full-index path")
    path = SKILL_ROOT / path_value
    if not path.is_file():
        raise SystemExit(f"full phrase index not found: {path}")
    document = load_json(path)
    entries = document.get("entries", [])
    if not isinstance(entries, list):
        raise SystemExit(f"full phrase index entries must be a list: {path}")
    return [entry for entry in entries if isinstance(entry, dict)]


def search(route_id: str, query: str, limit: int = 3, stage: str | None = None, direction: str | None = None, speaker: str | None = None, full_index: bool = False, include_boundary: bool = False, sexual_context: bool = False, explicit_same_topic: bool = False, age_identity_basis: bool = False, mutual_feedback: bool = False, no_refusal_or_discomfort: bool = False) -> dict[str, Any]:
    data = load_json(PHRASE_INDEX)
    if route_id in STATE_ONLY_ROUTES:
        state_result = STATE_ONLY_ROUTES[route_id]
        if route_id == "stop_boundary" and include_boundary:
            # Explicit boundary audit is allowed, but only boundary-only
            # entries from the dedicated shard may be returned.
            route = find_route(data, route_id)
            entries = load_shard(route)
            matches = []
            for entry in entries:
                if str(entry.get("callability")) != "boundary_only":
                    continue
                score = score_entry(entry, query, [str(item) for item in route.get("section_terms", [])], stage, direction)
                if score > 0 or not query:
                    item = dict(entry)
                    item["score"] = round(score, 2)
                    matches.append(item)
            matches.sort(key=lambda item: (-item["score"], str(item.get("phrase_key", ""))))
            return {
                "schema_version": 1,
                "route": route_id,
                "retrieval_status": "boundary_only",
                "source": "boundary_shard",
                "matches": matches[: max(0, limit)],
                "context_readback_required": True,
                "sendability": "not_granted",
            }
        return {
            "schema_version": 1,
            "route": route_id,
            "retrieval_status": state_result["retrieval_status"],
            "matches": [],
            "reason": state_result["reason"],
        }
    route = find_route(data, route_id)
    if route_id == "intimacy_conditional":
        # Keep the four checks explicit.  ``--sexual-context`` is retained as
        # a compatibility marker for upstream callers, but cannot waive any
        # individual requirement.
        verified = (
            explicit_same_topic
            and age_identity_basis
            and mutual_feedback
            and no_refusal_or_discomfort
        )
        if not verified:
            return {
                "schema_version": 1,
                "route": route_id,
                "retrieval_status": "blocked_until_context_verified",
                "matches": [],
                "reason": "\u4eb2\u5bc6\u6216\u6027\u8bdd\u9898\u5fc5\u987b\u540c\u65f6\u6838\u5bf9\u540c\u7c7b\u8bdd\u9898\u3001\u6210\u5e74\u8eab\u4efd\u3001\u4e92\u60e0\u53cd\u9988\u548c\u65e0\u62d2\u7edd\u4e0d\u9002\u4fe1\u53f7",
            }
    candidates: list[tuple[dict[str, Any], str]] = [(entry, "candidate_index") for entry in load_shard(route)]
    source = "candidate_index"
    if full_index:
        candidates.extend((entry, "source_only_audit") for entry in load_full_entries(route))
        source = "candidate_index_plus_full_index_source_only_audit"

    seen: set[str] = set()
    ranked: list[tuple[float, dict[str, Any]]] = []
    filtered: dict[str, int] = {}
    for entry, source_scope in candidates:
        key = str(entry.get("phrase_key") or entry.get("phrase_id") or entry.get("text") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        ok, reason = allowed(entry, include_boundary)
        if not ok:
            filtered[reason or "filtered"] = filtered.get(reason or "filtered", 0) + 1
            continue
        if speaker:
            roles = {str(item) for item in entry.get("speaker_roles", [])}
            if speaker not in roles:
                filtered["speaker_mismatch"] = filtered.get("speaker_mismatch", 0) + 1
                continue
        score = score_entry(entry, query, [str(item) for item in route.get("section_terms", [])], stage, direction)
        if score > 0 or not query:
            item = dict(entry)
            item["source_scope"] = source_scope
            if source_scope == "source_only_audit":
                item["sendability"] = "not_granted"
            ranked.append((score, item))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("phrase_key", ""))))
    matches = []
    for score, entry in ranked[: max(0, limit)]:
        item = dict(entry)
        item["score"] = round(score, 2)
        matches.append(item)

    warnings: list[str] = []
    if not full_index and len(matches) < limit:
        warnings.append("候选入口不足时可显式加 --full-index；完整索引只在按需查询时读取")
    if any("unknown" in {str(role) for role in item.get("speaker_roles", [])} for item in matches):
        warnings.append("\u90e8\u5206\u6761\u76ee\u7684\u8bf4\u8bdd\u4eba\u4ecd\u4e3a unknown\uff0c\u53d1\u9001\u524d\u5fc5\u987b\u56de\u8bfb\u539f\u59cb\u4e0a\u4e0b\u6587")
    if full_index:
        warnings.append("--full-index 仅用于 source-only 审计；命中内容不获得可发送许可")
    return {
        "schema_version": 1,
        "route": route_id,
        "retrieval_status": "candidate_reference_with_source_audit" if full_index else "candidate_reference_after_context_review",
        "source": source,
        "query": query,
        "matches": matches,
        "filtered": filtered,
        "warnings": warnings,
        "context_readback_required": True,
        "sendability": "not_granted" if full_index else "requires_context_review",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--stage", default=None)
    parser.add_argument("--direction", default=None)
    parser.add_argument("--speaker", default=None)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--full-index", action="store_true", help="按需读取完整 Jackson 去重索引")
    parser.add_argument("--include-boundary", action="store_true")
    parser.add_argument("--sexual-context", action="store_true", help="兼容标记；仍必须同时传入四项亲密话题核对条件")
    parser.add_argument("--explicit-same-topic", action="store_true")
    parser.add_argument("--age-identity-basis", action="store_true")
    parser.add_argument("--mutual-feedback", action="store_true")
    parser.add_argument("--no-refusal-or-discomfort", action="store_true")
    args = parser.parse_args()
    print(json.dumps(search(args.route, args.query, args.limit, args.stage, args.direction, args.speaker, args.full_index, args.include_boundary, args.sexual_context, args.explicit_same_topic, args.age_identity_basis, args.mutual_feedback, args.no_refusal_or_discomfort), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
