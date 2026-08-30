#!/usr/bin/env python3
"""Validate knowledge-unit frontmatter with explicit legacy compatibility."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED = ("id", "type", "title", "status", "canonical", "version", "source_refs")
ALLOWED_STATUS = {"candidate", "canonical", "superseded", "rejected", "conflict"}
ALLOWED_TYPES = {
    "policy",
    "stage",
    "signal",
    "rule",
    "direction",
    "case",
    "boundary",
    "viewpoint",
    "conflict",
}

DEFAULT_MANIFEST_NAME = "知识单元元数据兼容清单.json"


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "-")):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def default_manifest_path(root: Path) -> Path:
    """Find the Dragon compatibility manifest next to a knowledge directory."""
    candidates = (
        root.parent / "04-系统" / DEFAULT_MANIFEST_NAME,
        Path.cwd() / "04-系统" / DEFAULT_MANIFEST_NAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"legacy_units": {}}
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("compatibility manifest must be a JSON object")
    legacy_units = manifest.get("legacy_units", {})
    if not isinstance(legacy_units, dict):
        raise ValueError("compatibility manifest legacy_units must be an object")
    return {"legacy_units": legacy_units}


def has_topic(data: dict[str, str], topic: str) -> bool:
    """Use the existing compact frontmatter representation for topic filtering."""
    return topic in data.get("topics", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default="knowledge")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="legacy compatibility manifest (defaults to Dragon 04-系统 manifest)",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="only validate units whose frontmatter topics contain this value",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat registered legacy compatibility warnings as errors",
    )
    args = parser.parse_args()
    root = Path(args.directory).expanduser().resolve()
    files = sorted(root.rglob("*.md")) if root.exists() else []
    manifest_path = args.manifest or default_manifest_path(root)
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR {manifest_path}: invalid compatibility manifest: {exc}")
        return 1
    legacy_units = manifest["legacy_units"]
    errors = 0
    warnings = 0
    checked = 0
    seen_ids: set[str] = set()
    for path in files:
        data = parse_frontmatter(path)
        if args.topic and not has_topic(data, args.topic):
            continue
        checked += 1
        unit_id = data.get("id", "")
        if unit_id:
            seen_ids.add(unit_id)
        legacy = legacy_units.get(unit_id)
        if legacy is not None and not isinstance(legacy, dict):
            print(f"ERROR {manifest_path}: legacy entry {unit_id} must be an object")
            errors += 1
            legacy = None
        status = data.get("status", "")
        accepted_status = legacy.get("accepted_status") if legacy else None
        legacy_compat = bool(
            legacy
            and status == accepted_status
            and data.get("canonical", "").lower() == "true"
            and legacy.get("required_canonical") is True
        )
        raw_allow_missing = legacy.get("allow_missing", []) if legacy else []
        allow_missing = (
            set(raw_allow_missing)
            if legacy_compat and isinstance(raw_allow_missing, list)
            else set()
        )
        missing = [key for key in REQUIRED if key not in data]
        if missing:
            tolerated_missing = [key for key in missing if key in allow_missing]
            hard_missing = [key for key in missing if key not in allow_missing]
            if tolerated_missing and legacy_compat and not args.strict:
                print(
                    f"WARN  {path}: legacy metadata compatibility allows missing "
                    f"{', '.join(tolerated_missing)} (manifest entry {unit_id})"
                )
                warnings += 1
            elif tolerated_missing and legacy_compat and args.strict:
                print(
                    f"ERROR {path}: strict mode rejects legacy missing "
                    f"{', '.join(tolerated_missing)} (manifest entry {unit_id})"
                )
                errors += 1
            if hard_missing:
                print(f"ERROR {path}: missing {', '.join(hard_missing)}")
                errors += 1
        if status and status not in ALLOWED_STATUS:
            if legacy_compat and not args.strict:
                print(
                    f"WARN  {path}: legacy status {status} accepted for "
                    f"canonical compatibility (manifest entry {unit_id})"
                )
                warnings += 1
            elif legacy_compat and args.strict:
                print(
                    f"ERROR {path}: strict mode rejects legacy status {status} "
                    f"(manifest entry {unit_id})"
                )
                errors += 1
            else:
                print(f"ERROR {path}: invalid status {status}")
                errors += 1
        canonical = data.get("canonical", "").lower()
        if canonical not in {"true", "false"}:
            print(f"ERROR {path}: canonical must be true or false")
            errors += 1
        unit_type = data.get("type", "")
        if unit_type and unit_type not in ALLOWED_TYPES:
            print(f"ERROR {path}: invalid type {unit_type}")
            errors += 1
        if status == "conflict" and "developer_decision" not in data:
            print(f"WARN  {path}: conflict unit should record developer_decision")
            warnings += 1
    if not args.topic:
        for legacy_id in sorted(set(legacy_units) - seen_ids):
            print(f"WARN  {manifest_path}: legacy entry {legacy_id} was not found")
            warnings += 1
    print(f"checked={checked} errors={errors} warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
