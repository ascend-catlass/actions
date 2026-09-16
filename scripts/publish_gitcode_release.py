#!/usr/bin/env python3
"""Attach a validated wheel bundle to the existing GitCode tag release."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_ROOT = "https://api.gitcode.com/api/v5"


class GitCodeClient:
    def __init__(self, owner: str, repo: str, token: str) -> None:
        self.repository_url = f"{API_ROOT}/repos/{owner}/{repo}"
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "ascend-catlass-release-publisher",
        }

    def request_json(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None
        headers = dict(self.headers)
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.repository_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"GitCode API {method} {path} failed: {error.code} {detail}") from error

    def get_release(self, tag: str) -> dict | None:
        path = f"/releases/tags/{urllib.parse.quote(tag, safe='')}"
        request = urllib.request.Request(
            f"{self.repository_url}{path}", headers=self.headers, method="GET"
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"GitCode API GET {path} failed: {error.code} {detail}") from error

    def create_release(self, tag: str, name: str, notes: str) -> dict:
        return self.request_json(
            "POST",
            "/releases",
            {"tag_name": tag, "name": name, "body": notes, "release_status": "latest"},
        )

    def upload_file(self, tag: str, path: Path) -> None:
        query = urllib.parse.urlencode({"file_name": path.name})
        upload = self.request_json(
            "GET", f"/releases/{urllib.parse.quote(tag, safe='')}/upload_url?{query}"
        )
        upload_url = upload.get("url")
        upload_headers = upload.get("headers")
        if not isinstance(upload_url, str) or not isinstance(upload_headers, dict):
            raise RuntimeError(f"GitCode returned an invalid upload description for {path.name}")
        headers = {str(key): str(value) for key, value in upload_headers.items()}
        headers.setdefault("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        request = urllib.request.Request(
            upload_url, data=path.read_bytes(), headers=headers, method="PUT"
        )
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"GitCode upload failed for {path.name}: HTTP {response.status}")
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"GitCode upload failed for {path.name}: {error.code} {detail}") from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_sha256(url: str) -> str:
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "ascend-catlass-release-publisher"})
    with urllib.request.urlopen(request, timeout=900) as response:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish(client: GitCodeClient, tag: str, version: str, bundle: Path) -> None:
    wheel_dir = bundle / "wheels"
    files = sorted(wheel_dir.glob("*.whl")) + [bundle / "SHA256SUMS"]
    if len(files) != 9 or any(not path.is_file() for path in files):
        raise RuntimeError("Release bundle must contain eight wheels and SHA256SUMS")

    notes = (bundle / "release-notes.md").read_text(encoding="utf-8")
    release = client.get_release(tag)
    if release is None:
        release = client.create_release(tag, f"ascend-catlass-dsl {version}", notes)
        print(f"Created GitCode release for {tag}")
    elif release.get("tag_name") != tag:
        raise RuntimeError(f"GitCode returned the wrong release for {tag}")

    assets = {asset.get("name"): asset for asset in release.get("assets", [])}
    for path in files:
        existing = assets.get(path.name)
        if existing is not None:
            url = existing.get("browser_download_url")
            if not isinstance(url, str) or remote_sha256(url) != sha256(path):
                raise RuntimeError(f"GitCode release contains a conflicting asset: {path.name}")
            print(f"Reusing matching GitCode asset: {path.name}")
            continue
        client.upload_file(tag, path)
        print(f"Uploaded GitCode asset: {path.name}")

    expected = {path.name for path in files}
    for attempt in range(6):
        refreshed = client.get_release(tag) or {}
        names = {asset.get("name") for asset in refreshed.get("assets", [])}
        if expected <= names:
            print(f"Verified {len(expected)} GitCode release assets for {tag}")
            return
        if attempt < 5:
            time.sleep(2**attempt)
    missing = sorted(expected - names)
    raise RuntimeError(f"GitCode release did not expose uploaded assets: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("GITCODE_RELEASE_TOKEN")
    if not token:
        print("error: GITCODE_RELEASE_TOKEN is not configured", file=sys.stderr)
        return 1
    try:
        publish(
            GitCodeClient(args.owner, args.repo, token),
            args.tag,
            args.version,
            args.bundle,
        )
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
