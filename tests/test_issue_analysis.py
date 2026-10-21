"""Combined Issue analysis uses one response and preserves execution provenance."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.issue_analysis import prepare, extract
from shared_actions._lib.traecn_result import load_result


class CombinedIssueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = Path.cwd()
        os.chdir(self.temp.name)
        Path('_issue-source/.action-context').mkdir(parents=True)
        Path('_issue-source/.action-context/prompt.md').write_text('Source and discussion', encoding='utf-8')
        Path('_issue-label-result').mkdir()
        Path('_issue-label-result/prompt.md').write_text('Untrusted Issue and candidates', encoding='utf-8')
        Path('_issue-label-result/labels.json').write_text('{"bug-report":""}', encoding='utf-8')
        self.directory = Path('_issue-analysis')
        self.stage = Path('stage')
        self.stage.mkdir()
        self.record = {'status': 'success', 'exit_code': 0, 'requested_model': 'original-model',
                       'cli_version': 'setup-version', 'custom_provenance': 'preserved'}
        self.answer = {'label': 'bug-report', 'reason': 'A reported hang.', 'reply': 'See kernel.cpp:42.'}

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def write_stage(self):
        (self.stage / 'result.json').write_text(json.dumps(self.record), encoding='utf-8')
        (self.stage / 'response.md').write_text(json.dumps(self.answer), encoding='utf-8')

    def test_both_tasks_share_prompt_and_keep_exact_provenance(self):
        self.assertTrue(prepare(self.directory, reply=True, label=True))
        text = (self.directory / 'prompt.md').read_text(encoding='utf-8')
        self.assertIn('Source and discussion', text)
        self.assertIn('Untrusted Issue', text)
        self.assertEqual(text, Path('_issue-source/.action-context/combined.md').read_text(encoding='utf-8'))
        self.write_stage()
        extract(self.directory, self.stage)
        self.assertEqual(load_result(self.directory / 'reply').body, self.answer['reply'])
        self.assertEqual(load_result(self.directory / 'label').json()['label'], 'bug-report')
        for task in ('label', 'reply'):
            record = json.loads((self.directory / task / 'result.json').read_text(encoding='utf-8'))
            self.assertEqual({key: record[key] for key in self.record}, self.record)
            self.assertEqual(len(record['projection']['source_response_sha256']), 64)

    def test_role_author_classifies_without_source_or_reply(self):
        self.assertTrue(prepare(self.directory, reply=False, label=True))
        self.assertNotIn('Source and discussion', (self.directory / 'prompt.md').read_text(encoding='utf-8'))
        self.answer['reply'] = ''
        self.write_stage()
        extract(self.directory, self.stage)
        self.assertFalse((self.directory / 'reply').exists())

    def test_manual_label_still_allows_analysis_only(self):
        self.assertTrue(prepare(self.directory, reply=True, label=False))
        self.answer.update(label=None, reason='')
        self.write_stage()
        extract(self.directory, self.stage)
        self.assertFalse((self.directory / 'label').exists())
        self.assertTrue((self.directory / 'reply').is_dir())

    def test_nothing_to_do_does_not_request_model(self):
        self.assertFalse(prepare(self.directory, reply=False, label=False))
        self.assertFalse((self.directory / 'schema.json').exists())

    def test_invalid_or_failed_model_does_not_produce_publication_results(self):
        prepare(self.directory, reply=True, label=True)
        for answer in [{}, {**self.answer, 'label': 'invented'},
                       {**self.answer, 'reply': 'x' * 2401}, {**self.answer, 'reply': None},
                       {**self.answer, 'reason': ''}, {**self.answer, 'extra': True}]:
            (self.stage / 'response.md').write_text(json.dumps(answer), encoding='utf-8')
            (self.stage / 'result.json').write_text(json.dumps(self.record), encoding='utf-8')
            with self.assertRaises(ValueError):
                extract(self.directory, self.stage)
        self.write_stage()
        self.record['status'] = 'failed'
        self.write_stage()
        with self.assertRaises(ValueError):
            extract(self.directory, self.stage)
        self.assertFalse((self.directory / 'reply').exists())
        self.assertFalse((self.directory / 'label').exists())


if __name__ == '__main__':
    unittest.main()
