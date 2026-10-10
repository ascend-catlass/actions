"""Exercise the workflow's Bash classifier and runner/report wiring."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/test-gitcode-pr.yml').read_text())
JOBS = WORKFLOW['jobs']
CLASSIFIER = next(step for step in JOBS['prepare']['steps'] if step.get('id') == 'changes')
BASH = os.environ.get('TEST_BASH') or shutil.which('bash')


class RoutingTests(unittest.TestCase):
    @unittest.skipUnless(BASH, 'Bash is required')
    def test_changed_paths(self):
        scenarios = [
            (['README.md', 'docs/guide.md', 'python/tla_dsl/docs/guide.md'], False, False),
            (['python/tla_dsl/catlass/core.py'], True, False),
            (['tests/run_dsl_test.sh', 'tests/dsl_battery/case.py'], True, False),
            (['examples/55_case/main.cpp'], False, True),
            (['tests/test_example.py', 'README.md'], False, True),
            (['python/tla_dsl/core.py', 'include/catlass/core.hpp'], True, True),
            # Renames are represented by both paths; code renamed to .md still tests.
            (['examples/55_case/main.cpp', 'examples/55_case/main.md'], False, True),
        ]
        # YAML removes indentation from block scalar contents.
        script = 'set -euo pipefail\nrun_dsl=false' + CLASSIFIER['run'].split('run_dsl=false', 1)[1]
        for paths, dsl, non_dsl in scenarios:
            with self.subTest(paths=paths), tempfile.TemporaryDirectory() as directory:
                diff_file = Path(directory) / 'paths'
                output = Path(directory) / 'output'
                diff_file.write_bytes(b''.join(path.encode() + b'\0' for path in paths))
                result = subprocess.run(
                    [BASH, '--noprofile', '--norc', '-c', script],
                    env={**os.environ, 'diff_file': diff_file.as_posix(), 'GITHUB_OUTPUT': output.as_posix()},
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_text().splitlines(), [
                    f'run_dsl={str(dsl).lower()}', f'run_all={str(non_dsl).lower()}',
                ])

    def test_runner_and_reporting_contract(self):
        self.assertEqual(JOBS['prepare']['runs-on'], 'ubuntu-latest')
        npu = JOBS['merge-and-test']
        self.assertEqual(npu['runs-on'], ['self-hosted', 'ascend950'])
        self.assertEqual(npu['if'], "${{ needs.prepare.outputs.run_dsl == 'true' || needs.prepare.outputs.run_all == 'true' }}")
        for action in ['prepare-ci-tests', 'run-ci-tests']:
            self.assertFalse(any(action in step.get('uses', '') for step in JOBS['prepare']['steps']))
            self.assertTrue(any(action in step.get('uses', '') for step in npu['steps']))
        self.assertIn('--no-renames', CLASSIFIER['run'])
        self.assertNotIn('done < <(', CLASSIFIER['run'])
        report = JOBS['report']
        self.assertEqual(report['runs-on'], 'ubuntu-latest')
        self.assertIn('always()', report['if'])
        self.assertEqual(report['steps'][0]['with']['result'],
                         "${{ needs.prepare.outputs.run_dsl != 'true' && needs.prepare.outputs.run_all != 'true' && 'success' || needs.merge-and-test.result }}")


if __name__ == '__main__':
    unittest.main()
