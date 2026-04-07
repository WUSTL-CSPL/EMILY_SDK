"""
EMILY API client.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, Iterable, List, Optional

import requests

from emily_sdk.exceptions import APIError, AuthError, ValidationError
from emily_sdk.tracker import UploadTracker


class EmilyClient:
    """
    High-level client for the EMILY incident management API.

    Args:
        base_url: Base URL of the EMILY API (e.g. "https://emily.example.com").
        api_key: API token (`emily_...`) for authentication.
        timeout: Request timeout in seconds (default 30).
    """

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        if not base_url:
            raise ValidationError("base_url is required")
        if not api_key:
            raise ValidationError("api_key is required")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": api_key})

    # =========================================================================
    # Internal request helper
    # =========================================================================

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise APIError(f"Network error: {e}")

        if resp.status_code == 401:
            raise AuthError("Authentication failed: invalid or expired API key")
        if resp.status_code == 403:
            raise AuthError("Forbidden: API key lacks required permissions")
        if not resp.ok:
            raise APIError(
                f"HTTP {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
                response_body=resp.text,
            )

        # The export endpoint returns binary content, not JSON
        ct = resp.headers.get("Content-Type", "")
        if "application/json" in ct:
            try:
                return resp.json()
            except ValueError:
                raise APIError(f"Invalid JSON response: {resp.text[:500]}")
        return resp

    # =========================================================================
    # Single incident creation
    # =========================================================================

    def create_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a single incident.

        Args:
            incident: Dict of incident fields. See API documentation for required fields.

        Returns:
            The API response payload (typically contains incident_id).

        Raises:
            ValidationError: if `incident` is empty.
            APIError: on HTTP failure.
        """
        if not incident:
            raise ValidationError("incident dict cannot be empty")

        result = self._request("POST", "/api/user/incident/create", json=incident)
        # API wraps responses in {code, message, data}
        if isinstance(result, dict) and "code" in result:
            if result.get("code") != 200:
                raise APIError(f"API error: {result.get('message')}")
            return result.get("data", {})
        return result

    # =========================================================================
    # Resumable batch creation
    # =========================================================================

    def create_incidents_resumable(
        self,
        incidents: Iterable[Dict[str, Any]],
        state_file: str,
        on_progress: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        save_every: int = 5,
        skip_failed: bool = False,
    ) -> Dict[str, int]:
        """
        Create incidents one-by-one with resumable progress tracking.

        Each incident is hashed (md5 of its JSON content) and the SDK records
        the hash in `state_file` after a successful upload. If the process is
        interrupted (Ctrl-C, crash, network error), re-running with the same
        `incidents` and `state_file` will skip incidents that already succeeded.

        Args:
            incidents: Iterable of incident dicts.
            state_file: Path to a local JSON file used to persist upload state.
            on_progress: Optional callback (uploaded, total, current_incident) called after each upload.
            save_every: Save the state file every N successful uploads (default 5). Lower = safer but slower.
            skip_failed: If True, log failures and continue. If False (default), raise on first error.

        Returns:
            Dict with counts: {"uploaded": N, "skipped": M, "failed": K}.
        """
        tracker = UploadTracker(state_file)
        incidents_list = list(incidents)  # so we can compute total

        total = len(incidents_list)
        uploaded = 0
        skipped = 0
        failed = 0

        try:
            for i, incident in enumerate(incidents_list):
                if tracker.is_uploaded(incident):
                    skipped += 1
                    continue

                try:
                    result = self.create_incident(incident)
                    incident_id = result.get("incident_id") if isinstance(result, dict) else None
                    tracker.mark_uploaded(incident, incident_id)
                    uploaded += 1

                    if on_progress:
                        on_progress(uploaded + skipped, total, incident)

                    if uploaded % save_every == 0:
                        tracker.save()
                except Exception as e:
                    failed += 1
                    if not skip_failed:
                        tracker.save()
                        raise APIError(f"Failed at incident {i}: {e}")
        finally:
            tracker.save()

        return {"uploaded": uploaded, "skipped": skipped, "failed": failed, "total": total}

    # =========================================================================
    # Bulk import (well-formed JSON file only)
    # =========================================================================

    def import_incidents(
        self,
        json_file: str,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        Import incidents from a JSON file via the bulk import endpoint.

        The file must contain a JSON array of incident objects. The SDK validates
        that the file is well-formed JSON and that the top-level value is a list
        before uploading.

        Args:
            json_file: Path to the JSON file to import.
            validate: If True (default), parse and validate the file locally before uploading.

        Returns:
            The API response (typically a job ID for tracking the async import).
        """
        path = Path(json_file)
        if not path.exists():
            raise ValidationError(f"File not found: {json_file}")
        if not path.is_file():
            raise ValidationError(f"Not a file: {json_file}")
        if path.stat().st_size == 0:
            raise ValidationError(f"File is empty: {json_file}")

        if validate:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Malformed JSON in {json_file}: {e}")
            if not isinstance(data, list):
                raise ValidationError(
                    f"JSON root must be an array of incidents, got {type(data).__name__}"
                )
            if len(data) == 0:
                raise ValidationError("JSON array is empty")

        with open(path, "rb") as f:
            files = {"file": (path.name, f, "application/json")}
            result = self._request("POST", "/api/user/incident/import", files=files)

        if isinstance(result, dict) and "code" in result:
            if result.get("code") != 200:
                raise APIError(f"Import failed: {result.get('message')}")
            return result.get("data", {})
        return result

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Poll the status of an async job (e.g. an import)."""
        result = self._request("GET", f"/api/user/jobs/{job_id}")
        if isinstance(result, dict) and "code" in result:
            return result.get("data", {})
        return result

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 1.0,
        max_wait: float = 600.0,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Block until an async job completes or fails.

        Args:
            job_id: The job ID returned by import_incidents() or similar.
            poll_interval: Seconds between status checks (default 1).
            max_wait: Maximum total wait time in seconds (default 600 = 10 min).
            on_progress: Optional callback called with each status snapshot.

        Returns:
            The final job status dict.
        """
        import time
        start = time.time()
        while time.time() - start < max_wait:
            status = self.get_job_status(job_id)
            if on_progress:
                on_progress(status)
            state = status.get("state")
            if state == "COMPLETED":
                return status
            if state == "FAILED":
                raise APIError(f"Job failed: {status.get('error', 'unknown error')}")
            time.sleep(poll_interval)
        raise APIError(f"Job did not complete within {max_wait} seconds")

    # =========================================================================
    # Export
    # =========================================================================

    def export_incidents(
        self,
        start_time: str,
        end_time: str,
        format: str = "csv",
        org_id: Optional[str] = None,
        site_id: Optional[str] = None,
        instrument_id: Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> bytes:
        """
        Export incidents within a time range.

        Args:
            start_time: ISO-8601 start (e.g. "2026-01-01T00:00:00Z").
            end_time: ISO-8601 end (e.g. "2026-12-31T23:59:59Z").
            format: One of "csv", "json", "excel".
            org_id: Optional org filter.
            site_id: Optional site filter.
            instrument_id: Optional instrument filter.
            output_file: If provided, the export will be written to this path.

        Returns:
            The raw bytes of the export file.
        """
        if format not in ("csv", "json", "excel"):
            raise ValidationError(f"format must be 'csv', 'json', or 'excel'; got '{format}'")

        body = {
            "startTime": start_time,
            "endTime": end_time,
            "format": format,
        }
        if org_id: body["orgId"] = org_id
        if site_id: body["siteId"] = site_id
        if instrument_id: body["instrumentId"] = instrument_id

        resp = self._request("POST", "/api/user/incident/export", json=body)
        if isinstance(resp, dict):
            # Got JSON instead of binary — likely an error wrapped in CommonResult
            raise APIError(f"Unexpected JSON response: {resp}")

        content = resp.content
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(content)
        return content
