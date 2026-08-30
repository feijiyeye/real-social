#!/usr/bin/env python3
"""Validate a portable real-social Skill bundle and its manifest hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/policy.md",
    "references/runtime-contract.md",
    "references/processing-pipeline.md",
    "references/knowledge-schema.md",
    "references/portable-runtime.md",
    "scripts/build_runtime_indexes.py",
    "scripts/route_request.py",
    "scripts/search_phrases.py",
    "scripts/validate_knowledge.py",
    "knowledge/manifest.json",
    "knowledge/SOURCE_OF_TRUTH.md",
    "knowledge/AGENTS.md",
    "knowledge/02-知识单元",
    "knowledge/04-系统/知识单元元数据兼容清单.json",
    "knowledge/04-系统/真实社交运行时路由设计.md",
    "knowledge/04-系统/真实社交运行时路由配置.json",
    "runtime/runtime-entry.md",
    "runtime/route-index.json",
    "runtime/navigation-index.json",
    "runtime/unit-index.json",
    "runtime/phrase-route-index.json",
    "runtime/runtime-manifest.json",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, errors: list[str]) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON {path.relative_to(path.parents[1])}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"runtime JSON must be an object: {path}")
        return {}
    return value


def validate_runtime(root: Path, errors: list[str]) -> None:
    runtime_root = root / "runtime"
    route_index = read_json(runtime_root / "route-index.json", errors)
    navigation_index = read_json(runtime_root / "navigation-index.json", errors)
    unit_index = read_json(runtime_root / "unit-index.json", errors)
    phrase_index = read_json(runtime_root / "phrase-route-index.json", errors)
    runtime_manifest = read_json(runtime_root / "runtime-manifest.json", errors)

    units = unit_index.get("units", [])
    if not isinstance(units, list):
        errors.append("unit-index units must be a list")
        units = []
    unit_ids = {str(item.get("id")) for item in units if isinstance(item, dict)}
    formal = [
        item for item in units
        if isinstance(item, dict)
        and item.get("id") == "K-20260826-001"
        and item.get("status") == "canonical"
        and item.get("canonical") is True
    ]
    if not formal:
        errors.append("runtime unit-index must contain canonical K-20260826-001")
    actual_unit_count = len(units)
    actual_canonical_count = sum(
        1 for item in units
        if isinstance(item, dict) and item.get("canonical") is True
    )
    actual_candidate_count = sum(
        1 for item in units
        if isinstance(item, dict) and item.get("status") == "candidate"
    )
    for item in units:
        if isinstance(item, dict) and item.get("status") == "candidate" and item.get("canonical") is True:
            errors.append(f"candidate unit cannot be canonical: {item.get('id')}")
    for key, actual in (
        ("unit_count", actual_unit_count),
        ("canonical_count", actual_canonical_count),
        ("candidate_count", actual_candidate_count),
    ):
        declared = unit_index.get(key)
        if declared != actual:
            errors.append(f"unit-index {key} mismatch: declared={declared} actual={actual}")

    task_routes = route_index.get("task_routes", [])
    state_routes = route_index.get("state_routes", [])
    if not isinstance(task_routes, list) or not isinstance(state_routes, list):
        errors.append("route-index task_routes and state_routes must be lists")
        task_routes = []
        state_routes = []
    for label, routes in (("task", task_routes), ("state", state_routes)):
        seen: set[str] = set()
        for route in routes:
            if not isinstance(route, dict):
                errors.append(f"{label} route must be an object")
                continue
            route_id = str(route.get("id", ""))
            if not route_id:
                errors.append(f"{label} route missing id")
            if route_id in seen:
                errors.append(f"duplicate {label} route id: {route_id}")
            seen.add(route_id)
            missing = [item for item in route.get("primary_units", []) if str(item) not in unit_ids]
            if missing:
                errors.append(f"{label} route {route_id} references missing units: {', '.join(map(str, missing))}")
    state_by_id = {str(route.get("id")): route for route in state_routes if isinstance(route, dict)}
    stop = state_by_id.get("stop_boundary", {})
    recovery = state_by_id.get("recovery", {})
    if stop.get("priority", 0) < recovery.get("priority", 0):
        errors.append("stop_boundary priority must exceed recovery priority")
    if recovery.get("phrase_retrieval") != "disabled":
        errors.append("recovery route must disable phrase retrieval")
    if route_index.get("default_state_route") not in state_by_id:
        errors.append("route-index default_state_route is not defined")

    phrase_routes = phrase_index.get("routes", [])
    if not isinstance(phrase_routes, list):
        errors.append("phrase-route-index routes must be a list")
        phrase_routes = []
    phrase_ids: set[str] = set()
    for route in phrase_routes:
        if not isinstance(route, dict):
            errors.append("phrase route must be an object")
            continue
        route_id = str(route.get("id", ""))
        if route_id in phrase_ids:
            errors.append(f"duplicate phrase route id: {route_id}")
        phrase_ids.add(route_id)
        shard_path_value = route.get("shard")
        if not isinstance(shard_path_value, str):
            errors.append(f"phrase route {route_id} missing shard path")
        else:
            shard_path = root / shard_path_value
            try:
                shard_path.relative_to(root)
            except ValueError:
                errors.append(f"phrase route {route_id} shard escapes bundle: {shard_path_value}")
                shard_path = None
            if shard_path is not None and not shard_path.is_file():
                errors.append(f"phrase route {route_id} shard missing: {shard_path_value}")
            elif shard_path is not None:
                shard_doc = read_json(shard_path, errors)
                if shard_doc.get("route") != route_id:
                    errors.append(f"phrase route {route_id} shard route field mismatch")
                entries = shard_doc.get("entries", [])
                if not isinstance(entries, list):
                    errors.append(f"phrase route {route_id} shard entries must be a list")
                elif route_id == "stop_boundary":
                    non_boundary = [
                        str(entry.get("phrase_key", ""))
                        for entry in entries
                        if isinstance(entry, dict) and entry.get("callability") != "boundary_only"
                    ]
                    if non_boundary:
                        errors.append(
                            "stop_boundary shard contains non-boundary entries: "
                            + ", ".join(non_boundary[:5])
                        )
        full = route.get("full_index", {})
        full_path = full.get("path") if isinstance(full, dict) else None
        if not isinstance(full_path, str):
            errors.append(f"phrase route {route_id} missing full index path")
        elif not (root / full_path).is_file():
            errors.append(f"phrase route {route_id} full index missing: {full_path}")
    if "intimacy_conditional" not in phrase_ids:
        errors.append("phrase-route-index missing intimacy_conditional route")

    nav_rules = navigation_index.get("rules", [])
    if not isinstance(nav_rules, list):
        errors.append("navigation-index rules must be a list")

    if runtime_manifest.get("unit_count") != actual_unit_count:
        errors.append("runtime-manifest unit_count does not match unit-index")
    if runtime_manifest.get("canonical_count") != actual_canonical_count:
        errors.append("runtime-manifest canonical_count does not match unit-index")
    if runtime_manifest.get("candidate_count") != actual_candidate_count:
        errors.append("runtime-manifest candidate_count does not match unit-index")
    if runtime_manifest.get("phrase_route_count") != len(phrase_routes):
        errors.append("runtime-manifest phrase_route_count does not match phrase-route-index")
    full_phrase_index = runtime_manifest.get("full_phrase_index")
    if not isinstance(full_phrase_index, str) or not (root / full_phrase_index).is_file():
        errors.append("runtime-manifest full_phrase_index is missing")

    runtime_files = runtime_manifest.get("files", [])
    runtime_file_paths: set[str] = set()
    if not isinstance(runtime_files, list):
        errors.append("runtime-manifest files must be a list")
    else:
        for record in runtime_files:
            if not isinstance(record, dict):
                errors.append("runtime-manifest contains a non-object file record")
                continue
            relative = record.get("path")
            expected = record.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected, str):
                errors.append("runtime-manifest file record lacks path or sha256")
                continue
            if relative in runtime_file_paths:
                errors.append(f"runtime-manifest duplicate file record: {relative}")
            runtime_file_paths.add(relative)
            path = root / relative
            try:
                path.relative_to(root)
            except ValueError:
                errors.append(f"runtime-manifest path escapes bundle: {relative}")
                continue
            if not path.is_file():
                errors.append(f"runtime-manifest file missing: {relative}")
            elif digest(path) != expected:
                errors.append(f"runtime-manifest hash mismatch: {relative}")
            if isinstance(record.get("size"), int) and path.is_file() and record["size"] != path.stat().st_size:
                errors.append(f"runtime-manifest size mismatch: {relative}")

    indexes = runtime_manifest.get("indexes", [])
    if not isinstance(indexes, list):
        errors.append("runtime-manifest indexes must be a list")
        indexes = []
    for relative in indexes:
        if not isinstance(relative, str):
            errors.append("runtime-manifest index path must be a string")
            continue
        if not (root / relative).is_file():
            errors.append(f"runtime-manifest index missing: {relative}")
        if runtime_file_paths and relative not in runtime_file_paths:
            errors.append(f"runtime-manifest index is not hashed: {relative}")
    for route in phrase_routes:
        if not isinstance(route, dict):
            continue
        shard = route.get("shard")
        if isinstance(shard, str) and runtime_file_paths and shard not in runtime_file_paths:
            errors.append(f"phrase shard is not hashed in runtime-manifest: {shard}")

    for path in (root / "runtime").rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json"}:
            text = path.read_text(encoding="utf-8")
            if "/Users/company/" in text or "/Volumes/" in text:
                errors.append(f"runtime file contains machine-specific absolute path: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.bundle).expanduser().resolve()
    errors: list[str] = []

    for relative in REQUIRED:
        path = root / relative
        if not path.exists():
            errors.append(f"missing required path: {relative}")

    skill_text = (root / "SKILL.md").read_text(encoding="utf-8") if (root / "SKILL.md").is_file() else ""
    if "name: real-social" not in skill_text:
        errors.append("SKILL.md does not declare name: real-social")
    if "/Users/company/" in skill_text or "/Volumes/" in skill_text:
        errors.append("SKILL.md contains a machine-specific absolute path")

    manifest_path = root / "knowledge/manifest.json"
    manifest: dict[str, object] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid manifest JSON: {exc}")

    records = manifest.get("files", []) if isinstance(manifest, dict) else []
    checked = 0
    if not isinstance(records, list):
        errors.append("manifest files must be a list")
        records = []
    for record in records:
        if not isinstance(record, dict):
            errors.append("manifest contains a non-object file record")
            continue
        relative = record.get("bundle_path")
        expected = record.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append("manifest file record lacks bundle_path or sha256")
            continue
        path = root / relative
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"manifest path escapes bundle: {relative}")
            continue
        if not path.is_file():
            errors.append(f"manifest file missing: {relative}")
            continue
        checked += 1
        actual = digest(path)
        if actual != expected:
            errors.append(f"hash mismatch: {relative}")

    if manifest.get("package_id") != "real-social":
        errors.append("manifest package_id must be real-social")
    if manifest.get("display_name") != "真实社交":
        errors.append("manifest display_name must be 真实社交")

    validate_runtime(root, errors)

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"checked={checked} errors={len(errors)}")
        return 1
    print(f"checked={checked} errors=0 package=real-social display=真实社交")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
