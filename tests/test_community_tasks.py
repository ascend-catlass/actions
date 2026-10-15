import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import community_tasks as task

HEAD, BASE = 'a' * 40, 'b' * 40
DIFF = '''diff --git a/source.cpp b/source.cpp
--- a/source.cpp
+++ b/source.cpp
@@ -4,2 +4,3 @@
 unchanged
-old
+new
+another
'''


class API:
    def __init__(self):
        self.pr = {'state': 'open', 'head': {'sha': HEAD}, 'base': {'sha': BASE}}
        self.comments = []
        self.writes = []

    def request(self, method, path, body=None, **kwargs):
        if path == '/user':
            return {'id': 'bot'}
        if path.endswith('/pulls/123'):
            return self.pr
        if method == 'POST':
            self.writes.append(body)
            comment = {'id': str(len(self.comments) + 1), 'body': body['body'], 'user': {'id': 'bot'},
                       'position': {'new_path': body.get('path'), 'head_sha': HEAD}}
            self.comments.append(comment)
            return comment
        if '/pulls/comments/' in path:
            return self.comments[int(path.rsplit('/', 1)[1]) - 1]
        return copy.deepcopy(self.comments)


def metadata():
    return {'number': '123', 'head_sha': HEAD, 'base_sha': BASE, 'user_id': 'bot',
            'lines': task.changed_lines(DIFF)}


class CommunityTaskTests(unittest.TestCase):
    def test_findings_only_on_real_added_lines(self):
        self.assertEqual(task.changed_lines(DIFF), {'source.cpp': [5, 6]})
        for path, line in [('source.cpp', 4), ('other.cpp', 5), ('../outside', 5), ('source.cpp', True)]:
            with self.subTest(path=path, line=line), self.assertRaises(ValueError):
                task.validate_findings({'findings': [{'path': path, 'line': line, 'body': 'Why?'}]}, metadata()['lines'])

    def test_inline_publish_readback_and_retry_dedup(self):
        api = API()
        answer = {'findings': [{'path': 'source.cpp', 'line': 5, 'body': '这个边界会越界吗？'}]}
        self.assertEqual(task.publish_review(api, metadata(), answer)['comment_ids'], ['1'])
        self.assertEqual(task.publish_review(api, metadata(), answer)['comment_ids'], ['1'])
        self.assertEqual(len(api.writes), 1)
        self.assertEqual(api.writes[0]['position'], 5)
        self.assertEqual(api.writes[0]['position_type'], 'text')

    def test_stale_head_base_closed_and_identity_block_before_posting(self):
        for field in ('head', 'base', 'state', 'identity'):
            api = API()
            context = metadata()
            if field in ('head', 'base'):
                api.pr[field]['sha'] = 'c' * 40
            elif field == 'state':
                api.pr['state'] = 'closed'
            else:
                context['user_id'] = 'different'
            with self.subTest(field=field), self.assertRaises(ValueError):
                task.publish_review(api, context, {'findings': []})
            self.assertEqual(api.writes, [])

    def test_compile_is_one_exact_command_not_inline(self):
        api = API()
        task.compile_once(api, '123', {'id': 'bot'})
        task.compile_once(api, '123', {'id': 'bot'})
        self.assertEqual(api.writes, [{'body': 'compile'}])

    def test_complex_issue_does_not_apply_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(task.apply_fix(Path(directory), {'simple': False, 'summary': 'Needs reproduction', 'patch': ''}))

    def test_patch_cannot_write_automation_or_escape_checkout(self):
        for name in ('.github/workflows/ci.yml', '../escape', '.git/config', '/etc/passwd'):
            answer = {'simple': True, 'summary': 'fix', 'patch': f'--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-old\n+new\n'}
            with self.subTest(name=name), self.assertRaises(ValueError):
                task.apply_fix(Path('.'), answer)

    def test_real_patch_application_and_staged_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'file.txt').write_text('old\n', encoding='utf-8', newline='\n')
            task.git(root, 'config', 'core.autocrlf', 'false')
            task.git(root, 'add', 'file.txt')
            task.git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'base')
            answer = {'simple': True, 'summary': 'fix', 'patch': 'diff --git a/file.txt b/file.txt\n--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n'}
            self.assertTrue(task.apply_fix(root, answer))
            self.assertEqual(task.git(root, 'show', ':file.txt'), 'new')

    def test_manual_workflows_are_independent_and_validation_runner_has_no_secrets(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        for name in ('fix-gitcode-issue', 'review-gitcode-pr'):
            workflow = yaml.safe_load((root / f'.github/workflows/{name}.yml').read_text(encoding='utf-8'))
            self.assertEqual(set(workflow.get('on', workflow.get(True))), {'workflow_dispatch'})
            self.assertNotIn('issue_reply', json.dumps(workflow))
            self.assertNotIn('reply-gitcode-issue', json.dumps(workflow))
        workflow = yaml.safe_load((root / '.github/workflows/fix-gitcode-issue.yml').read_text(encoding='utf-8'))
        self.assertNotIn('secrets.', json.dumps(workflow['jobs']['validate']))
        self.assertEqual(workflow['jobs']['publish']['needs'], 'validate')
        self.assertNotIn('roles', json.dumps(workflow))

    def test_fix_publishes_to_fork_then_creates_pr_and_compile(self):
        from scripts.gitcode_issue_reply import snapshot, fingerprint
        issue = {'state': 'open', 'number': '739', 'title': 'Bug', 'body': 'Repro', 'user': {'login': 'committer'}}
        identity = {'id': 'bot', 'login': 'bot-account'}
        context = {'number': '739', 'source_sha': HEAD, 'user_id': 'bot',
                   'fingerprint': fingerprint(snapshot(issue, [], 'bot'))}
        branch = f'codex/issue-739-{HEAD[:12]}'
        marker = f'<!-- issue-fix:739:{HEAD} -->'
        pr = {'number': 123, 'state': 'open', 'body': marker, 'user': identity,
              'head': {'ref': branch, 'repo': {'full_name': 'bot-account/catlass'}}}
        api = API()
        calls = []

        def request(method, path, body=None, **kwargs):
            calls.append((method, path, body))
            if path == '/user':
                return identity
            if path == '/repos/bot-account/catlass':
                return {'fork': True, 'parent': {'full_name': 'cann/catlass'}}
            if path.startswith(task.ROOT + '/pulls?'):
                return []
            if path == task.ROOT + '/pulls' and method == 'POST':
                return pr
            if path == task.ROOT + '/pulls/123':
                return pr
            return api.request(method, path, body, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory)
            task.save(result / 'validation.json', {'result': 'validated', 'command': 'test',
                      'patch_sha': task.hashlib.sha256(b'patch').hexdigest()})
            client = unittest.mock.Mock()
            client.issue.return_value = issue
            client.comments.return_value = []
            publisher = unittest.mock.Mock()
            publisher.request.side_effect = request
            with patch.dict(os.environ, {'GITCODE_TOKEN': 'test-only'}), \
                    patch.object(task, 'Client', return_value=client), \
                    patch.object(task, 'restore_fix'), patch.object(task, 'apply_fix', return_value=True), \
                    patch.object(task, 'git', return_value=b'patch'), patch.object(task, 'push_branch') as push:
                response = task.publish_fix(publisher, context, {'summary': 'Fix boundary'}, result / 'source', 'test', result)
            self.assertEqual(response['pr_number'], '123')
            push.assert_called_once_with(result / 'source', 'bot-account', branch)
            create = next(body for method, path, body in calls if method == 'POST' and path == task.ROOT + '/pulls')
            self.assertEqual(create['head'], 'bot-account:' + branch)
            self.assertEqual(create['base'], 'master')
            self.assertEqual(api.writes, [{'body': 'compile'}])

    def test_complex_fix_publication_has_no_api_or_push(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory)
            task.save(result / 'validation.json', {'result': 'needs-human'})
            api = unittest.mock.Mock()
            self.assertEqual(task.publish_fix(api, {}, {}, result / 'source', 'test', result), {'result': 'needs-human'})
            api.request.assert_not_called()

    def test_validation_has_no_publishing_credentials_and_failure_propagates(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GITCODE_TOKEN': 'secret', 'TRAE_CN_PAT': 'secret'}):
            with patch.object(task.subprocess, 'run') as run:
                task.validate_fix(Path(directory), 'test-command', Path(directory) / 'log')
                env = run.call_args.kwargs['env']
                self.assertNotIn('GITCODE_TOKEN', env)
                self.assertNotIn('TRAE_CN_PAT', env)
                self.assertTrue(run.call_args.kwargs['check'])
            with self.assertRaises(ValueError):
                task.validate_fix(Path(directory), '', Path(directory) / 'log')


if __name__ == '__main__':
    unittest.main()
