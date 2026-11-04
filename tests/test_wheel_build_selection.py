"""PR wheel selection, ABI coverage, and reusable workflow wiring."""
import itertools
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml
from scripts.wheel_build_selection import (ARCHES, PYTHONS, build_selection,
                                           dispatch_selection, validate_pr, verify_wheels)

ROOT = Path(__file__).resolve().parents[1]


class WheelSelectionTests(unittest.TestCase):
    def test_optional_pr_preserves_selected_targets(self):
        env = {"PYTHON_" + v.replace(".", ""): "true" for v in PYTHONS}
        env.update({"ARCH_X86_64": "true", "ARCH_AARCH64": "false"})
        for pr in [None, "", "1607"]:
            selected = dict(env)
            if pr is not None:
                selected["PR_NUMBER"] = pr
            result = dispatch_selection(selected)
            self.assertEqual(result["pr_number"], pr or "")
            self.assertEqual(json.loads(result["python_versions"]), list(PYTHONS))
            self.assertEqual(json.loads(result["matrix"]), {"include": [{"target_arch": "x86_64"}]})
        for pr in [" ", "0", "-1", "01", "1607\n", "1607;echo bad"]:
            with self.assertRaises(ValueError):
                dispatch_selection(dict(env, PR_NUMBER=pr))

    @unittest.skipUnless(shutil.which('git') and shutil.which('bash'), 'git and bash required')
    def test_default_head_resolves_exact_commit_and_rejects_missing_remote(self):
        config = yaml.safe_load((ROOT / '.github/workflows/pr-dsl-wheel.yml').read_text())
        head = next(s for s in config['jobs']['prepare']['steps'] if s.get('id') == 'head')
        with tempfile.TemporaryDirectory() as tmp:
            remote = Path(tmp) / 'source'
            subprocess.run(['git', 'init', '--quiet', str(remote)], check=True)
            (remote / 'source.txt').write_text('head build')
            subprocess.run(['git', '-C', str(remote), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(remote), '-c', 'user.name=test', '-c',
                            'user.email=test@example.com', 'commit', '--quiet', '-m', 'head'], check=True)
            sha = subprocess.check_output(['git', '-C', str(remote), 'rev-parse', 'HEAD'], text=True).strip()
            output = Path(tmp) / 'output'
            env = dict(os.environ, GITHUB_OUTPUT=str(output))
            for path, success in [(remote, True), (Path(tmp) / 'missing', False)]:
                script = head['run'].replace('https://atomgit.com/cann/catlass.git', "'" + path.as_posix() + "'")
                result = subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stderr)
            self.assertEqual(output.read_text(), 'source_sha=' + sha + '\n')

    def test_all_checkbox_combinations(self):
        for flags in itertools.product([False, True], repeat=6):
            env = {"PR_NUMBER": "1280"}
            keys = ["PYTHON_" + v.replace(".", "") for v in PYTHONS] + ["ARCH_" + a.upper() for a in ARCHES]
            env.update({k: str(f).lower() for k, f in zip(keys, flags)})
            if not any(flags[:4]) or not any(flags[4:]):
                with self.assertRaises(ValueError):
                    dispatch_selection(env)
                continue
            result = dispatch_selection(env)
            self.assertEqual(json.loads(result["python_versions"]), [v for v, f in zip(PYTHONS, flags) if f])
            self.assertEqual(json.loads(result["matrix"])["include"],
                             [{"target_arch": a} for a, f in zip(ARCHES, flags[4:]) if f])

    def test_reject_invalid_pr_and_reusable_inputs(self):
        for pr in ["", "0", "-1", "01", "1\n", "1280; echo bad", "${{ secrets.X }}"]:
            with self.assertRaises(ValueError):
                validate_pr(pr)
        for versions in ['[]', '"3.12"', '["3.14"]', '["3.12","3.12"]', '[true]', 'null', '{}']:
            with self.assertRaises(ValueError):
                build_selection(versions, "")
        with self.assertRaises(ValueError):
            build_selection('["3.12"]', "amd64;echo bad")
        env = {"PR_NUMBER": "1280", "PYTHON_310": "yes"}
        with self.assertRaises(ValueError):
            dispatch_selection(env)

    def test_defaults_and_single_architecture(self):
        self.assertEqual(build_selection(json.dumps(PYTHONS), "")["cibw_build"],
                         "cp310-* cp311-* cp312-* cp313-*")
        result = build_selection('["3.11","3.13"]', 'aarch64')
        self.assertEqual(result['cibw_build'], 'cp311-* cp313-*')
        self.assertEqual(json.loads(result['build_matrix'])['include'],
                         [{'target_arch': 'aarch64', 'runner_arch': 'ARM64'}])

    def test_expected_wheels_must_all_be_present_exactly_once(self):
        def wheel(tag):
            return f'ascend_catlass_dsl-1.2.4.dev20261102+pr1280.gabcdef012345-{tag}-{tag}-manylinux_2_28_x86_64.whl'
        verify_wheels([wheel('cp310'), wheel('cp312')], '["3.10","3.12"]')
        for wheels in [[], [wheel('cp310')], [wheel('cp310'), wheel('cp310')],
                       [wheel('cp310'), wheel('cp311')], ['bad.whl']]:
            with self.assertRaises(ValueError):
                verify_wheels(wheels, '["3.10","3.12"]')

    def test_cli_empty_selection_fails_without_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'outputs'
            env = dict(os.environ, GITHUB_OUTPUT=str(output), PR_NUMBER='1280')
            env.update({'PYTHON_' + v.replace('.', ''): 'false' for v in PYTHONS})
            env.update({'ARCH_' + a.upper(): 'true' for a in ARCHES})
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/wheel_build_selection.py'), 'dispatch'],
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Select at least one', result.stderr)
            self.assertFalse(output.exists())

    def test_workflow_pins_one_pr_commit_and_only_builds_artifacts(self):
        config = yaml.safe_load((ROOT / '.github/workflows/pr-dsl-wheel.yml').read_text())
        inputs = config.get('on', config.get(True))['workflow_dispatch']['inputs']
        self.assertFalse(inputs['pr_number']['required'])
        self.assertEqual(inputs['pr_number']['default'], '')
        prepare = config['jobs']['prepare']
        self.assertEqual(prepare['outputs']['source_sha'],
                         '${{ steps.pr.outputs.head-sha || steps.head.outputs.source_sha }}')
        pr = next(s for s in prepare['steps'] if s.get('id') == 'pr')
        head = next(s for s in prepare['steps'] if s.get('id') == 'head')
        self.assertEqual(pr['if'], "${{ steps.selection.outputs.pr_number != '' }}")
        self.assertEqual(head['if'], "${{ steps.selection.outputs.pr_number == '' }}")
        self.assertEqual(sum(v['type'] == 'boolean' for v in inputs.values()), 6)
        self.assertTrue(all(v.get('default') is True for v in inputs.values() if v['type'] == 'boolean'))
        self.assertEqual(set(config['jobs']), {'prepare', 'build'})
        builder = config['jobs']['build']
        self.assertEqual(builder['with']['catlass_ref'], '${{ needs.prepare.outputs.source_sha }}')
        self.assertEqual(builder['with']['target_arch'], '${{ matrix.target_arch }}')
        self.assertEqual(builder['with']['python_versions'], '${{ needs.prepare.outputs.python_versions }}')
        self.assertEqual(builder['with']['artifact_retention_days'], 7)
        self.assertEqual(builder['uses'], './.github/workflows/build-dsl-wheel.yml')
        reusable = yaml.safe_load((ROOT / '.github/workflows/build-dsl-wheel.yml').read_text())
        call = reusable.get('on', reusable.get(True))['workflow_call']
        self.assertEqual(call['inputs']['artifact_retention_days']['default'], 30)
        steps = reusable['jobs']['build']['steps']
        upload = next(s for s in steps if s.get('uses') == 'actions/upload-artifact@v4')
        self.assertEqual(upload['with']['retention-days'], '${{ inputs.artifact_retention_days || 30 }}')
        cleanup = next(s for s in steps if s.get('name') == 'Clean up per-run wheel sources')
        self.assertEqual(cleanup['if'], '${{ always() }}')
        prep = reusable['jobs']['npuir']['with']
        self.assertIn('inputs.target_arch', prep['runner_label'])
        self.assertIn('inputs.target_arch', prep['target_arch'])
        build = next(s for s in reusable['jobs']['build']['steps'] if s.get('name') == 'Build wheels')
        self.assertEqual(build['env']['CIBW_BUILD'], '${{ needs.resolve.outputs.cibw_build }}')
        dependency = yaml.safe_load((ROOT / '.github/workflows/build-ascendnpu-ir-20261013.yml').read_text())
        self.assertIn('inputs.target_arch', dependency['concurrency']['group'])


if __name__ == '__main__':
    unittest.main()
