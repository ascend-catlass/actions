"""Shared authenticated GitCode REST transport and generic action entrypoint."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.gitcode.com/api/v5"


class GitCodeAPI:
    def __init__(self, token):
        if not token:
            raise ValueError("GitCode token is required")
        self.headers = {"Authorization": f"Bearer {token}", "PRIVATE-TOKEN": token,
                        "Accept": "application/json", "User-Agent": "ascend-catlass-actions"}

    def request(self, method, path, body=None, encoding="form"):
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise ValueError("Unsupported GitCode method")
        if not path.startswith("/") or path.startswith("//") or ".." in path or "\n" in path:
            raise ValueError("GitCode path must be relative to the fixed v5 API root")
        if encoding not in {"form", "json"}:
            raise ValueError("Body encoding must be form or json")
        headers, data = dict(self.headers), None
        if body is not None:
            if not isinstance(body, dict) or "access_token" in body:
                raise ValueError("Request body must be an object without credentials")
            if encoding == "json":
                data = json.dumps(body).encode("utf-8")
                headers["Content-Type"] = "application/json"
            else:
                data = urllib.parse.urlencode(body).encode("utf-8")
                headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(API_ROOT + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                content = response.read()
                # GitCode PATCH/DELETE may succeed with HTTP 204 or an empty
                # response. Business stages verify mutations with a separate GET.
                return json.loads(content) if content.strip() else {}
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"GitCode {method} request failed (HTTP {error.code})") from None


def main():
    body_file = os.environ.get("GITCODE_API_BODY", "")
    body = json.loads(Path(body_file).read_text(encoding="utf-8")) if body_file else None
    result = GitCodeAPI(os.environ.get("GITCODE_TOKEN", "")).request(
        os.environ["GITCODE_API_METHOD"], os.environ["GITCODE_API_PATH"], body,
        os.environ.get("GITCODE_API_ENCODING", "form"))
    directory = Path(tempfile.mkdtemp(prefix="gitcode-api-", dir=os.environ.get("RUNNER_TEMP")))
    output = directory / "response.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"response-file={output}\n")
    print("GitCode API request completed")


if __name__ == "__main__":
    main()
