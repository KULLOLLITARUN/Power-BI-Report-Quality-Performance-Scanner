"""Remediation audit store and history management for PBIP Sentinel."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pbiscan.remediation.models import RemediationManifest

logger = logging.getLogger(__name__)

# Manifest IDs are generated as e.g. MAN-20260101-120000-ABCDEF123456; anything
# else (separators, "..") must never reach a filesystem path.
_MANIFEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class RemediationAuditStore:
    """Manages persistent audit records and history for remediation runs."""

    DEFAULT_STORE_DIR_NAME = ".pbiscan"

    @classmethod
    def resolve_store_dir(cls, project_or_store_dir: Path) -> Path:
        """Pure path calculation resolving the remediation audit directory."""
        if project_or_store_dir.name == "remediation" and project_or_store_dir.parent.name == cls.DEFAULT_STORE_DIR_NAME:
            return project_or_store_dir
        elif (project_or_store_dir / cls.DEFAULT_STORE_DIR_NAME / "remediation").exists():
            return project_or_store_dir / cls.DEFAULT_STORE_DIR_NAME / "remediation"
        elif project_or_store_dir.is_dir():
            return project_or_store_dir / cls.DEFAULT_STORE_DIR_NAME / "remediation"
        else:
            return project_or_store_dir.parent / cls.DEFAULT_STORE_DIR_NAME / "remediation"

    @classmethod
    def ensure_store_dir(cls, project_or_store_dir: Path) -> Path:
        """Ensure the audit store directory exists before writing."""
        store_dir = cls.resolve_store_dir(project_or_store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        return store_dir

    @classmethod
    def save_manifest(cls, manifest: RemediationManifest, target_dir: Path) -> Path:
        """Persist a RemediationManifest to disk and update history.json index."""
        store_dir = cls.ensure_store_dir(target_dir)
        manifest_filename = f"manifest_{manifest.manifest_id}.json"
        manifest_path = store_dir / manifest_filename

        # Write immutable manifest file
        manifest_path.write_text(manifest.to_json(indent=2), encoding="utf-8")

        # Update history.json index
        cls._update_history_index(store_dir, manifest, manifest_filename)

        return manifest_path

    @classmethod
    def get_manifest(cls, manifest_id: str, target_dir: Path) -> Optional[RemediationManifest]:
        """Load a specific manifest by ID (pure read-only)."""
        if not _MANIFEST_ID_RE.match(manifest_id):
            return None

        store_dir = cls.resolve_store_dir(target_dir)
        if not store_dir.exists():
            return None

        manifest_path = store_dir / f"manifest_{manifest_id}.json"
        if not manifest_path.exists():
            return None

        try:
            content = manifest_path.read_text(encoding="utf-8")
            return RemediationManifest.from_json(content)
        except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Unreadable remediation manifest %s: %s", manifest_path, exc)
            return None

    @classmethod
    def list_manifests(cls, target_dir: Path) -> list[dict[str, Any]]:
        """List summary history entries in reverse chronological order (pure read-only)."""
        store_dir = cls.resolve_store_dir(target_dir)
        if not store_dir.exists():
            return []

        history_path = store_dir / "history.json"
        if not history_path.exists():
            return []

        entries = cls._read_history(history_path)
        if entries is None:
            return []
        return sorted(entries, key=lambda x: x.get("created_at", ""), reverse=True)

    @staticmethod
    def _read_history(history_path: Path) -> Optional[list[dict[str, Any]]]:
        """Parse history.json; None (with a logged warning) if unreadable or malformed."""
        try:
            raw = json.loads(history_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Unreadable remediation history %s: %s", history_path, exc)
            return None
        if not isinstance(raw, list) or not all(isinstance(e, dict) for e in raw):
            logger.warning("Malformed remediation history %s: expected a list of entries", history_path)
            return None
        return raw

    @classmethod
    def _update_history_index(cls, store_dir: Path, manifest: RemediationManifest, manifest_filename: str) -> None:
        """Add entry to history.json index."""
        history_path = store_dir / "history.json"
        entries: list[dict[str, Any]] = []

        if history_path.exists():
            existing = cls._read_history(history_path)
            if existing is None:
                # Keep the damaged index for inspection instead of overwriting the
                # audit trail; the individual manifest files are untouched.
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                preserved = history_path.with_name(f"history.corrupt-{stamp}.json")
                history_path.replace(preserved)
                logger.warning("Preserved unreadable remediation history as %s and started a new index", preserved)
            else:
                entries = existing

        # Remove duplicate entry if exists
        entries = [e for e in entries if e.get("manifest_id") != manifest.manifest_id]

        summary_entry = {
            "manifest_id": manifest.manifest_id,
            "manifest_version": manifest.manifest_version,
            "created_at": manifest.created_at,
            "actor": manifest.actor,
            "decision": manifest.decision,
            "model_name": manifest.model_name,
            "before_score": manifest.before_score,
            "after_score": manifest.after_score,
            "score_delta": manifest.score_delta,
            "applied_count": len(manifest.applied_patches),
            "rejected_count": len(manifest.rejected_patches),
            "manifest_file": manifest_filename,
        }
        entries.append(summary_entry)
        entries = sorted(entries, key=lambda x: x.get("created_at", ""), reverse=True)

        history_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
