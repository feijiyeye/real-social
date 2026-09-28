#!/usr/bin/env python3
"""Build the public runtime-only real-social Skill snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
EXCLUDED_RAW_FILES = {
    "2026-08-25_AI找出劲爆片段提示词.txt",
    "2026-08-25_8.17.srt",
}


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
        destination = destination_root / relative
        if source.suffix.lower() in {".md", ".txt", ".json", ".srt"}:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(sanitize_public_text(read_text(source)), encoding="utf-8")
            records.append(
                {
                    "source_label": source_label,
                    "original_path": str(source),
                    "bundle_path": destination.relative_to(SKILL_ROOT).as_posix(),
                    "sha256": sha256(destination),
                    "size": str(destination.stat().st_size),
                }
            )
        else:
            copy_one(source, destination, records, source_label, original_path=str(source))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sanitize_public_text(text: str) -> str:
    """Remove raw/external source paths from public structured artifacts."""
    text = re.sub(r"/Users/company/[^\"`\n )]+", "local_only", text)
    text = re.sub(r"/Volumes/[^\"`\n )]+", "local_only", text)
    text = re.sub(
        r"/Users/company/Documents/Dragon知识库/(?:01-原始资料|external-sources)/[^\"`\n )]+",
        "local_only",
        text,
    )
    return re.sub(r"(?<![\w`])(?:01-原始资料|external-sources)/[^\"`\n )]+", "local_only", text)


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
    text = sanitize_public_text(text)
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


def sanitize_project_snapshot(records: list[dict[str, str]]) -> None:
    """Remove unrelated short-video clipping entries from copied governance text."""
    transforms: dict[str, Callable[[str], str]] = {
        "knowledge/03-动态索引/主题索引.md": lambda text: "\n".join(
            line
            for line in text.splitlines()
            if "短视频内容筛选" not in line and "短视频传播" not in line
        )
        + "\n",
        "knowledge/04-系统/入库日志.md": lambda text: "\n".join(
            line for line in text.splitlines() if not line.startswith("| 2026-08-25 |")
        )
        + "\n",
        "knowledge/04-系统/系统状态.md": lambda text: text.replace(
            "- 当前候选知识单元：49", "- 当前候选知识单元：47"
        ).replace(
            "- 原始资料文件：82（排除 `01-原始资料/.gitkeep`；本次新增提示词和 8.17.srt 归档副本）",
            "- 原始资料文件：80（排除 `01-原始资料/.gitkeep`）",
        ).replace(
            "- 候选主题：11", "- 候选主题：9"
        ).replace(
            "其中男性情感聊天候选 47 个，短视频筛选候选 2 个；",
            "其中男性情感聊天候选 47 个；",
        ).replace(
            "- 2026-08-25 新增短视频筛选候选：`K-20260825-001` 保存用户提供的“AI找出劲爆片段”提示词，`K-20260825-002` 保存基于 `8.17.srt` 的 20 段候选和 Top 5。两者均为 `candidate`，不计入当前有效知识；SRT 的中英文重复段和第 1,902 条时间码回跳已记录。\n",
            "",
        ).replace(
            "短视频筛选报告位于 `02-知识单元/K-20260825-002_8.17直播字幕劲爆片段筛选候选.md`。",
            "",
        ),
    }
    for relative, transform in transforms.items():
        path = SKILL_ROOT / relative
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        updated = transform(original)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        for record in records:
            if record.get("bundle_path") == relative:
                record["sha256"] = sha256(path)
                record["size"] = str(path.stat().st_size)
                break


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

    # Expose portable governance copies at the bundle root. Exact governance
    # originals stay in the local Dragon repository and are never copied.
    for name in ("SOURCE_OF_TRUTH.md", "AGENTS.md", "CLAUDE.md", "README.md"):
        source = dragon_root / name
        if source.is_file():
            write_generated(source, KNOWLEDGE_ROOT / name, records, dragon_root)

    # Raw source files and external originals are intentionally excluded from
    # this public snapshot. They remain available in the local Dragon source.
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
    sanitize_project_snapshot(records)
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
        "publication": "public_runtime_only",
        "source_audit": "local_only",
        "excluded_paths": [
            "knowledge/01-原始资料/",
            "knowledge/external-sources/",
            "knowledge/_original_dragon_root/",
        ],
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
        "files": [
            {key: value for key, value in record.items() if key not in {"original_path", "source_sha256"}}
            for record in records
        ],
        "local_only_sources": True,
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
