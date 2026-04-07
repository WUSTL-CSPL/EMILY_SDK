"""
Example: export incidents to a CSV file.

Usage:
    export EMILY_API_URL=https://emily.example.com
    export EMILY_API_KEY=emily_your_token_here
    python export.py 2026-01-01T00:00:00Z 2026-12-31T23:59:59Z incidents.csv
"""

import os
import sys

from emily_sdk import EmilyClient


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <start_iso> <end_iso> <output_file>")
        print(f"Example: {sys.argv[0]} 2026-01-01T00:00:00Z 2026-12-31T23:59:59Z out.csv")
        sys.exit(1)

    start, end, output = sys.argv[1], sys.argv[2], sys.argv[3]

    base_url = os.environ.get("EMILY_API_URL")
    api_key = os.environ.get("EMILY_API_KEY")
    if not base_url or not api_key:
        print("Error: EMILY_API_URL and EMILY_API_KEY environment variables must be set")
        sys.exit(1)

    client = EmilyClient(base_url=base_url, api_key=api_key)

    # Determine format from extension
    ext = output.lower().rsplit(".", 1)[-1]
    fmt = {"csv": "csv", "json": "json", "xlsx": "excel"}.get(ext, "csv")

    print(f"Exporting incidents from {start} to {end} as {fmt}...")
    client.export_incidents(
        start_time=start,
        end_time=end,
        format=fmt,
        output_file=output,
    )
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()
