#!/usr/bin/env python3
"""Build a portable real-social Skill snapshot from the current Dragon sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional


SKILL_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = SKILL_ROOT / "knowledge"
DEFAULT_DRAGON_ROOT = Path("/Users/company/Documents/Dragon知识库")
DEFAULT_EXTERNAL_ROOT = Path("/Volumes/PS3001/Jackson案例素材Skill")
PROJECT_TOPICS = ("男性情感聊天教学", "线上聊天候选", "真实社交")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_one(
    source: Path,
    destination: Path,
    records: list[dict[str, str]],
    source_label: str,
    original_path: Optional[str] = None,
) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_digest = sha256(source)
    destination_digest = sha256(destination)
    if source_digest != destination_digest:
        raise OSError(f"copy hash mismatch: {source} -> {destination}")
    records.append(
        {
            "source_label": source_label,
            "original_path": original_path or str(source),
            "bundle_path": destination.relative_to(SKILL_ROOT).as_posix(),
            "sha256": destination_digest,
            "source_sha256": source_digest,
            "size": str(destination.stat().st_size),
        }
    )


def copy_tree(
    source_root: Path,
    destination_root: Path,
    records: list[dict[str, str]],
    source_label: str,
    include: Optional[Callable[[Path], bool]] = None,
) -> None:
    for source in sorted(source_root.rglob("*")):
        if not source.is_file():
            continue
        if include and not include(source):
            continue
        relative = source.relative_to(source_root)
        copy_one(
            source,
            destination_root / relative,
            records,
            source_label,
            original_path=str(source),
        )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_real_social_unit(path: Path) -> bool:
    if path.name == ".gitkeep":
        return False
    text = read_text(path)
    return any(topic in text for topic in PROJECT_TOPICS)


def write_generated(
    source: Path,
    destination: Path,
    records: list[dict[str, str]],
    dragon_root: Path,
) -> None:
    text = read_text(source)
    text = text.replace(str(dragon_root), ".")
    text = text.replace("/Users/company/.codex/skills/male-emotion-chat-coach", ".")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    records.append(
        {
            "source_label": "portable_generated_governance",
            "original_path": str(source),
            "bundle_path": destination.relative_to(SKILL_ROOT).as_posix(),
            "sha256": sha256(destination),
            "size": str(destination.stat().st_size),
        }
    )


def external_file(root: Path, relative: str) -> tuple[Path, str]:
    source = root / relative
    return source, f"external:{relative}"


def build_runtime_indexes() -> list[Path]:
    """Generate compact runtime indexes after the knowledge snapshot is copied."""
    script = SKILL_ROOT / "scripts" / "build_runtime_indexes.py"
    if not script.is_file():
        raise FileNotFoundError(script)
    subprocess.run(
        [sys.executable, str(script), "--skill-root", str(SKILL_ROOT)],
        check=True,
    )
    runtime_root = SKILL_ROOT / "runtime"
    # Include phrase-route shards in the source manifest as well as the five
    # top-level runtime files.  The shards are part of the published runtime,
    # so omitting them makes the manifest unable to verify a real bundle.
    return [path for path in sorted(runtime_root.rglob("*")) if path.is_file()]


def register_generated_file(path: Path, records: list[dict[str, str]]) -> None:
    records.append(
        {
            "source_label": "runtime_generated",
            "original_path": "04-系统/真实社交运行时路由配置.json",
            "bundle_path": path.relative_to(SKILL_ROOT).as_posix(),
            "sha256": sha256(path),
            "size": str(path.stat().st_size),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dragon-root", type=Path, default=DEFAULT_DRAGON_ROOT)
    parser.add_argument("--external-root", type=Path, default=DEFAULT_EXTERNAL_ROOT)
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()
    dragon_root = args.dragon_root.expanduser().resolve()
    external_root = args.external_root.expanduser().resolve()
    if not dragon_root.is_dir():
        raise SystemExit(f"Dragon root not found: {dragon_root}")

    if KNOWLEDGE_ROOT.exists() and not args.keep_existing:
        shutil.rmtree(KNOWLEDGE_ROOT)
    KNOWLEDGE_ROOT.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str]] = []
    missing: list[str] = []

    # Preserve exact governance originals, then expose portable copies at the bundle root.
    for name in ("SOURCE_OF_TRUTH.md", "AGENTS.md", "CLAUDE.md", "README.md"):
        source = dragon_root / name
        if source.is_file():
            copy_one(
                source,
                KNOWLEDGE_ROOT / "_original_dragon_root" / name,
                records,
                "dragon_root_original",
            )
            write_generated(source, KNOWLEDGE_ROOT / name, records, dragon_root)

    # Current project snapshot. Raw files are kept exactly as archived in Dragon.
    copy_tree(
        dragon_root / "01-原始资料",
        KNOWLEDGE_ROOT / "01-原始资料",
        records,
        "dragon_raw",
        include=lambda path: path.name != ".gitkeep" and not path.name.startswith("._"),
    )
    copy_tree(
        dragon_root / "02-知识单元",
        KNOWLEDGE_ROOT / "02-知识单元",
        records,
        "dragon_real_social_knowledge",
        include=is_real_social_unit,
    )
    copy_tree(
        dragon_root / "03-动态索引",
        KNOWLEDGE_ROOT / "03-动态索引",
        records,
        "dragon_index",
    )
    copy_tree(
        dragon_root / "04-系统",
        KNOWLEDGE_ROOT / "04-系统",
        records,
        "dragon_system",
    )
    archive_root = dragon_root / ".trash"
    if archive_root.is_dir():
        copy_tree(
            archive_root,
            KNOWLEDGE_ROOT / "archive",
            records,
            "dragon_real_social_archive",
            include=lambda path: path.parent == archive_root
            and (
                path.name.startswith("2026-08-21_K-20260821-")
                or path.name == "README.md"
            ),
        )

    # External originals still referenced by current knowledge units.
    external_files = [
        "Jackson flow体系/老版体系无广告/体系txt/第三节.txt",
        "Jackson flow体系/老版体系无广告/体系txt/第四节.srt",
        "Jackson flow体系/老版体系无广告/体系txt/第五节｜假性评估.txt",
        "zhenshi-理论.docx",
    ]
    external_files.extend(
        f"杰哥聊天/{name}"
        for name in (
            "杰哥2.srt",
            "杰哥3.srt",
            "杰哥4.srt",
            "杰哥聊天1上.srt",
            "杰哥聊天1下.srt",
            "杰哥聊天5.srt",
            "杰哥聊天6.srt",
            "杰哥聊天7.srt",
            "杰哥聊天8.srt",
            "杰哥聊天9-1.srt",
            "杰哥聊天9-2.srt",
        )
    )
    for relative in external_files:
        source, label = external_file(external_root, relative)
        if source.is_file():
            copy_one(
                source,
                KNOWLEDGE_ROOT / "external-sources" / relative,
                records,
                label,
            )
        else:
            missing.append(str(source))

    notes_root = external_root / "apple_notes_quick_notes_2026_08"
    if notes_root.is_dir():
        copy_tree(
            notes_root,
            KNOWLEDGE_ROOT / "external-sources" / "apple_notes_quick_notes_2026_08",
            records,
            "external:apple_notes_quick_notes_2026_08",
            include=lambda path: not path.name.startswith("._"),
        )
    else:
        missing.append(str(notes_root))

    framework = Path("/Users/company/Documents/Codex/2026-08-21/skill/outputs/male-emotion-chat-framework-v0.md")
    if framework.is_file():
        copy_one(
            framework,
            KNOWLEDGE_ROOT / "external-sources" / "legacy-codex" / framework.name,
            records,
            "external:legacy_codex_framework",
        )
    else:
        missing.append(str(framework))

    # Build the small runtime entry and derived route indexes only after the
    # copied knowledge snapshot is complete.  The full manifest and phrase
    # index remain available for audits but are not part of the default load.
    for generated in build_runtime_indexes():
        register_generated_file(generated, records)

    manifest = {
        "schema_version": 1,
        "package_id": "real-social",
        "display_name": "真实社交",
        "snapshot_date": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source_root": str(dragon_root),
        "external_source_root": str(external_root),
        "scope": "当前 Dragon 知识库中的真实社交/男性情感聊天项目；不含短视频、读书和其他无关项目",
        "runtime_root": "knowledge",
        "runtime_entry": "runtime/runtime-entry.md",
        "runtime_indexes": [
            "runtime/route-index.json",
            "runtime/navigation-index.json",
            "runtime/unit-index.json",
            "runtime/phrase-route-index.json",
            "runtime/runtime-manifest.json",
        ],
        "counts": {
            "files": len(records),
            "knowledge_units": sum(
                1
                for record in records
                if record["bundle_path"].startswith("knowledge/02-知识单元/")
            ),
            "raw_sources": sum(
                1
                for record in records
                if record["bundle_path"].startswith("knowledge/01-原始资料/")
            ),
            "external_sources": sum(
                1
                for record in records
                if record["bundle_path"].startswith("knowledge/external-sources/")
            ),
            "runtime_files": sum(
                1
                for record in records
                if record["bundle_path"].startswith("runtime/")
            ),
        },
        "files": records,
        "source_path_map": {
            record["original_path"]: record["bundle_path"]
            for record in records
            if record.get("original_path")
        },
        "missing_external_sources": missing,
    }
    manifest_path = KNOWLEDGE_ROOT / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"bundle": str(SKILL_ROOT), **manifest["counts"], "missing": len(missing)}, ensure_ascii=False))
    if missing:
        print("Missing external sources:")
        for path in missing:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
