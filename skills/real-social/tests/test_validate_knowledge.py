#!/usr/bin/env python3
"""Regression tests for legacy metadata compatibility in validate_knowledge.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_knowledge.py"


VALID = """---
id: {unit_id}
type: stage
title: Test unit
created: 2026-08-23
updated: 2026-08-23
status: candidate
canonical: false
version: 1
topics: [{topic}]
source_refs: [test]
---

# Test unit
"""


LEGACY = """---
id: LEGACY-001
title: Legacy unit
created: 2026-08-23
updated: 2026-08-23
status: active
canonical: true
topics: [male-emotion]
source_refs: [test]
---

# Legacy unit
"""


class ValidatorCompatibilityTests(unittest.TestCase):
    def run_validator(self, root: Path, manifest: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(root), "--manifest", str(manifest), *extra],
            check=False,
            capture_output=True,
            text=True,
        )

    def write_manifest(self, root: Path) -> Path:
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "legacy_units": {
                        "LEGACY-001": {
                            "accepted_status": "active",
                            "required_canonical": True,
                            "allow_missing": ["type", "version"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_registered_legacy_warns_but_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "legacy.md").write_text(LEGACY, encoding="utf-8")
            manifest = self.write_manifest(root)
            result = self.run_validator(root, manifest)
            self.assertEqual(result.returncode, 0)
            self.assertIn("errors=0 warnings=2", result.stdout)

    def test_strict_mode_rejects_registered_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "legacy.md").write_text(LEGACY, encoding="utf-8")
            manifest = self.write_manifest(root)
            result = self.run_validator(root, manifest, "--strict")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("errors=2", result.stdout)

    def test_unregistered_missing_fields_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = LEGACY.replace("LEGACY-001", "NEW-001")
            (root / "new.md").write_text(content, encoding="utf-8")
            manifest = self.write_manifest(root)
            result = self.run_validator(root, manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing type, version", result.stdout)
            self.assertIn("invalid status active", result.stdout)

    def test_registered_id_with_wrong_status_is_not_compat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = LEGACY.replace("status: active", "status: candidate")
            (root / "wrong-status.md").write_text(content, encoding="utf-8")
            manifest = self.write_manifest(root)
            result = self.run_validator(root, manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing type, version", result.stdout)

    def test_topic_filter_excludes_other_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "male.md").write_text(
                VALID.format(unit_id="MALE-001", topic="male-emotion"), encoding="utf-8"
            )
            (root / "short.md").write_text(
                VALID.format(unit_id="SHORT-001", topic="short-video"), encoding="utf-8"
            )
            manifest = self.write_manifest(root)
            result = self.run_validator(root, manifest, "--topic", "male-emotion")
            self.assertEqual(result.returncode, 0)
            self.assertIn("checked=1 errors=0", result.stdout)

    def test_missing_canonical_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = VALID.format(unit_id="NO-CANONICAL", topic="male-emotion").replace(
                "canonical: false\n", ""
            )
            (root / "missing-canonical.md").write_text(content, encoding="utf-8")
            manifest = self.write_manifest(root)
            result = self.run_validator(root, manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing canonical", result.stdout)


if __name__ == "__main__":
    unittest.main()
