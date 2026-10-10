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
MERGER = next(step for step in JOBS['merge-and-test']['steps'] if step.get('id') == 'merge')
BASH = os.environ.get('TEST_BASH') or shutil.which('bash')


class RoutingTests(unittest.TestCase):
    @unittest.skipUnless(BASH, 'Bash is required')
    def test_target_updates_and_merge_conflicts(self):
        for conflict in [False, True]:
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'source'
                source.mkdir()

                def git(*args):
                    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()

                git('init', '-q', '-b', 'master')
                git('config', 'user.name', 'test')
                git('config', 'user.email', 'test@example.invalid')
                git('config', 'core.autocrlf', 'false')
                case = source / 'examples/55_case/main.cpp'
                case.parent.mkdir(parents=True)
                case.write_text('base\n')
                git('add', '.')
                git('commit', '-qm', 'base')
                stale_base = git('rev-parse', 'HEAD')
                git('checkout', '-qb', 'feature')
                case.write_text('PR change\n')
                git('add', '.')
                git('commit', '-qm', 'PR')
                head = git('rev-parse', 'HEAD')
                git('update-ref', 'refs/merge-requests/1/head', head)
                git('checkout', '-q', 'master')
                if conflict:
                    case.write_text('conflicting target change\n')
                else:
                    (source / 'README.md').write_text('target advanced\n')
                git('add', '.')
                git('commit', '-qm', 'target update')
                actual_base = git('rev-parse', 'HEAD')

                for step, stage in [(CLASSIFIER, 'classify'), (MERGER, 'merge')]:
                    output = root / f'{stage}-output'
                    runner_temp = root / stage
                    runner_temp.mkdir()
                    # Execute the workflow script against a disposable local remote.
                    script = step['run'].replace('https://gitcode.com/cann/catlass.git',
                                                 f'"{source.as_posix()}"')
                    result = subprocess.run(
                        [BASH, '--noprofile', '--norc', '-c', script],
                        env={**os.environ, 'RUNNER_TEMP': runner_temp.as_posix(),
                             'GITHUB_OUTPUT': output.as_posix(), 'GITHUB_RUN_ID': '1',
                             'GITHUB_RUN_ATTEMPT': '1', 'PR_NUMBER': '1', 'BASE_REF': 'master',
                             'BASE_SHA': stale_base, 'HEAD_SHA': head},
                        capture_output=True, text=True,
                    )
                    values = dict(line.split('=', 1) for line in output.read_text().splitlines())
                    self.assertEqual(values['base_sha'], actual_base)
                    if stage == 'merge' and conflict:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('CONFLICT', result.stdout)
                        self.assertNotIn('worktree', values)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        if stage == 'classify':
                            self.assertEqual(values['run_all'], 'true')
                        else:
                            merged_case = Path(values['worktree']) / 'examples/55_case/main.cpp'
                            self.assertEqual(merged_case.read_text(), 'PR change\n')
                            self.assertEqual((merged_case.parents[2] / 'README.md').read_text(),
                                             'target advanced\n')

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
        non_dsl = next(step for step in npu['steps'] if step['name'] == 'Run non-DSL test stage')
        self.assertEqual(non_dsl['with']['base-sha'], '${{ steps.merge.outputs.base_sha }}')
        report = JOBS['report']
        self.assertEqual(report['runs-on'], 'ubuntu-latest')
        self.assertIn('always()', report['if'])
        self.assertEqual(report['steps'][0]['with']['result'],
                         "${{ needs.prepare.outputs.run_dsl != 'true' && needs.prepare.outputs.run_all != 'true' && 'success' || needs.merge-and-test.result }}")


if __name__ == '__main__':
    unittest.main()
