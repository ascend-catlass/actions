"""CANN release precedence, safe latest updates, and production workflow wiring."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / '.github/actions/install-cann-release'
spec = importlib.util.spec_from_file_location('cann_release_versions', ACTION / 'versions.py')
versions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(versions)


class VersionTests(unittest.TestCase):
    def test_semver_order_including_final_release_and_numeric_identifiers(self):
        ordered = ['8.5.2', '9.1.1', '9.2.0-alpha', '9.2.0-alpha.1',
                   '9.2.0-alpha.beta', '9.2.0-beta.2', '9.2.0-beta.10',
                   '9.2.0-rc.1', '9.2.0', '9.2.1', '9.10.0', '10.0.0-beta.1']
        self.assertEqual(sorted(reversed(ordered), key=versions.version_key), ordered)

    def test_directory_links_only_not_dates_or_listing_order(self):
        html = '''<a href="9.2.0/">9.2.0</a> 19-Oct-2026
<a href="9.2.0-beta.2/">9.2.0-beta.2</a> 30-Oct-2026
<a href="9.1.1/">9.1.1</a><a href="../">parent</a>
<a href="https://example.com/99.0.0/">external</a><a href="master/">master</a>
<a href="9.3.0~weekly.20261020.01/">weekly</a>'''
        self.assertEqual(versions.latest_version(html), '9.2.0')

    def test_reject_invalid_versions_and_empty_index(self):
        for value in ['9.2', '09.2.0', '9.2.0-beta.02', '../9.2.0', '9.2.0/extra',
                      '9.2.0;echo bad', '9.2.0~weekly.20261020.01']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                versions.version_key(value)
        with self.assertRaises(ValueError):
            versions.latest_version('<a href="../">parent</a>')

    def test_cli_newer_uses_same_precedence(self):
        for candidate, installed, expected in [('9.2.0', '9.2.0-beta.2', 0),
                ('9.2.0-beta.2', '9.2.0', 1), ('9.2.0', '9.2.0', 1),
                ('9.2.0-beta.10', '9.2.0-beta.2', 0)]:
            result = subprocess.run([sys.executable, str(ACTION / 'versions.py'),
                                     'newer', candidate, installed], check=False)
            self.assertEqual(result.returncode, expected)

    def test_workflow_reuses_transport_and_cannot_install_unmerged_code(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/install-cann-release.yml').read_text())
        triggers = workflow.get('on', workflow.get(True))
        self.assertEqual(set(triggers), {'schedule', 'workflow_dispatch'})
        self.assertEqual(triggers['schedule'], [{'cron': '0 19 * * 0'}])
        for job in workflow['jobs'].values():
            self.assertEqual(job['if'], "${{ github.ref == 'refs/heads/main' }}")
        self.assertEqual(workflow['jobs']['tools']['uses'], './.github/workflows/package-hardware-tools.yml')
        install = workflow['jobs']['install']
        self.assertEqual(install['strategy']['matrix'], '${{ fromJSON(needs.resolve.outputs.matrix) }}')
        self.assertFalse(any(s.get('uses') == 'actions/checkout@v4' for s in install['steps']))
        self.assertEqual(install['steps'][0]['uses'], 'actions/download-artifact@v4')
        self.assertEqual(workflow['concurrency']['group'], 'install-cann-weekly')


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Requires native Linux symlinks')
class LatestLinkTests(unittest.TestCase):
    def update(self, root, version):
        # Exercise the real installer function in a temporary directory, without installing packages.
        text = (ACTION / 'install.sh').read_text()
        function = text.split('update_latest() {', 1)[1].split('\n}\n', 1)[0]
        command = 'set -euo pipefail\nroot=$1; version=$2; target=$root/$version; versions=$3\n'
        command += 'update_latest() {' + function + '\n}\nupdate_latest\n'
        return subprocess.run(['bash', '-c', command, 'latest-test', str(root), version,
                               str(ACTION / 'versions.py')], capture_output=True, text=True)

    def test_latest_advances_and_never_downgrades(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for version in ['9.2.0-beta.2', '9.2.0-beta.10', '9.2.0', '9.10.0']:
                (root / version).mkdir()
                self.assertEqual(self.update(root, version).returncode, 0)
                self.assertEqual((root / 'latest').resolve(), root / version)
            for old_version in ['9.2.0-beta.2', '9.2.0']:
                self.assertEqual(self.update(root, old_version).returncode, 0)
                self.assertEqual((root / 'latest').resolve(), root / '9.10.0')

    def test_latest_repairs_missing_link_and_refuses_real_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '9.2.0').mkdir()
            self.assertEqual(self.update(root, '9.2.0').returncode, 0)
            (root / 'latest').unlink()
            (root / 'latest').write_text('existing user file')
            self.assertNotEqual(self.update(root, '9.2.0').returncode, 0)
            self.assertEqual((root / 'latest').read_text(), 'existing user file')


if __name__ == '__main__':
    unittest.main()
