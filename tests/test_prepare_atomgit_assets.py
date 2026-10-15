import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from scripts.prepare_atomgit_assets import prepare


class ReleaseAssetsTests(unittest.TestCase):
    def fixture(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / 'wheels').mkdir()
        for n in range(8): (root / 'wheels' / f'package-{n}.whl').write_bytes(str(n).encode())
        sums = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in sorted((root/'wheels').glob('*.whl'))]
        (root/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
        return root

    def test_eight_wheels_and_checksums_feed_public_asset_list(self):
        root = self.fixture()
        api = Mock()
        api.request.return_value = {'assets': []}
        self.assertEqual(len(prepare(api, 'cann/catlass', 'v2.1.0', root)), 9)
        (root/'wheels/package-0.whl').write_bytes(b'corruption')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            prepare(api, 'cann/catlass', 'v2.1.0', root)

    def test_matching_existing_asset_is_not_uploaded_again(self):
        root = self.fixture()
        api = Mock()
        api.request.return_value = {'assets': [{'name': 'package-0.whl', 'browser_download_url': 'https://atomgit.com/asset'}]}
        with patch('scripts.prepare_atomgit_assets.urlopen', return_value=io.BytesIO(b'0')):
            pending = prepare(api, 'cann/catlass', 'v2.1.0', root)
        self.assertEqual(len(pending), 8)
        self.assertFalse(any(p.endswith('package-0.whl') for p in pending))
        with patch('scripts.prepare_atomgit_assets.urlopen', return_value=io.BytesIO(b'other')):
            with self.assertRaisesRegex(ValueError, 'conflicting asset'):
                prepare(api, 'cann/catlass', 'v2.1.0', root)

    def test_missing_bundle_or_non_404_service_error_is_not_hidden(self):
        root = self.fixture()
        api = Mock()
        api.request.side_effect = RuntimeError('AtomGit GET request failed (HTTP 500)')
        with self.assertRaisesRegex(RuntimeError, 'HTTP 500'):
            prepare(api, 'cann/catlass', 'v2.1.0', root)
        api.request.side_effect = RuntimeError('AtomGit GET request failed (HTTP 404)')
        self.assertEqual(len(prepare(api, 'cann/catlass', 'v2.1.0', root)), 9)
        (root/'wheels/package-0.whl').unlink()
        with self.assertRaisesRegex(ValueError, 'eight wheels'):
            prepare(api, 'cann/catlass', 'v2.1.0', root)
