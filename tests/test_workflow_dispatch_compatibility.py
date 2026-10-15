"""Exercise stable dispatch routes and legacy input forwarding after rebranding."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASH = os.environ.get('TEST_BASH') or shutil.which('bash')
ROUTES = {'test-gitcode-pr': 'test-atomgit-pr',
          'reply-gitcode-ci-passed': 'reply-atomgit-ci-passed',
          'reply-gitcode-issue': 'reply-atomgit-issue'}


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / f'{name}.yml').read_text(encoding='utf-8'))


def events(config):
    return config.get('on', config.get(True))


class WorkflowDispatchCompatibility(unittest.TestCase):
    def test_existing_dispatch_routes_forward_to_callable_canonical_workflows(self):
        for old, new in ROUTES.items():
            with self.subTest(route=old):
                adapter, target = workflow(old), workflow(new)
                self.assertEqual(set(events(adapter)), {'workflow_dispatch'})
                self.assertEqual(events(adapter)['workflow_dispatch']['inputs'],
                                 events(target)['workflow_call']['inputs'])
                self.assertEqual(events(target)['workflow_dispatch']['inputs'],
                                 events(target)['workflow_call']['inputs'])
                call = adapter['jobs']['run']
                self.assertEqual(call['uses'], f'./.github/workflows/{new}.yml')
                self.assertEqual(call['secrets'], 'inherit')
                self.assertEqual(set(call['with']), set(events(target)['workflow_call']['inputs']))
                self.assertNotIn('steps', call)
                if old != 'reply-gitcode-issue':
                    self.assertEqual(call['with']['pr_number'], '${{ inputs.pr_number }}')
                self.assertIn('AtomGit', adapter['name'])

    def test_rdv_adapter_allows_diagnostic_permission_and_legacy_secret(self):
        adapter = workflow('test-gitcode-pr')
        target = workflow('test-atomgit-pr')
        self.assertEqual(adapter['permissions']['actions'], 'read')
        self.assertEqual(target['jobs']['analyze-failure']['permissions']['actions'], 'read')
        secrets = events(target)['workflow_call']['secrets']
        for name in ('ATOMGIT_TOKEN', 'GITCODE_TOKEN', 'TRAE_CN_PAT'):
            self.assertFalse(secrets[name]['required'])

    @unittest.skipUnless(BASH, 'Bash is required')
    def test_issue_adapter_normalizes_legacy_urls_without_accepting_arbitrary_input(self):
        adapter = workflow('reply-gitcode-issue')
        step = adapter['jobs']['normalize']['steps'][0]
        call = adapter['jobs']['run']
        self.assertEqual(call['needs'], 'normalize')
        self.assertEqual(call['with']['issue_url'], '${{ needs.normalize.outputs.issue-url }}')
        self.assertEqual(call['with']['publish'], '${{ inputs.publish }}')
        for url, expected in [
            ('https://gitcode.com/cann/catlass/issues/739', 'https://atomgit.com/cann/catlass/issues/739'),
            ('https://atomgit.com/cann/catlass/issues/739', 'https://atomgit.com/cann/catlass/issues/739'),
            ('https://gitcode.com/cann/catlass/issues/739?secret=x', None),
            ('https://gitcode.com.evil.test/cann/catlass/issues/739', None),
            ('https://gitcode.com/cann/catlass/issues/739\nother=value', None),
        ]:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'outputs'
                result = subprocess.run([BASH, '--noprofile', '--norc', '-c', step['run']],
                    env={**os.environ, 'ISSUE_URL': url, 'GITHUB_OUTPUT': output.as_posix()},
                    capture_output=True, text=True)
                if expected is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(output.read_text().strip(), f'issue-url={expected}')
