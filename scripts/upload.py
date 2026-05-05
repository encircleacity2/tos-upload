#!/usr/bin/env python3
"""Upload a file to BytePlus TOS and emit a JSON result with a presigned URL.

Usage:
    python3 upload.py <file_path> [--key OBJECT_KEY] [--bucket BUCKET]
                                  [--expires SECONDS] [--public]
                                  [--content-type MIME]

Reads credentials from (in priority order):
    1. Environment variables: TOS_ACCESS_KEY, TOS_SECRET_KEY,
       TOS_ENDPOINT, TOS_REGION, TOS_BUCKET
    2. tos_credentials.json next to this skill

On first run (no bucket configured), lists all buckets in the region and
prompts the user to choose one, then saves it to tos_credentials.json.

Output: a single JSON object on stdout with bucket/key/url/size/expires_at.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path

try:
    import tos
except ImportError:
    sys.stderr.write(
        "tos package not installed. Run: pip install tos\n"
    )
    sys.exit(2)


SKILL_ROOT = Path(__file__).resolve().parent.parent
CREDS_FILE = SKILL_ROOT / "tos_credentials.json"


def load_credentials() -> dict:
    creds: dict = {}
    if CREDS_FILE.exists():
        try:
            creds = json.loads(CREDS_FILE.read_text())
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Failed to parse {CREDS_FILE}: {e}\n")
            sys.exit(2)

    env_map = {
        "access_key": "TOS_ACCESS_KEY",
        "secret_key": "TOS_SECRET_KEY",
        "endpoint": "TOS_ENDPOINT",
        "region": "TOS_REGION",
        "bucket": "TOS_BUCKET",
    }
    for field, env_name in env_map.items():
        if os.environ.get(env_name):
            creds[field] = os.environ[env_name]

    missing = [k for k in ("access_key", "secret_key", "endpoint", "region")
               if not creds.get(k)]
    if missing:
        sys.stderr.write(
            "Missing TOS credentials: " + ", ".join(missing) + "\n"
            f"Fill {CREDS_FILE} or set TOS_ACCESS_KEY / TOS_SECRET_KEY / "
            "TOS_ENDPOINT / TOS_REGION (and TOS_BUCKET).\n"
        )
        sys.exit(2)
    return creds


def select_bucket(client: tos.TosClientV2, creds: dict) -> str:
    """List buckets and prompt the user to choose one; saves choice to creds file."""
    sys.stderr.write("\nNo default bucket configured. Listing available buckets...\n\n")
    try:
        resp = client.list_buckets()
        buckets = [b.name for b in resp.buckets]
    except Exception as e:
        sys.stderr.write(f"Failed to list buckets: {e}\n")
        sys.exit(1)

    if not buckets:
        sys.stderr.write("No buckets found under this account.\n")
        sys.exit(1)

    sys.stderr.write("Available buckets:\n")
    for i, name in enumerate(buckets, 1):
        sys.stderr.write(f"  {i:3}. {name}\n")

    sys.stderr.write(
        f"\nWhich bucket should be used for uploads? "
        f"Enter a number (1-{len(buckets)}) or type a bucket name: "
    )
    choice = input().strip()

    if choice.isdigit():
        idx = int(choice) - 1
        if idx < 0 or idx >= len(buckets):
            sys.stderr.write(f"Invalid selection: {choice}\n")
            sys.exit(1)
        selected = buckets[idx]
    else:
        selected = choice

    # Save to credentials file (env-var overrides are not persisted)
    if CREDS_FILE.exists():
        try:
            saved = json.loads(CREDS_FILE.read_text())
        except json.JSONDecodeError:
            saved = {}
        saved["bucket"] = selected
        CREDS_FILE.write_text(json.dumps(saved, indent=2, ensure_ascii=False) + "\n")
        sys.stderr.write(f"\nSaved default bucket '{selected}' to {CREDS_FILE}\n\n")

    return selected


def build_object_key(file_path: Path, override: str | None) -> str:
    if override:
        return override
    today = _dt.date.today().strftime("%Y/%m/%d")
    suffix = uuid.uuid4().hex[:8]
    return f"uploads/{today}/{suffix}_{file_path.name}"


def main() -> int:
    p = argparse.ArgumentParser(description="Upload a file to BytePlus TOS.")
    p.add_argument("file", help="Local file path to upload.")
    p.add_argument("--key", help="Object key in the bucket. Default: uploads/YYYY/MM/DD/<rand>_<filename>.")
    p.add_argument("--bucket", help="Override bucket name from credentials.")
    p.add_argument("--expires", type=int, default=3600,
                   help="Presigned URL TTL in seconds (default 3600).")
    p.add_argument("--public", action="store_true",
                   help="Skip presigning; return the bucket-domain URL (requires public-read ACL).")
    p.add_argument("--content-type", help="Override content type. Default: guessed from extension.")
    p.add_argument("--no-checkpoint", action="store_true",
                   help="Disable resumable checkpoint (use for tiny files or stateless runs).")
    args = p.parse_args()

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.is_file():
        sys.stderr.write(f"Not a file: {file_path}\n")
        return 2

    creds = load_credentials()

    client = tos.TosClientV2(
        ak=creds["access_key"],
        sk=creds["secret_key"],
        endpoint=creds["endpoint"],
        region=creds["region"],
    )

    # Resolve bucket: CLI flag > credentials/env > interactive selection
    bucket = args.bucket or creds.get("bucket") or ""
    if not bucket:
        bucket = select_bucket(client, creds)

    key = build_object_key(file_path, args.key)
    content_type = args.content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    size = file_path.stat().st_size

    try:
        client.upload_file(
            bucket=bucket,
            key=key,
            file_path=str(file_path),
            task_num=4,
            enable_checkpoint=not args.no_checkpoint,
            content_type=content_type,
        )

        if args.public:
            url = f"https://{bucket}.{creds['endpoint']}/{key}"
            expires_at = None
        else:
            signed = client.pre_signed_url(
                http_method=tos.HttpMethodType.Http_Method_Get,
                bucket=bucket,
                key=key,
                expires=args.expires,
            )
            url = signed.signed_url
            expires_at = (_dt.datetime.now(_dt.timezone.utc)
                          + _dt.timedelta(seconds=args.expires)).isoformat()

    except tos.exceptions.TosClientError as e:
        sys.stderr.write(f"TOS client error: {e.message}\n")
        return 1
    except tos.exceptions.TosServerError as e:
        sys.stderr.write(
            f"TOS server error: status={e.status_code} code={e.code} "
            f"message={e.message} request_id={e.request_id}\n"
        )
        return 1

    result = {
        "bucket": bucket,
        "key": key,
        "url": url,
        "expires_at": expires_at,
        "size_bytes": size,
        "content_type": content_type,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
