"""Keep existing deployments working while preferring the current secret name."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml

from scripts.atomgit_api import AtomGitAPI, resolve_token
from scripts import community_tasks

ROOT = Path(__file__).resolve().parents[1]
FALLBACK = '${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}'


class TokenCompatibilityTests(unittest.TestCase):
    def test_current_secret_wins_and_empty_or_missing_current_uses_legacy(self):
        for values, expected in [
            ({'ATOMGIT_TOKEN': 'current', 'GITCODE_TOKEN': 'legacy'}, 'current'),
            ({'ATOMGIT_TOKEN': 'current'}, 'current'),
            ({'ATOMGIT_TOKEN': '', 'GITCODE_TOKEN': 'legacy'}, 'legacy'),
            ({'GITCODE_TOKEN': 'legacy'}, 'legacy'),
        ]:
            with self.subTest(keys=list(values)), patch.dict(os.environ, values, clear=True):
                api = AtomGitAPI(resolve_token())
                self.assertEqual(api.headers['Authorization'], f'Bearer {expected}')
                self.assertEqual(api.headers['PRIVATE-TOKEN'], expected)
        for values in [{}, {'ATOMGIT_TOKEN': '', 'GITCODE_TOKEN': ''}]:
            with self.subTest(keys=list(values)), patch.dict(os.environ, values, clear=True):
                with self.assertRaisesRegex(ValueError, 'token is required'):
                    AtomGitAPI(resolve_token())

    def test_fork_push_accepts_legacy_only_configuration(self):
        with patch.dict(os.environ, {'GITCODE_TOKEN': 'legacy-only'}, clear=True), \
             patch.object(community_tasks.subprocess, 'run') as run:
            community_tasks.push_branch(Path('.'), 'account', 'codex/test')
        env = run.call_args.kwargs['env']
        self.assertEqual(env['ATOMGIT_PUSH_TOKEN'], 'legacy-only')
        self.assertNotIn('GITCODE_TOKEN', env)

    def test_all_workflow_secret_consumers_have_the_ordered_fallback(self):
        consumers = 0
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            for line in path.read_text(encoding='utf-8').splitlines():
                if 'secrets.ATOMGIT_TOKEN' in line:
                    self.assertIn(FALLBACK, line, path)
                    consumers += 1
        self.assertGreaterEqual(consumers, 15)

    def test_reusable_build_accepts_legacy_named_secret_without_new_secret(self):
        config = yaml.safe_load((ROOT / '.github/workflows/build-dsl-wheel.yml').read_text(encoding='utf-8'))
        events = config.get('on', config.get(True))
        secrets = events['workflow_call']['secrets']
        self.assertEqual(set(secrets), {'ATOMGIT_TOKEN', 'GITCODE_TOKEN'})
        self.assertFalse(secrets['ATOMGIT_TOKEN']['required'])
        self.assertFalse(secrets['GITCODE_TOKEN']['required'])

    def test_existing_release_environment_is_preserved(self):
        config = yaml.safe_load((ROOT / '.github/workflows/release-dsl-wheel.yml').read_text(encoding='utf-8'))
        self.assertEqual(config['jobs']['publish-atomgit']['environment']['name'], 'gitcode-release')
