from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import publish_gitcode_release


class FakeGitCodeClient:
    def __init__(self, existing: bool) -> None:
        self.release = {"tag_name": "v2.1.0", "assets": []} if existing else None
        self.created = False
        self.uploaded: list[str] = []

    def get_release(self, tag: str) -> dict | None:
        return self.release

    def create_release(self, tag: str, name: str, notes: str) -> dict:
        self.created = True
        self.release = {"tag_name": tag, "name": name, "body": notes, "assets": []}
        return self.release

    def upload_file(self, tag: str, path: Path) -> None:
        self.uploaded.append(path.name)
        assert self.release is not None
        self.release["assets"].append(
            {"name": path.name, "browser_download_url": f"https://example.invalid/{path.name}"}
        )


class PublishGitCodeReleaseTest(unittest.TestCase):
    def make_bundle(self, root: Path) -> Path:
        bundle = root / "bundle"
        wheel_dir = bundle / "wheels"
        wheel_dir.mkdir(parents=True)
        for index in range(8):
            (wheel_dir / f"package-{index}.whl").write_bytes(f"wheel-{index}".encode())
        (bundle / "SHA256SUMS").write_text("checksums\n", encoding="utf-8")
        (bundle / "release-notes.md").write_text("release notes\n", encoding="utf-8")
        return bundle

    def test_creates_missing_release_and_uploads_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeGitCodeClient(existing=False)
            publish_gitcode_release.publish(
                client, "v2.1.0", "2.1.0", self.make_bundle(Path(directory))
            )
            self.assertTrue(client.created)
            self.assertEqual(len(client.uploaded), 9)
            self.assertIn("SHA256SUMS", client.uploaded)

    def test_reuses_existing_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeGitCodeClient(existing=True)
            publish_gitcode_release.publish(
                client, "v2.1.0", "2.1.0", self.make_bundle(Path(directory))
            )
            self.assertFalse(client.created)
            self.assertEqual(len(client.uploaded), 9)


if __name__ == "__main__":
    unittest.main()
