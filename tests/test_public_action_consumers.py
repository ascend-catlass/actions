"""Check published interfaces and project boundaries against the pinned dependency."""
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SHA = '4042e6e501fab8a2cee4e87fca0248b2347e05df'


class PublicActionConsumers(unittest.TestCase):
    def test_all_public_calls_use_pinned_existing_interfaces(self):
        names = set()
        for path in [*(ROOT / '.github/workflows').glob('*.yml'), *(ROOT / '.github/actions').glob('*/action.yml')]:
            config = yaml.safe_load(path.read_text(encoding='utf-8'))
            groups = [config['runs']] if 'runs' in config else config['jobs'].values()
            for group in groups:
                for step in group.get('steps', []):
                    use = step.get('uses', '')
                    if not use.startswith('yuantao313/actions/'):
                        continue
                    name, ref = use.removeprefix('yuantao313/actions/').split('@')
                    names.add(name)
                    self.assertEqual(ref, SHA, path)
                    metadata = yaml.safe_load((ROOT / 'shared_actions' / name / 'action.yml').read_text(encoding='utf-8'))
                    inputs = metadata.get('inputs', {})
                    supplied = step.get('with', {})
                    self.assertFalse(set(supplied) - set(inputs), (path, name))
                    self.assertFalse({key for key, field in inputs.items() if field.get('required') and key not in supplied}, (path, name))
        self.assertEqual(names, {'atomgit-api', 'atomgit-pr-metadata', 'atomgit-checkout-pr',
                                'atomgit-pr-status', 'atomgit-issue-context', 'atomgit-issue-comment',
                                'atomgit-release', 'setup-traecn', 'traecn', 'trust-checkout',
                                'install-python-requirements'})

    def test_generic_implementations_are_not_vendored(self):
        for name in ['atomgit-api', 'atomgit-pr-metadata', 'setup-trae-cn', 'trae-cn']:
            self.assertFalse((ROOT / '.github/actions' / name / 'action.yml').exists())
        adapter = (ROOT / 'scripts/atomgit_api.py').read_text(encoding='utf-8')
        self.assertIn('from shared_actions._lib.atomgit_api import AtomGitAPI', adapter)
        self.assertNotIn('urllib', adapter)
        self.assertFalse((ROOT / '.github/actions/run-ci-tests/trust-checkout.sh').exists())

    def test_platform_domains_and_trigger_documents(self):
        for path in [*(ROOT / '.github').rglob('*.yml'), *(ROOT / 'scripts').glob('*.py'),
                     *(ROOT / 'docs').rglob('*.md'), ROOT / 'README.md', ROOT / 'README.en.md']:
            text = path.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'(?i)(?:dev[ -](?:web)?hook|dev gateway)', path)
            if path.name != 'reply-gitcode-issue.yml':
                self.assertNotRegex(text, r'(?i)https?://[^\s/]*gitcode\.com', path)

    def test_metadata_and_merge_output_names_match_public_contract(self):
        config = yaml.safe_load((ROOT / '.github/workflows/test-atomgit-pr.yml').read_text(encoding='utf-8'))
        prepare = config['jobs']['prepare']
        self.assertEqual(prepare['outputs']['head_sha'], '${{ steps.pr.outputs.head-sha }}')
        tests = config['jobs']['merge-and-test']['steps']
        non_dsl = next(s for s in tests if s.get('name') == 'Run non-DSL test stage')
        self.assertEqual(non_dsl['with']['base-sha'], '${{ steps.merge.outputs.base-sha }}')
