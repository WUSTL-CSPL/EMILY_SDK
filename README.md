# EMILY Python SDK

A Python SDK for the EMILY incident management API. Provides clean interfaces for:

- Creating single incidents
- Resumable batch creation with stop/resume support
- Bulk import from JSON files (with local validation)
- Exporting incidents to CSV/JSON/Excel

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from emily_sdk import EmilyClient

client = EmilyClient(
    base_url="https://cspl-emily.engr.wustl.edu",
    api_key="emily_your_token_here",
)
```

## API Reference

### 1. Create a single incident

```python
incident = {
    "orgId": "aaaaaaaa-0000-0000-0000-000000000001",
    "siteId": "5c9d5ccd-7f7f-4d22-8be0-84832e4715d0",
    "instrumentId": "8111b7d2-82b4-4bad-88ba-d5d29d4a3281",
    "dataType": "spectrometer",
    "startTime": "2026-04-01T19:33:11Z",
    "endTime": "2026-04-01T20:33:10Z",
    "fLowHz": 1947470781,
    "fHighHz": 2003332724,
    "intensityKind": "power_dbm",
    "intensityVal": -85.5,
    "directional": False,
    "ra": 0,
    "dec": 0,
    "az": 0,
    "el": 90,
    "timezone": "UTC",
    "tStartLocal": "2026-04-01T19:33:11Z",
    "tEndLocal": "2026-04-01T20:33:10Z",
    "privacyTier": "internal",
}

result = client.create_incident(incident)
print(f"Created incident: {result['incident_id']}")
```

### 2. Resumable batch creation

Upload many incidents one at a time, with automatic stop/resume support.
If the script crashes or you press Ctrl-C, simply re-run the same command
and it will skip incidents that already succeeded.

```python
incidents = [
    {"orgId": "...", "siteId": "...", ...},
    {"orgId": "...", "siteId": "...", ...},
    # ... 1000 more
]

def progress(processed, total, current):
    print(f"  [{processed}/{total}]")

result = client.create_incidents_resumable(
    incidents=incidents,
    state_file="upload_state.json",   # local progress file
    on_progress=progress,
    save_every=5,                     # persist state every 5 successful uploads
    skip_failed=False,                # raise on first error (set True to continue past failures)
)

print(f"Uploaded: {result['uploaded']}, Skipped (already done): {result['skipped']}, Failed: {result['failed']}")
```

**How it works**: Each incident is hashed (md5 of its canonical JSON) and recorded
in `upload_state.json` after a successful upload. On the next run, the SDK skips
any incident whose hash is already in the state file.

To start fresh, delete the state file or call `tracker.reset()`.

### 3. Bulk import from a JSON file

Uploads a JSON file containing an array of incidents to the bulk import endpoint.
The file is validated locally before upload (must be well-formed JSON, must be an array).

```python
result = client.import_incidents("incidents_batch.json")
print(f"Import job started: {result['jobId']}")

# Optional: poll until the import completes
final = client.wait_for_job(
    result["jobId"],
    on_progress=lambda s: print(f"  {s['progress']}% — {s.get('processed', 0)} processed"),
)
print(f"Import done: {final['message']}")
```

**Local validation**: the SDK rejects the file before upload if:
- The file doesn't exist or is empty
- The content is malformed JSON
- The root value is not an array
- The array is empty

Pass `validate=False` to skip local validation (let the server handle it).

### 4. Export incidents

```python
# Get bytes back
data = client.export_incidents(
    start_time="2026-01-01T00:00:00Z",
    end_time="2026-12-31T23:59:59Z",
    format="csv",  # or "json", "excel"
    org_id="aaaaaaaa-0000-0000-0000-000000000001",  # optional
)

# Or write directly to a file
client.export_incidents(
    start_time="2026-01-01T00:00:00Z",
    end_time="2026-12-31T23:59:59Z",
    format="excel",
    output_file="exports/incidents_2026.xlsx",
)
```

## Error Handling

```python
from emily_sdk import EmilyClient, AuthError, ValidationError, APIError

client = EmilyClient(base_url="...", api_key="...")

try:
    client.create_incident({})  # empty dict
except ValidationError as e:
    print(f"Bad input: {e}")
except AuthError as e:
    print(f"Auth problem: {e}")
except APIError as e:
    print(f"API error (status {e.status_code}): {e}")
```

## Getting an API Key

API tokens are managed in the EMILY web UI:

1. Log in to the EMILY portal
2. Click **API Tokens** in the sidebar
3. Click **Create Token**, give it a name and expiration
4. Copy the token (it's shown only once — store it securely)

The token format is `emily_<64-hex-chars>`.

## License

MIT
