#!/usr/bin/env python3
"""Download event cover images, upload them to Supabase Storage and set
public.events.cover_image for each es/en pair.

Dry run (default) only prints the plan. Pass --apply to upload and update.

Env:
  SUPABASE_SERVICE_ROLE_KEY  required for --apply
  SUPABASE_URL               defaults to the tcdjxxnjfqnfbnseuhsa project
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://tcdjxxnjfqnfbnseuhsa.supabase.co"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"


def request(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def public_url(base, bucket, path):
    return f"{base}/storage/v1/object/public/{bucket}/{urllib.parse.quote(path)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapping", nargs="?", default="data/event_images_quepasa.json")
    ap.add_argument("--apply", action="store_true", help="upload and run the UPDATEs")
    ap.add_argument("--download-dir", default="downloads")
    args = ap.parse_args()

    base = os.environ.get("SUPABASE_URL", DEFAULT_URL).rstrip("/")
    cfg = json.loads(Path(args.mapping).read_text())
    bucket = cfg["bucket"]
    entries = [e for e in cfg["entries"] if e["include"]]
    skipped = [e for e in cfg["entries"] if not e["include"]]

    for e in entries:
        ids = "/".join(map(str, e["ids"]))
        print(f"{ids:<8} {e['event']}\n         {e['image_url']}\n      -> {public_url(base, bucket, e['storage_path'])}")
    for e in skipped:
        print(f"SKIP {'/'.join(map(str, e['ids']))} {e['event']}: {e['note']}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to upload and update.")
        return

    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        sys.exit("SUPABASE_SERVICE_ROLE_KEY is not set")
    auth = {"apikey": key, "Authorization": f"Bearer {key}"}

    # 1. Download and upload every distinct image before touching the table.
    out = Path(args.download_dir)
    out.mkdir(exist_ok=True)
    uploaded = set()
    for e in entries:
        path = e["storage_path"]
        if path in uploaded:
            continue
        status, headers, body = request("GET", e["image_url"], headers={"User-Agent": UA})
        ctype = headers.get("Content-Type", "").split(";")[0]
        if status != 200 or not ctype.startswith("image/"):
            sys.exit(f"download failed {e['image_url']}: {status} {ctype}")
        (out / Path(path).name).write_bytes(body)

        ctype = ctype or mimetypes.guess_type(path)[0] or "image/jpeg"
        status, _, resp = request(
            "POST",
            f"{base}/storage/v1/object/{bucket}/{urllib.parse.quote(path)}",
            data=body,
            headers={**auth, "Content-Type": ctype, "x-upsert": "false"},
        )
        if status not in (200, 201):
            sys.exit(f"upload failed {path}: {status} {resp[:300]!r}")
        print(f"uploaded {path} ({len(body)} bytes)")
        uploaded.add(path)

    # 2. UPDATE cover_image for both language rows of each event.
    for e in entries:
        url = public_url(base, bucket, e["storage_path"])
        ids = ",".join(map(str, e["ids"]))
        status, _, resp = request(
            "PATCH",
            f"{base}/rest/v1/events?id=in.({ids})",
            data=json.dumps({"cover_image": url}).encode(),
            headers={**auth, "Content-Type": "application/json", "Prefer": "return=representation"},
        )
        rows = json.loads(resp) if status == 200 else []
        if len(rows) != len(e["ids"]):
            sys.exit(f"update {ids} touched {len(rows)} rows (status {status}): {resp[:300]!r}")
        print(f"updated {ids} -> {url}")


if __name__ == "__main__":
    main()
