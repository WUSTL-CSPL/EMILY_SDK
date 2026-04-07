"""
Example: resumable batch upload of incidents.

Usage:
    export EMILY_API_URL=https://emily.example.com
    export EMILY_API_KEY=emily_your_token_here
    python resumable_upload.py incidents.json upload_state.json

If interrupted, just re-run the same command — it will skip incidents that already succeeded.
"""

import json
import os
import sys

from emily_sdk import EmilyClient


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <incidents.json> <state_file.json>")
        sys.exit(1)

    incidents_file, state_file = sys.argv[1], sys.argv[2]

    base_url = os.environ.get("EMILY_API_URL")
    api_key = os.environ.get("EMILY_API_KEY")
    if not base_url or not api_key:
        print("Error: EMILY_API_URL and EMILY_API_KEY environment variables must be set")
        sys.exit(1)

    with open(incidents_file, "r") as f:
        incidents = json.load(f)

    if not isinstance(incidents, list):
        print(f"Error: {incidents_file} must contain a JSON array")
        sys.exit(1)

    print(f"Loaded {len(incidents)} incidents from {incidents_file}")
    print(f"State file: {state_file}")
    print()

    client = EmilyClient(base_url=base_url, api_key=api_key)

    def progress(processed, total, current):
        print(f"  [{processed:>5}/{total}]", end="\r")

    try:
        result = client.create_incidents_resumable(
            incidents=incidents,
            state_file=state_file,
            on_progress=progress,
            save_every=10,
            skip_failed=False,
        )
        print()
        print(f"Done! Uploaded={result['uploaded']}, Skipped={result['skipped']}, Failed={result['failed']}")
    except KeyboardInterrupt:
        print()
        print("Interrupted. Re-run the same command to resume.")
        sys.exit(130)


if __name__ == "__main__":
    main()
