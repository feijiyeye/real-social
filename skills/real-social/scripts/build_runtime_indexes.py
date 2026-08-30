#!/usr/bin/env python3
"""Build the small, lazy-loaded runtime indexes for the real-social bundle.

The Dragon files remain the source of truth.  This script only derives compact
metadata and route hints; it never changes knowledge-unit status or canonical
flags and it never copies the full phrase corpus into a runtime index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_NAME = "真实社交运行时路由配置.json"
ROUTE_FILES = (
    "runtime-entry.md",
    "route-index.json",
    "navigation-index.json",
    "unit-index.json",
    "phrase-route-index.json",
    "runtime-manifest.json",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc


def split_inline_list(value: str) -> list[str]:
    """Parse the simple inline YAML lists used by current knowledge units."""
    body = value.strip()[1:-1].strip()
    if not body:
        return []
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    depth = 0
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
            current.append(char)
        elif char in "[({":
            depth += 1
            current.append(char)
        elif char in "]) }".replace(" ", ""):
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
        else:
            current.append(char)
    item = "".join(current).strip()
    if item:
        parts.append(item)
    return [strip_yaml_scalar(item) for item in parts]


def strip_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse_value(value: str) -> Any:
    value = value.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        return split_inline_list(value)
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    return strip_yaml_scalar(value)


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    if not match:
        return {}, ""
    block = match.group(1)
    data: dict[str, Any] = {}
    active_list: str | None = None
    for line in block.splitlines():
        top = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if top:
            key, raw = top.groups()
            parsed = parse_value(raw)
            data[key] = parsed
            active_list = key if raw.strip() == "" else None
            continue
        list_item = re.match(r"^\s+-\s+(.*)$", line)
        if list_item and active_list:
            current = data.setdefault(active_list, [])
            if not isinstance(current, list):
                current = []
                data[active_list] = current
            current.append(parse_value(list_item.group(1)))
    return data, block


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if value in (None, ""):
        return []
    return [str(value)]


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_nested(block: str, key: str) -> str | None:
    match = re.search(rf"^\s{{2,}}{re.escape(key)}:\s*(.*?)\s*$", block, flags=re.M)
    return strip_yaml_scalar(match.group(1)) if match else None


def extract_source_refs(block: str) -> list[str]:
    values: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("-"):
            stripped = stripped[1:].strip()
        if not stripped.startswith("file:"):
            continue
        value = stripped.split(":", 1)[1].strip()
        value = strip_yaml_scalar(value)
        if value and value not in values:
            values.append(value)
    return values


def package_path_for_source(source: str, knowledge_root: Path) -> str:
    """Return a portable label without leaking an installation-specific path."""
    source_path = Path(source)
    if not source_path.is_absolute():
        candidate = knowledge_root / source_path
        if candidate.is_file():
            return candidate.relative_to(knowledge_root.parent).as_posix()
        return source.replace("\\", "/")

    # Historical Dragon paths can be mapped by their known relative suffix.
    marker = "/Documents/Dragon知识库/"
    if marker in source:
        return "knowledge/" + source.split(marker, 1)[1]

    basename = source_path.name
    matches = sorted(knowledge_root.rglob(basename)) if basename else []
    if matches:
        return matches[0].relative_to(knowledge_root.parent).as_posix()
    return basename or source


def load_config(skill_root: Path, explicit: Path | None = None) -> dict[str, Any]:
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(
        [
            skill_root / "knowledge" / "04-系统" / CONFIG_NAME,
            skill_root.parent.parent / "04-系统" / CONFIG_NAME,
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            config = read_json(candidate, {})
            if not isinstance(config, dict):
                raise ValueError(f"route config must be an object: {candidate}")
            return config
    raise FileNotFoundError(f"route config not found: {CONFIG_NAME}")


def compact_unit(path: Path, knowledge_root: Path) -> dict[str, Any]:
    data, block = parse_frontmatter(path)
    relative = path.relative_to(knowledge_root.parent).as_posix()
    def compact_list(value: Any, limit: int) -> list[str]:
        result = as_list(value)
        return [item[:240] for item in result[:limit]]

    unit: dict[str, Any] = {
        "id": str(data.get("id", "")),
        "type": str(data.get("type", "")),
        "title": str(data.get("title", "")),
        "status": str(data.get("status", "")),
        "canonical": bool_value(data.get("canonical", False)),
        "version": int_value(data.get("version")),
        "path": relative,
        "topics": compact_list(data.get("topics"), 12),
        "aliases": compact_list(data.get("aliases"), 12),
        "related": compact_list(data.get("related"), 32),
        "trigger_signals": compact_list(data.get("trigger_signals"), 8),
        "disconfirming_signals": compact_list(data.get("disconfirming_signals"), 8),
        "allowed_directions": compact_list(data.get("allowed_directions"), 8),
        "forbidden_moves": compact_list(data.get("forbidden_moves"), 8),
        "scope_stage": extract_nested(block, "stage") or "",
        "authority": str(data.get("authority", "")),
        "confidence": data.get("confidence"),
        "callability": str(data.get("callability", "")),
        "chain_refs": compact_list(data.get("chain_refs"), 16),
        "case_refs": compact_list(data.get("case_refs"), 16),
        "source_ref_files": [package_path_for_source(item, knowledge_root) for item in extract_source_refs(block)[:8]],
    }
    # Empty optional values add noise to the runtime index and are not useful
    # for routing.  Keep the required identity fields even when malformed so
    # the validator can report the source problem.
    for key in ("topics", "aliases", "related", "trigger_signals", "disconfirming_signals", "allowed_directions", "forbidden_moves", "chain_refs", "case_refs", "source_ref_files"):
        if not unit[key]:
            unit.pop(key)
    for key in ("version", "confidence"):
        if unit[key] is None:
            unit.pop(key)
    return unit


def build_unit_index(skill_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    knowledge_root = skill_root / "knowledge"
    units: list[dict[str, Any]] = []
    units_root = knowledge_root / "02-知识单元"
    if units_root.is_dir():
        for path in sorted(units_root.glob("*.md")):
            item = compact_unit(path, knowledge_root)
            if item.get("id"):
                units.append(item)

    route_membership: dict[str, list[str]] = {}
    for route in config.get("task_routes", []) + config.get("state_routes", []):
        if not isinstance(route, dict):
            continue
        for unit_id in route.get("primary_units", []):
            route_membership.setdefault(str(unit_id), []).append(str(route.get("id", "")))
    for item in units:
        route_ids = sorted(set(route_membership.get(item["id"], [])))
        if route_ids:
            item["route_ids"] = route_ids

    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "package_id": "real-social",
        "unit_count": len(units),
        "canonical_count": sum(1 for item in units if item.get("canonical") is True),
        "candidate_count": sum(1 for item in units if item.get("status") == "candidate"),
        "units": units,
    }


def build_route_index(config: dict[str, Any], unit_index: dict[str, Any]) -> dict[str, Any]:
    known_ids = {str(item.get("id")) for item in unit_index.get("units", [])}

    def clean_route(route: dict[str, Any], kind: str) -> dict[str, Any]:
        result = dict(route)
        result["kind"] = kind
        result["primary_units"] = [str(item) for item in route.get("primary_units", [])]
        result["missing_primary_units"] = [item for item in result["primary_units"] if item not in known_ids]
        result["match_any"] = [str(item) for item in route.get("match_any", [])]
        return result

    task_routes = [clean_route(route, "task") for route in config.get("task_routes", []) if isinstance(route, dict)]
    state_routes = [clean_route(route, "state") for route in config.get("state_routes", []) if isinstance(route, dict)]
    state_routes.sort(key=lambda item: int(item.get("priority", 0)), reverse=True)
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "package_id": "real-social",
        "default_task_route": config.get("default_task_route", "analyze_chat"),
        "default_state_route": config.get("default_state_route", "unknown_stage"),
        "limits": config.get("limits", {}),
        "stage_navigation": config.get("stage_navigation", {}),
        "priority_order": [item["id"] for item in state_routes],
        "task_routes": task_routes,
        "state_routes": state_routes,
        "hard_boundaries": config.get("hard_boundaries", {}),
        "lazy_loading": config.get("lazy_loading", {}),
    }


def normalize_source_ref(value: str) -> str:
    value = value.replace("\\", "/")
    if value.startswith("knowledge/"):
        return value
    if value.startswith("01-原始资料/") or value.startswith("external-sources/"):
        return "knowledge/" + value
    return value


CALLABILITY_RANK = {
    "boundary_only": 50,
    "not_default_direction": 40,
    "source_only_unreviewed": 35,
    "source_preserved": 30,
    "context_required": 20,
    "candidate_reference": 15,
    "candidate_callable_after_context_review": 10,
    "candidate_callable": 10,
}


def entry_from_candidate(entry: dict[str, Any], group_callability: str = "candidate_callable_after_context_review") -> dict[str, Any]:
    refs = []
    for ref in entry.get("source_refs", []) if isinstance(entry.get("source_refs"), list) else []:
        if not isinstance(ref, dict):
            continue
        copy = {key: ref[key] for key in ("file", "locator", "section") if key in ref}
        if "file" in copy:
            copy["file"] = normalize_source_ref(str(copy["file"]))
        refs.append(copy)
    entry_callability = str(entry.get("callability") or "")
    # A source-group restriction is a lower bound on safety.  An entry may be
    # more restrictive than its group, but it must never widen a group-level
    # boundary such as ``boundary_only``.
    if CALLABILITY_RANK.get(group_callability, 0) > CALLABILITY_RANK.get(entry_callability, 0):
        effective_callability = group_callability
    else:
        effective_callability = entry_callability or group_callability
    result: dict[str, Any] = {
        "phrase_id": entry.get("phrase_id"),
        "phrase_key": entry.get("phrase_key"),
        "text": entry.get("text", entry.get("canonical_text", "")),
        "sections": [str(item) for item in entry.get("sections", [])],
        "speaker_roles": [str(item) for item in entry.get("speaker_roles", [])],
        "occurrence_count": entry.get("occurrence_count", entry.get("occurrence_count_in_merged_index", 0)),
        "callability": effective_callability,
        "source_refs": refs,
    }
    return {key: value for key, value in result.items() if value not in (None, "", [], {})}


def build_phrase_index(skill_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    knowledge_root = skill_root / "knowledge"
    source_root = knowledge_root / "01-原始资料"
    jackson = read_json(source_root / "2026-08-23_Jackson体系话术候选参考清单.json", {})
    apple = read_json(source_root / "2026-08-23_AppleNotesQuickNotes候选参考增补清单.json", {})
    sources_by_group: dict[str, list[dict[str, Any]]] = {}
    for document in (jackson, apple):
        for group in document.get("groups", []) if isinstance(document, dict) else []:
            if not isinstance(group, dict):
                continue
            group_callability = str(group.get("callability") or "candidate_callable_after_context_review")
            entries = [
                entry_from_candidate(item, group_callability)
                for item in group.get("entries", [])
                if isinstance(item, dict)
            ]
            sources_by_group.setdefault(str(group.get("id", "")), []).extend(entries)

    routes: list[dict[str, Any]] = []
    shards: dict[str, dict[str, Any]] = {}
    for route in config.get("phrase_routes", []):
        if not isinstance(route, dict):
            continue
        merged: dict[str, dict[str, Any]] = {}
        for group_id in route.get("source_groups", []):
            for entry in sources_by_group.get(str(group_id), []):
                key = str(entry.get("phrase_key") or entry.get("phrase_id") or entry.get("text"))
                if key not in merged:
                    merged[key] = dict(entry)
                    continue
                current = merged[key]
                current["sections"] = sorted(set(current.get("sections", [])) | set(entry.get("sections", [])))
                current["speaker_roles"] = sorted(set(current.get("speaker_roles", [])) | set(entry.get("speaker_roles", [])))
                current["source_refs"] = current.get("source_refs", []) + [ref for ref in entry.get("source_refs", []) if ref not in current.get("source_refs", [])]
                current["occurrence_count"] = max(current.get("occurrence_count", 0), entry.get("occurrence_count", 0))
                if CALLABILITY_RANK.get(str(entry.get("callability")), 0) > CALLABILITY_RANK.get(str(current.get("callability")), 0):
                    current["callability"] = entry.get("callability")
        route_copy = dict(route)
        route_copy["preferred_entry_count"] = len(merged)
        route_copy["shard"] = f"runtime/phrase-routes/{route_copy.get('id', 'unknown')}.json"
        route_copy["full_index"] = {
            "path": "knowledge/01-原始资料/2026-08-23_Jackson体系话术去重索引.json",
            "lookup": "on_demand",
            "section_terms": [str(item) for item in route.get("section_terms", [])],
        }
        routes.append(route_copy)
        shards[str(route_copy.get("id", "unknown"))] = {
            "schema_version": 1,
            "generated_at": now_iso(),
            "package_id": "real-social",
            "route": route_copy.get("id"),
            "label": route_copy.get("label"),
            "entries": list(merged.values()),
        }

    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "package_id": "real-social",
        "retrieval_policy": {
            "candidate_first": True,
            "full_index": "on_demand",
            "context_readback_required": True,
            "recovery": "disabled",
            "sexual_route_requires": ["explicit_same_topic", "age_identity_basis", "mutual_feedback", "no_refusal_or_discomfort"],
        },
        "routes": routes,
        "_shards": shards,
    }


def render_runtime_entry(config: dict[str, Any]) -> str:
    state_routes = sorted(
        (item for item in config.get("state_routes", []) if isinstance(item, dict)),
        key=lambda item: int(item.get("priority", 0)),
        reverse=True,
    )
    priority_lines = "\n".join(
        f"{int(route.get('priority', 0)):>3}  `{route.get('id', '')}`：{route.get('label', '')}" for route in state_routes
    )
    task_lines = "\n".join(
        f"- `{route.get('id', '')}`：{route.get('label', '')}"
        for route in config.get("task_routes", [])
        if isinstance(route, dict)
    )
    stage_navigation = config.get("stage_navigation", {})
    required_outputs = stage_navigation.get("required_outputs", []) if isinstance(stage_navigation, dict) else []
    examples_require = stage_navigation.get("examples_require", []) if isinstance(stage_navigation, dict) else []
    evidence_layers = stage_navigation.get("evidence_layers", []) if isinstance(stage_navigation, dict) else []
    required_output_text = "、".join(f"`{item}`" for item in required_outputs)
    examples_require_text = "、".join(f"`{item}`" for item in examples_require)
    evidence_layers_text = "、".join(f"`{item}`" for item in evidence_layers)
    return f"""# 真实社交运行时入口

这是 `real-social` 的轻量启动层。先读本文件和 `route-index.json`，再根据当前输入只选择一个主模块；不要在普通聊天首轮加载完整 `manifest`、续接摘要或 2867 条话术索引。

## 调用顺序

```text
任务模式识别 -> 硬边界/状态识别 -> 选择一个主模块
-> 读取正式单元与小型索引 -> 按需召回案例/话术
-> 输出证据、阶段、方向、状态字段与下一步
```

## 阶段导航优先

聊天分析和回复任务默认先做阶段导航，再决定是否给示例。新聊天证据先区分 {evidence_layers_text}，并输出 {required_output_text}；术语必须受证据约束，不能直接当话术模板。只有阶段和方向明确、用户明确要求可发送内容且边界满足（{examples_require_text}）时才进入少量示例。收到新反馈后重新判断阶段、方向、反馈门控和下一步，不机械延续上一条建议。

任务路由：

{task_lines}

状态路由按优先级处理（高优先级覆盖低优先级）：

```text
{priority_lines}
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
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_indexes(skill_root: Path, config_path: Path | None = None) -> list[Path]:
    skill_root = skill_root.resolve()
    runtime_root = skill_root / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    config = load_config(skill_root, config_path.resolve() if config_path else None)
    unit_index = build_unit_index(skill_root, config)
    route_index = build_route_index(config, unit_index)
    navigation_index = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "package_id": "real-social",
        "rules": config.get("navigation_rules", []),
    }
    phrase_index = build_phrase_index(skill_root, config)
    shards = phrase_index.pop("_shards", {})

    payloads: dict[str, str] = {
        "runtime-entry.md": render_runtime_entry(config),
        "route-index.json": json.dumps(route_index, ensure_ascii=False, indent=2) + "\n",
        "navigation-index.json": json.dumps(navigation_index, ensure_ascii=False, indent=2) + "\n",
        "unit-index.json": json.dumps(unit_index, ensure_ascii=False, indent=2) + "\n",
        "phrase-route-index.json": json.dumps(phrase_index, ensure_ascii=False, indent=2) + "\n",
    }
    for name, content in payloads.items():
        (runtime_root / name).write_text(content, encoding="utf-8")

    shard_root = runtime_root / "phrase-routes"
    shard_root.mkdir(parents=True, exist_ok=True)
    for stale in shard_root.glob("*.json"):
        stale.unlink()
    shard_files: list[Path] = []
    for route_id, shard in sorted(shards.items()):
        shard_path = shard_root / f"{route_id}.json"
        shard_path.write_text(json.dumps(shard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        shard_files.append(shard_path)

    generated_files = [runtime_root / name for name in payloads] + shard_files
    runtime_manifest = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "package_id": "real-social",
        "entry": "runtime/runtime-entry.md",
        "indexes": [f"runtime/{name}" for name in payloads if name.endswith(".json")]
        + [f"runtime/phrase-routes/{path.name}" for path in shard_files],
        "unit_count": unit_index["unit_count"],
        "canonical_count": unit_index["canonical_count"],
        "candidate_count": unit_index["candidate_count"],
        "phrase_route_count": len(phrase_index["routes"]),
        "full_phrase_index": "knowledge/01-原始资料/2026-08-23_Jackson体系话术去重索引.json",
        "files": [
            {
                "path": path.relative_to(skill_root).as_posix(),
                "sha256": sha256(path),
                "size": path.stat().st_size,
            }
            for path in generated_files
        ],
    }
    manifest_path = runtime_root / "runtime-manifest.json"
    manifest_path.write_text(json.dumps(runtime_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return generated_files + [manifest_path]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    generated = build_indexes(args.skill_root, args.config)
    print(json.dumps({"runtime_root": str(args.skill_root.resolve() / "runtime"), "files": [path.name for path in generated]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
