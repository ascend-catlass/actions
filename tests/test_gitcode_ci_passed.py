"""Exercise the migrated reminder against a mock GitCode API."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gitcode_ci_passed import MESSAGE, remind


class API:
    def __init__(self, pr=None, pages=None):
        self.pr = pr if pr is not None else {'state': 'open', 'labels': [{'name': 'ci-pipeline-passed'}]}
        self.pages = iter(pages if pages is not None else [[]])
        self.calls = []

    def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path, body, kwargs))
        if method == 'POST':
            return {'id': 1}
        if '/comments?' in path:
            return next(self.pages)
        return self.pr


class ReminderTests(unittest.TestCase):
    def test_posts_original_message_after_checking_current_pr(self):
        api = API()
        self.assertEqual(remind(api, '123'), 'commented')
        self.assertEqual(api.calls[0][:2], ('GET', '/repos/cann/catlass/pulls/123'))
        self.assertEqual(api.calls[-1], ('POST', '/repos/cann/catlass/pulls/123/comments',
                                        {'body': MESSAGE}, {'encoding': 'json'}))
        self.assertIn('SIG', MESSAGE)
        self.assertIn('`rdvcompile`', MESSAGE)

    def test_skips_closed_or_no_longer_passed_pr(self):
        for pr, reason in [({'state': 'closed', 'labels': ['ci-pipeline-passed']}, 'pr_not_open'),
                           ({'state': 'open', 'labels': []}, 'label_not_present')]:
            api = API(pr=pr)
            self.assertEqual(remind(api, '123'), reason)
            self.assertEqual(len(api.calls), 1)

    def test_label_formats(self):
        for label in ['ci-pipeline-passed', {'title': 'ci-pipeline-passed'}, {'name': 'ci-pipeline-passed'}]:
            self.assertEqual(remind(API(pr={'state': 'opened', 'labels': [label]}), '123'), 'commented')

    def test_redelivery_scans_all_pages_and_does_not_post(self):
        api = API(pages=[[{'body': 'other'}] * 100, [{'body': MESSAGE}]])
        self.assertEqual(remind(api, '123'), 'already_reminded')
        self.assertTrue(api.calls[-1][1].endswith('page=2&comment_type=pr_comment'))
        self.assertFalse(any(call[0] == 'POST' for call in api.calls))

    def test_exact_page_boundary_fetches_next_page(self):
        api = API(pages=[[{'body': 'other'}] * 100, []])
        self.assertEqual(remind(api, '123'), 'commented')
        self.assertEqual(len(api.calls), 4)

    def test_invalid_numbers_fail_before_api_access(self):
        for number in ['', '0', '-1', '1/other', '1?x=2', '１２３', None]:
            api = API()
            with self.assertRaises(ValueError):
                remind(api, number)
            self.assertEqual(api.calls, [])

    def test_malformed_api_responses_never_post(self):
        for api in [API(pr=[]), API(pr={'state': 'open'}), API(pages=[{}])]:
            with self.assertRaises(ValueError):
                remind(api, '123')
            self.assertFalse(any(call[0] == 'POST' for call in api.calls))

    def test_api_failure_is_not_reported_as_success(self):
        class FailingAPI(API):
            def request(self, *args, **kwargs):
                raise RuntimeError('HTTP 403')
        with self.assertRaises(RuntimeError):
            remind(FailingAPI(), '123')


if __name__ == '__main__':
    unittest.main()
