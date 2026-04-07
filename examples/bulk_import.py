"""
Example: bulk import a JSON file via the async import endpoint.

Usage:
    export EMILY_API_URL=https://emily.example.com
    export EMILY_API_KEY=emily_your_token_here
    python bulk_import.py incidents.json
"""

import os
import sys

from emily_sdk import EmilyClient


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <incidents.json>")
        sys.exit(1)

    base_url = os.environ.get("EMILY_API_URL")
    api_key = os.environ.get("EMILY_API_KEY")
    if not base_url or not api_key:
        print("Error: EMILY_API_URL and EMILY_API_KEY environment variables must be set")
        sys.exit(1)

    client = EmilyClient(base_url=base_url, api_key=api_key)

    print(f"Validating and uploading {sys.argv[1]}...")
    result = client.import_incidents(sys.argv[1])
    job_id = result["jobId"]
    print(f"Import job started: {job_id}")

    print("Waiting for completion...")
    final = client.wait_for_job(
        job_id,
        on_progress=lambda s: print(f"  {s.get('progress', 0)}% — processed {s.get('processed', 0)}/{s.get('total', '?')}"),
    )
    print(f"\nDone: {final.get('message')}")


if __name__ == "__main__":
    main()
