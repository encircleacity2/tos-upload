---
name: tos-upload
description: Upload local files (videos, images, any binary) to BytePlus TOS object storage and return a presigned URL by default. Use when the user says 上传到 TOS, 上传视频到对象存储, 传到 BytePlus TOS, 把这个视频/文件上传, upload to TOS, push to TOS bucket, 生成 TOS 链接, get a TOS presigned URL.
metadata:
  requires:
    bins: ["python3"]
    pip: ["tos"]
---

# BytePlus TOS Upload

Wraps the official BytePlus TOS Python SDK (`pip install tos`) to upload a local file in one shot and return a presigned GET URL (default 1h TTL). Handles large files via the SDK's `upload_file` (multipart + resumable checkpoint).

## When to use

- "把 `/path/to/video.mp4` 上传到 TOS,给我个链接"
- "传到 BytePlus 对象存储"
- "生成一个 TOS 预签名 URL,我要发给别人下载"
- Any time a local file needs to live on TOS and be reachable via URL.

## When NOT to use

- File needs to land in **飞书云盘 / Drive** → use `lark-drive` instead.
- File is already on TOS and you just need a fresh presigned URL → call `pre_signed_url` directly via a one-off Python snippet; no need to re-upload.
- Target storage is S3 / GCS / 火山引擎 VOD → different SDK.

## Prerequisites (one-time setup)

1. **Credentials.** Copy the template and fill in real values:

   ```bash
   cp tos_credentials.json.example tos_credentials.json
   # then edit tos_credentials.json with your AK / SK / bucket
   ```

   Default region preset is `ap-southeast-1` (endpoint `tos-ap-southeast-1.bytepluses.com`). For other regions see [Region & endpoint](https://docs.byteplus.com/en/docs/tos/docs-region-and-endpoint).

   Alternatively export env vars (they win over the JSON):
   `TOS_ACCESS_KEY`, `TOS_SECRET_KEY`, `TOS_ENDPOINT`, `TOS_REGION`, `TOS_BUCKET`.

2. **SDK.** Install if missing: `pip3 install tos`.

3. **First run — bucket selection.** If `bucket` is left empty in `tos_credentials.json`, the script will list all buckets under the account on the first upload and prompt you to choose one. The selection is saved back to `tos_credentials.json` automatically.

## How to invoke

Always shell out to the script — do not re-implement upload logic in chat:

```bash
python3 /path/to/tos-upload/scripts/upload.py <FILE> [flags]
```

Flags:

| Flag | Purpose | Default |
|---|---|---|
| `--key KEY` | Object key in the bucket | `uploads/YYYY/MM/DD/<rand>_<filename>` |
| `--bucket NAME` | Override bucket from credentials | from `tos_credentials.json` |
| `--expires SECONDS` | Presigned URL TTL | `3600` (1 hour) |
| `--public` | Skip presigning, return bucket-domain URL (needs public-read ACL) | off |
| `--content-type MIME` | Override Content-Type | guessed from extension |
| `--no-checkpoint` | Disable resumable checkpoint state | off |

The script prints a single JSON object to stdout:

```json
{
  "bucket": "my-bucket",
  "key": "uploads/2026/04/27/3f9a1c2b_demo.mp4",
  "url": "https://my-bucket.tos-ap-southeast-1.bytepluses.com/uploads/...?X-Tos-Signature=...",
  "expires_at": "2026-04-27T07:12:34+00:00",
  "size_bytes": 12345678,
  "content_type": "video/mp4"
}
```

Show the user the `url` and `expires_at`. For `--public` runs, `expires_at` is `null`.

## Typical flows

**Quick video upload, default 1h presigned URL:**
```bash
python3 scripts/upload.py /path/to/clip.mp4
```

**Custom key + 24h URL:**
```bash
python3 scripts/upload.py /tmp/foo.mp4 --key videos/launch/foo.mp4 --expires 86400
```

**Public bucket, no signing:**
```bash
python3 scripts/upload.py /tmp/poster.png --public
```

## Failure modes

- `Missing TOS credentials: …` → `tos_credentials.json` not filled or env vars missing.
- `TosServerError status=403 code=AccessDenied` → AK/SK wrong, bucket in different region, or bucket policy blocks the AK.
- `TosServerError status=404 code=NoSuchBucket` → bucket name typo or wrong region/endpoint pairing. Use `get_bucket_location` to confirm which endpoint the bucket belongs to.
- `tos package not installed` → `pip3 install tos` then retry.

Surface the SDK's `request_id` field to the user when reporting a server error — it's what BytePlus support needs to trace the call.
