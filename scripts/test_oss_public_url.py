"""Smoke test Aliyun OSS upload and public URL access.

Reads OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME, and
OSS_ENDPOINT from environment variables.
"""

from __future__ import annotations

import base64
from email.utils import formatdate
import hashlib
import hmac
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"missing env: {name}")
    return value


def _oss_authorization(
    access_key_id: str,
    access_key_secret: str,
    method: str,
    content_type: str,
    date: str,
    bucket: str,
    object_key: str,
    headers: dict[str, str],
) -> str:
    oss_headers = ""
    for key in sorted(k.lower() for k in headers if k.lower().startswith("x-oss-")):
        oss_headers += f"{key}:{headers[key]}\n"

    resource = f"/{bucket}/{object_key}"
    string_to_sign = f"{method}\n\n{content_type}\n{date}\n{oss_headers}{resource}"
    digest = hmac.new(
        access_key_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("ascii")
    return f"OSS {access_key_id}:{signature}"


def main() -> None:
    access_key_id = _required("OSS_ACCESS_KEY_ID")
    access_key_secret = _required("OSS_ACCESS_KEY_SECRET")
    bucket = _required("OSS_BUCKET_NAME")
    endpoint = _required("OSS_ENDPOINT").removeprefix("https://").removeprefix("http://")

    object_key = f"suno_music/output/oss_smoke_test_{int(time.time())}.txt"
    body = b"suno oss public url smoke test\n"
    content_type = "text/plain"
    date = formatdate(usegmt=True)
    host = f"{bucket}.{endpoint}"
    url = f"https://{host}/{object_key}"
    oss_headers = {"x-oss-object-acl": "public-read"}
    headers = {
        "Date": date,
        "Host": host,
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
        **oss_headers,
    }
    headers["Authorization"] = _oss_authorization(
        access_key_id,
        access_key_secret,
        "PUT",
        content_type,
        date,
        bucket,
        object_key,
        oss_headers,
    )

    request = Request(url, data=body, headers=headers, method="PUT")
    try:
        with urlopen(request, timeout=30) as response:
            print(f"PUT {response.status}")
    except HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"))
        raise

    with urlopen(Request(url, method="GET"), timeout=30) as response:
        downloaded = response.read()
        print(f"GET {response.status}")
        print(f"URL {url}")
        print(f"BODY {downloaded.decode('utf-8', errors='replace').strip()}")


if __name__ == "__main__":
    main()
