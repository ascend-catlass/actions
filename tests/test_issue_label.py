"""Verify Issue classification and additive, stale-safe publication."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import yaml
from scripts import issue_label as policy
from shared_actions._lib.traecn_result import TraeResult


class API:
    def __init__(self):
        self.value = {'title': 'Documentation examples are missing', 'body': 'Add a tutorial.',
                      'state': 'open', 'labels': [{'name': 'Agent'}], 'user': {'login': 'yuantao_'}}
        self.catalogue = [{'name': name, 'description': 'Issue kind'} for name in
                          ['documentation', 'feature', 'bug-report', 'wontfix', 'question']]
        self.writes = []
        self.pages = None

    def request(self, method, path, body=None, **kwargs):
        if '/labels?' in path:
            if self.pages is not None:
                page = int(path.rsplit('page=', 1)[1])
                return copy.deepcopy(self.pages[page - 1])
            return copy.deepcopy(self.catalogue)
        if method == 'POST':
            self.writes.append((path, body, kwargs))
            self.value['labels'].extend({'name': name} for name in body)
            return copy.deepcopy(self.value['labels'])
        return copy.deepcopy(self.value)


def context(api):
    return {'number': '739', 'fingerprint': policy.digest(policy.snapshot(api.value)),
            'labels': policy.available(api)}


def answer(label='documentation', reason='The Issue requests a tutorial.'):
    return TraeResult(json.dumps({'label': label, 'reason': reason}), 'configured-model')


class IssueLabelTests(unittest.TestCase):
    def test_prepare_includes_role_authors_and_only_existing_kind_labels(self):
        api = API()
        api.catalogue.append({'name': 'approved', 'description': 'Not an Issue kind'})
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.assertEqual(policy.prepare(api, '739', directory), 'ready')
            data = json.loads((directory / 'context.json').read_text(encoding='utf-8'))
            schema = json.loads((directory / 'schema.json').read_text(encoding='utf-8'))
            self.assertEqual(set(data['labels']), set(schema['properties']['label']['enum']))
            self.assertNotIn('approved', data['labels'])
            self.assertIn('untrusted', (directory / 'prompt.md').read_text(encoding='utf-8').lower())
        self.assertEqual(api.writes, [])

    def test_publish_adds_exactly_one_label_and_preserves_other_labels(self):
        api = API()
        result = policy.publish(api, context(api), answer())
        self.assertEqual(result['result'], 'labeled')
        self.assertEqual(result['model'], 'configured-model')
        self.assertEqual(api.writes, [('/repos/cann/catlass/issues/739/labels', ['documentation'], {'encoding': 'json'})])
        self.assertEqual(policy.names(api.value['labels']), {'documentation', 'Agent'})

    def test_repeated_delivery_and_manual_classification_do_not_write(self):
        for label in ['documentation', 'feature', 'bug-report', 'wontfix']:
            api = API()
            prepared = context(api)
            api.value['labels'].append({'name': label})
            self.assertEqual(policy.publish(api, prepared, answer())['result'], 'already_classified')
            self.assertEqual(api.writes, [])

    def test_closed_and_confidential_issues_skip_prepare_and_publish(self):
        for change, expected in [({'state': 'closed'}, 'issue_not_open'),
                                 ({'confidential': True}, 'confidential_issue')]:
            api = API()
            prepared = context(api)
            api.value.update(change)
            with tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(policy.prepare(api, '739', Path(tmp)), expected)
            self.assertEqual(policy.publish(api, prepared, answer())['result'], expected)
            self.assertEqual(api.writes, [])

    def test_changed_text_or_labels_is_rejected_without_writing(self):
        for change in [{'title': 'Different request'}, {'body': 'Edited'}, {'labels': []}]:
            api = API()
            prepared = context(api)
            api.value.update(change)
            with self.assertRaisesRegex(ValueError, 'Issue changed'):
                policy.publish(api, prepared, answer())
            self.assertEqual(api.writes, [])

    def test_deleted_label_is_rejected(self):
        api = API()
        prepared = context(api)
        api.catalogue = []
        with self.assertRaisesRegex(ValueError, 'no longer exists'):
            policy.publish(api, prepared, answer())
        self.assertEqual(api.writes, [])

    def test_malformed_or_invented_model_output_never_writes(self):
        for data in [[], {'label': 'documentation'}, {'label': 'approved', 'reason': 'Do it'},
                     {'label': 'invented', 'reason': 'Do it'}, {'label': ['documentation'], 'reason': 'x'},
                     {'label': 'documentation', 'reason': ''},
                     {'label': 'documentation', 'reason': 'x', 'extra': True}]:
            api = API()
            with self.assertRaises(ValueError):
                policy.publish(api, context(api), TraeResult(json.dumps(data), 'model'))
            self.assertEqual(api.writes, [])

    def test_label_catalogue_is_paginated(self):
        api = API()
        api.pages = [[{'name': f'other-{i}'} for i in range(100)], [{'name': 'documentation'}]]
        self.assertEqual(policy.available(api), {'documentation': ''})

    def test_readback_failure_is_not_reported_as_success(self):
        class Broken(API):
            def request(self, method, path, body=None, **kwargs):
                if method == 'POST':
                    return []
                return super().request(method, path, body, **kwargs)
        api = Broken()
        with self.assertRaisesRegex(ValueError, 'read-back'):
            policy.publish(api, context(api), answer())

    def test_input_number_and_empty_catalogue_fail_closed(self):
        for value in ['0', '../1', '1?x=2', '１２', None]:
            with self.assertRaises(ValueError):
                policy.number(value)
        api = API()
        api.catalogue = []
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'No existing'):
                policy.prepare(api, '739', Path(tmp))

    def test_workflow_uses_token_free_shared_model_stage_and_serializes_issues(self):
        root = Path(__file__).resolve().parents[1]
        workflow = yaml.safe_load((root / '.github/workflows/reply-atomgit-issue.yml').read_text(encoding='utf-8'))
        steps = workflow['jobs']['reply']['steps']
        model = next(step for step in steps if step.get('id') == 'trae')
        self.assertEqual(model['uses'], './.github/actions/catlass-ai')
        self.assertNotIn('ATOMGIT_TOKEN', json.dumps(model))
        self.assertNotIn('GITCODE_TOKEN', json.dumps(model))
        self.assertEqual(workflow['concurrency']['cancel-in-progress'], False)
        publishers = [step for step in steps if step.get('with', {}).get('operation') == 'publish']
        self.assertEqual({step['with']['stage-result'] for step in publishers},
                         {'_issue-analysis/label', '_issue-analysis/reply'})
        self.assertEqual(sum(step.get('uses') == './.github/actions/catlass-ai' for step in steps), 1)
        self.assertFalse((root / '.github/workflows/label-atomgit-issue.yml').exists())


if __name__ == '__main__':
    unittest.main()
