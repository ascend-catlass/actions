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
        self.assertEqual(wheel['env']['CANN_ROOT'], '/usr/local/Ascend/cann-9.2.0-beta.2')
        self.assertEqual(wheel['jobs']['npuir']['uses'], './.github/workflows/build-ascendnpu-ir-20261013.yml')
        for key in ['NPUIR_BASELINE_DATE', 'NPUIR_LEGACY_POSTFIX', 'NPUIR_BUILD_CONTRACT', 'NPUIR_BUILD_FINGERPRINT']:
            self.assertEqual(wheel['env'][key], npuir['env'][key])
        self.assertEqual(wheel['jobs']['npuir']['with']['ref'], '${{ needs.resolve.outputs.npuir_sha }}')
        for name in ['nightly-dsl-wheel.yml', 'release-dsl-wheel.yml']:
            self.assertTrue(any(j.get('uses') == './.github/workflows/build-dsl-wheel.yml'
                                for j in workflow(name)['jobs'].values()))

if __name__ == '__main__':
    unittest.main()
