"""
Upload tracker for resumable batch incident creation.

The tracker uses a local JSON state file to record which incidents have been
successfully uploaded. If the upload is interrupted, the user can re-run the
same command and the SDK will skip incidents that are already marked as uploaded.

Each incident is identified by a deterministic content hash (md5 of its JSON
representation), so re-running with the same input will resume from where it
left off.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class UploadTracker:
    """
    Tracks which incidents in a batch have been successfully uploaded.

    Usage:
        tracker = UploadTracker("upload_state.json")
        for incident in incidents:
            if tracker.is_uploaded(incident):
                continue
            upload(incident)
            tracker.mark_uploaded(incident, response.get("incident_id"))
        tracker.save()
    """

    SCHEMA_VERSION = 1

    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self._state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("schema_version") != self.SCHEMA_VERSION:
                    raise ValueError(
                        f"State file schema mismatch. Expected {self.SCHEMA_VERSION}, "
                        f"got {data.get('schema_version')}"
                    )
                return data
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Invalid state file {self.state_file}: {e}")
        return {
            "schema_version": self.SCHEMA_VERSION,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "uploaded": {},  # hash -> {incident_id, uploaded_at}
        }

    @staticmethod
    def _hash_incident(incident: Dict[str, Any]) -> str:
        """Compute a deterministic hash of an incident for tracking purposes."""
        canonical = json.dumps(incident, sort_keys=True, separators=(",", ":"))
        return hashlib.md5(canonical.encode("utf-8")).hexdigest()

    def is_uploaded(self, incident: Dict[str, Any]) -> bool:
        return self._hash_incident(incident) in self._state["uploaded"]

    def mark_uploaded(self, incident: Dict[str, Any], incident_id: Optional[str] = None) -> None:
        h = self._hash_incident(incident)
        self._state["uploaded"][h] = {
            "incident_id": incident_id,
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
        }

    def save(self) -> None:
        """Persist the state file to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp then rename
        tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)
        tmp.replace(self.state_file)

    def uploaded_count(self) -> int:
        return len(self._state["uploaded"])

    def get_uploaded_id(self, incident: Dict[str, Any]) -> Optional[str]:
        entry = self._state["uploaded"].get(self._hash_incident(incident))
        return entry.get("incident_id") if entry else None

    def reset(self) -> None:
        """Clear all tracked uploads."""
        self._state["uploaded"] = {}
        self.save()
