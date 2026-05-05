# tos-upload

A [Claude Code](https://claude.ai/code) skill that uploads local files to [BytePlus TOS](https://www.byteplus.com/en/product/tos) object storage and returns a presigned GET URL.

## Features

- Single-command upload: `python3 scripts/upload.py <file>`
- Presigned URL output (default 1h TTL, configurable)
- Multipart + resumable checkpoint for large files
- First-run interactive bucket selection — lists available buckets and saves your choice
- Credentials via JSON file or environment variables

## Setup

1. **Install the SDK:**
   ```bash
   pip3 install tos
   ```

2. **Configure credentials:**
   ```bash
   cp tos_credentials.json.example tos_credentials.json
   # Edit tos_credentials.json — fill in access_key, secret_key, endpoint, region
   # Leave bucket empty to get an interactive bucket picker on first run
   ```

   Or use environment variables:
   ```bash
   export TOS_ACCESS_KEY="<ak>"
   export TOS_SECRET_KEY="<sk>"
   export TOS_ENDPOINT="tos-ap-southeast-1.bytepluses.com"
   export TOS_REGION="ap-southeast-1"
   export TOS_BUCKET="<bucket>"
   ```

   See [BytePlus TOS Region & Endpoint docs](https://docs.byteplus.com/en/docs/tos/docs-region-and-endpoint) for available regions.

## Usage

```bash
# Basic upload (1h presigned URL)
python3 scripts/upload.py /path/to/file.mp4

# Custom object key + 24h URL
python3 scripts/upload.py /path/to/file.mp4 --key videos/demo.mp4 --expires 86400

# Public URL (no signing; requires public-read bucket ACL)
python3 scripts/upload.py /path/to/poster.png --public
```

Output (JSON on stdout):
```json
{
  "bucket": "my-bucket",
  "key": "uploads/2026/05/05/3f9a1c2b_file.mp4",
  "url": "https://my-bucket.tos-ap-southeast-1.bytepluses.com/uploads/...?X-Tos-Signature=...",
  "expires_at": "2026-05-06T07:00:00+00:00",
  "size_bytes": 12345678,
  "content_type": "video/mp4"
}
```

## Using as a Claude Code skill

Install by placing this directory under `~/.claude/skills/tos-upload/`. Claude Code will auto-discover it and invoke `scripts/upload.py` when you ask to upload files to TOS.

## License

MIT
