"""Exercise the RDV cleanup step against disposable directories."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/test-atomgit-pr.yml').read_text())
STEP = next(s for s in WORKFLOW['jobs']['merge-and-test']['steps']
            if s['name'] == 'Delete test container and source directory')


class CleanupTests(unittest.TestCase):
    def test_cleanup_always_runs_even_before_container_creation(self):
        self.assertEqual(STEP['if'], '${{ always() }}')
        self.assertEqual(STEP['env']['SOURCE_DIR'],
                         '${{ github.workspace }}/.rdv-work/pr-${{ github.run_id }}-${{ github.run_attempt }}')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('bash'), 'Linux cleanup integration')
    def test_cleanup_is_limited_to_this_run_and_stops_if_container_removal_fails(self):
        for scenario in ('normal', 'no-container', 'outside', 'symlink', 'parent-symlink',
                         'wrong-container', 'docker-failure'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                workspace = root / 'workspace'
                workspace.mkdir()
                outside = root / 'outside'
                outside.mkdir()
                (outside / 'keep').write_text('unrelated data')
                parent = workspace / '.rdv-work'
                if scenario == 'parent-symlink':
                    parent.symlink_to(outside, target_is_directory=True)
                else:
                    parent.mkdir()
                source = parent / 'pr-123-1'
                if scenario == 'symlink':
                    source.symlink_to(outside, target_is_directory=True)
                else:
                    source.mkdir()
                    (source / 'generated').write_text('build output')
                other = parent / 'pr-456-1'
                other.mkdir()
                bin_dir = root / 'bin'
                bin_dir.mkdir()
                commands = {
                    'docker': '#!/bin/bash\necho "$*" >> "$CALL_LOG"\n'
                              'if [[ "$1" == rm && "$FAIL_DOCKER" == 1 ]]; then exit 1; fi\n',
                    'sudo': '#!/bin/bash\n[[ "$1" == -n ]] && shift\nexec "$@"\n',
                }
                for name, text in commands.items():
                    command = bin_dir / name
                    command.write_text(text)
                    command.chmod(0o755)
                env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}',
                       'GITHUB_WORKSPACE': str(workspace), 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1',
                       'SOURCE_DIR': str(outside if scenario == 'outside' else source),
                       'CONTAINER_NAME': '' if scenario == 'no-container' else
                       ('unrelated' if scenario == 'wrong-container' else 'catlass-rdv-123-1'),
                       'CALL_LOG': str(root / 'calls'), 'FAIL_DOCKER': str(int(scenario == 'docker-failure'))}
                result = subprocess.run(['bash', '-c', STEP['run']], env=env, capture_output=True, text=True)
                success = scenario in ('normal', 'no-container')
                self.assertEqual(result.returncode == 0, success, result.stderr)
                self.assertEqual(source.exists(), not success)
                self.assertTrue((outside / 'keep').exists())
                self.assertTrue(other.exists())


if __name__ == '__main__':
    unittest.main()
