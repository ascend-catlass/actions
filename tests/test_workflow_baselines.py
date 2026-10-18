"""Check the production PR and wheel workflow baseline contracts."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'))

class BaselineTests(unittest.TestCase):
    def test_pr_entrypoint_uses_expected_stages_and_image(self):
        main = workflow('test-atomgit-pr.yml')
        steps = main['jobs']['merge-and-test']['steps']
        container = next(s for s in steps if s.get('id') == 'create_container')
        self.assertEqual(container['with']['image-tag'], '9.2.0-beta.2-950-ubuntu22.04-py3.12')
        self.assertEqual([s['with']['suite'] for s in steps if s.get('with', {}).get('suite', '').startswith('dsl')],
                         ['dsl-dev', 'dsl-ir', 'dsl-lit', 'dsl'])

    def test_wheel_chain_uses_matching_archive_contract(self):
        wheel = workflow('build-dsl-wheel.yml')
        npuir = workflow('build-ascendnpu-ir-20261013.yml')
        self.assertEqual(wheel['jobs']['npuir']['uses'], './.github/workflows/build-ascendnpu-ir-20261013.yml')
        for key in ['NPUIR_BASELINE_DATE', 'NPUIR_LEGACY_POSTFIX', 'NPUIR_BUILD_CONTRACT', 'NPUIR_BUILD_FINGERPRINT']:
            self.assertEqual(wheel['env'][key], npuir['env'][key])
        self.assertEqual(wheel['jobs']['npuir']['with']['ref'], '${{ needs.resolve.outputs.npuir_sha }}')
        for name in ['nightly-dsl-wheel.yml', 'release-dsl-wheel.yml']:
            self.assertTrue(any(j.get('uses') == './.github/workflows/build-dsl-wheel.yml'
                                for j in workflow(name)['jobs'].values()))

    def test_wheel_build_has_no_host_cann_dependency(self):
        wheel = workflow('build-dsl-wheel.yml')
        self.assertNotIn('CANN_ROOT', wheel['env'])
        steps = wheel['jobs']['build']['steps']
        build = next(s for s in steps if s['name'] == 'Build wheels')
        env = build['env']
        self.assertIn('ASCEND_HOME_PATH=""', env['CIBW_ENVIRONMENT'])
        self.assertNotIn('Ascend/cann', env['CIBW_CONTAINER_ENGINE'])
        self.assertNotIn('set_env.sh', env['CIBW_BEFORE_ALL'])
        self.assertNotIn('Validate CANN', [s['name'] for s in steps])

    def test_wheel_and_dependency_jobs_use_same_dedicated_worker_pool(self):
        wheel = workflow('build-dsl-wheel.yml')['jobs']['build']
        npuir = workflow('build-ascendnpu-ir-20261013.yml')['jobs']['prepare']
        expected = ['self-hosted', 'Linux', 'ascend-catlass-dsl-build', '${{ matrix.runner_arch }}']
        self.assertEqual(wheel['runs-on'], expected)
        self.assertEqual(npuir['runs-on'], '${{ matrix.runs_on }}')
        selector = workflow('build-ascendnpu-ir-20261013.yml')['jobs']['runners']
        self.assertEqual(selector['steps'][-1]['env']['DEFAULT_RUNNER_LABEL'], 'ascend-catlass-dsl-build')
        self.assertEqual({row['target_arch']: row['runner_arch']
                          for row in wheel['strategy']['matrix']['include']},
                         {'x86_64': 'X64', 'aarch64': 'ARM64'})
        # Release transport and historical diagnosis have separate routing.
        self.assertEqual(workflow('release-dsl-wheel.yml')['jobs']['publish-atomgit']['runs-on'],
                         ['self-hosted', 'publish', 'X64'])
        self.assertEqual(workflow('build-ascendnpu-ir-20260720.yml')['jobs']['prepare']['runs-on'],
                         ['self-hosted', 'publish', '${{ matrix.runner_arch }}'])

if __name__ == '__main__':
    unittest.main()
