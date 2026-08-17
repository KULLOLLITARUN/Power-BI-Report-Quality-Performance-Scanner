"""Backup and rollback management for PBIP Sentinel remediation."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from pbiscan.remediation.models import compute_file_sha256


class BackupManager:
    """Manages transactional backups, atomic rollback, and restoration verification."""

    @staticmethod
    def create_backup(project_path: Path) -> Path:
        """Create a timestamped backup directory of the PBIP project."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_dir = project_path.parent / f"{project_path.name}.bak_{timestamp}"
        
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
            
        shutil.copytree(project_path, backup_dir)
        return backup_dir

    @staticmethod
    def restore_backup(backup_path: Path, target_path: Path) -> bool:
        """Restore target directory from backup."""
        if not backup_path.exists():
            return False

        if target_path.exists():
            shutil.rmtree(target_path)

        shutil.copytree(backup_path, target_path)
        return True

    @staticmethod
    def verify_restoration(backup_path: Path, target_path: Path) -> bool:
        """Verify that restored target is 100% byte-for-byte identical to the backup."""
        if not backup_path.exists() or not target_path.exists():
            return False

        backup_files = {p.relative_to(backup_path): p for p in backup_path.glob("**/*") if p.is_file()}
        target_files = {p.relative_to(target_path): p for p in target_path.glob("**/*") if p.is_file()}

        if set(backup_files.keys()) != set(target_files.keys()):
            return False

        for rel_path, b_file in backup_files.items():
            t_file = target_files[rel_path]
            if compute_file_sha256(b_file) != compute_file_sha256(t_file):
                return False

        return True

    @staticmethod
    def get_backup_metadata(backup_path: Path) -> dict:
        """Extract portable audit metadata from a backup directory."""
        if not backup_path.exists():
            return {
                "backup_id": None,
                "backup_location": None,
                "backup_hash": None,
                "files_backed_up": [],
            }

        files = sorted([str(p.relative_to(backup_path)) for p in backup_path.glob("**/*") if p.is_file()])
        from pbiscan.remediation.models import compute_sha256
        combined_hashes = "".join(compute_file_sha256(backup_path / f) for f in files)
        backup_hash = compute_sha256(combined_hashes) if files else ""
        backup_id = f"BKP-{backup_path.name.split('.bak_')[-1] if '.bak_' in backup_path.name else 'MANUAL'}-{backup_hash[:8]}"

        return {
            "backup_id": backup_id,
            "backup_location": str(backup_path),
            "backup_hash": backup_hash,
            "files_backed_up": files,
        }
