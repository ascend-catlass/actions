import copy
import unittest
from shared_actions._lib import operations
from scripts.issue_reply_policy import check_publication
from scripts.atomgit_issue_reply import MARKER, LEGACY_MARKER

URL = 'https://atomgit.com/cann/catlass/issues/739'
ROLES = {'repository': 'cann/catlass', 'maintainer_ids': ['Owner'], 'committer_ids': []}


class API:
    def __init__(self):
        self.issue = {'number': 739, 'title': 'Bug', 'body': 'Repro', 'state': 'open', 'user': {'login': 'contributor'}}
        self.comments = []
        self.writes = []

    def request(self, method, path, body=None, *args):
        if path == '/user': return {'id': 'bot'}
        if method == 'PATCH':
            self.writes.append((path, body))
            self.comments[0]['body'] = body['body']
            return {}
        if '/issues/comments/' in path: return copy.deepcopy(self.comments[0])
        if '/comments?' in path: return copy.deepcopy(self.comments)
        return copy.deepcopy(self.issue)

    def context(self):
        return {'issue_url': URL, 'user_id': 'bot', 'source_sha': 'a'*40,
                'fingerprint': operations.digest(operations.snapshot(self.issue, self.comments, 'bot'))}


class PolicyTests(unittest.TestCase):
    def test_publish_checks_current_role_before_migration(self):
        api = API()
        metadata = api.context()
        api.issue['user']['login'] = 'Owner'
        with self.assertRaisesRegex(ValueError, 'ineligible'):
            check_publication(api, metadata, '有依据的回复', ROLES)
        self.assertEqual(api.writes, [])

    def test_changed_discussion_blocks_legacy_migration(self):
        api = API()
        metadata = api.context()
        api.comments.append({'id': 1, 'body': 'new evidence'})
        with self.assertRaisesRegex(ValueError, 'discussion changed'):
            check_publication(api, metadata, '有依据的回复', ROLES)
        self.assertEqual(api.writes, [])

    def test_existing_reply_migrates_without_duplicate_and_remains_idempotent(self):
        for marker in (MARKER, LEGACY_MARKER):
            api = API()
            api.comments = [{'id': 42, 'body': marker + '\nOld answer', 'user': {'id': 'bot'}}]
            metadata = check_publication(api, api.context(), '检查边界条件。', ROLES)
            self.assertEqual(api.comments[0]['id'], 42)
            self.assertIn(operations.MARKER, api.comments[0]['body'])
            self.assertEqual(metadata['fingerprint'], api.context()['fingerprint'])
            operations.comment(api, metadata, '检查边界条件。', 'DeepSeek-V4.1-Flash', self.output())
            self.assertEqual(len(api.comments), 1)
            self.assertIn('检查边界条件。', api.comments[0]['body'])
            self.assertEqual(len(api.writes), 2)

    def output(self):
        import tempfile
        from pathlib import Path
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Path(folder.name) / 'published.json'

    def test_project_prose_and_marker_policy(self):
        api = API()
        for answer in ['', 'x'*2401, MARKER, 'TRAE 自动分析', 'By model']:
            with self.subTest(answer=answer[:20]), self.assertRaises(ValueError):
                check_publication(api, api.context(), answer, ROLES)
        self.assertEqual(api.writes, [])

    def test_multiple_owned_comments_and_identity_changes_are_rejected(self):
        api = API()
        api.comments = [{'id': n, 'body': MARKER, 'user': {'id': 'bot'}} for n in (1, 2)]
        with self.assertRaisesRegex(ValueError, 'Multiple owned'):
            check_publication(api, api.context(), '回复', ROLES)
        context = api.context()
        context['user_id'] = 'someone-else'
        with self.assertRaisesRegex(ValueError, 'identity'):
            check_publication(api, context, '回复', ROLES)
        self.assertEqual(api.writes, [])
