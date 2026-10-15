import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import yaml
from scripts import rdv_failure_analysis as analysis

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash')


class Logs:
    def __init__(self, name='Test PR #1459'):
        self.paths = []
        self.jobs = [{'id': 17, 'name': name, 'conclusion': 'failure', 'steps': [
            {'name': 'Build DSL', 'conclusion': 'failure', 'number': 6},
            {'name': 'Cleanup', 'conclusion': 'success', 'number': 7}]}]

    def json(self, path):
        self.paths.append(path)
        return {'jobs': self.jobs}

    def log(self, path):
        self.paths.append(path)
        return 'compiler: error: unknown type Tile\n'


class FailureAnalysisTests(unittest.TestCase):
    def test_current_attempt_and_failed_steps_only(self):
        logs = Logs()
        context = analysis.collect(logs, '100', '2', '1459')
        self.assertIn('/runs/100/attempts/2/jobs?', logs.paths[0])
        self.assertEqual(logs.paths[1], '/actions/jobs/17/steps/5/logs')
        self.assertEqual(context['failed_steps'], ['Build DSL'])
        self.assertIn('unknown type Tile', context['evidence'][0]['log_tail'])

    def test_preparation_and_legacy_job_names_are_supported(self):
        for name in ['Test PR', 'Register and classify PR test']:
            self.assertEqual(analysis.collect(Logs(name), '100', '1', '1459')['job_id'], '17')

    def test_missing_or_wrong_job_cannot_produce_a_diagnosis(self):
        for logs in [Logs('Test PR #123'), Logs('Report PR result')]:
            with self.assertRaises(ValueError):
                analysis.collect(logs, '100', '1', '1459')
        with self.assertRaises(ValueError):
            analysis.collect(Logs(), '../old-run', '1', '1459')

    def test_unavailable_step_endpoint_uses_bounded_job_fallback(self):
        logs = Logs()
        with patch.object(logs, 'log', side_effect=[ValueError('unavailable'), 'error: build failed']):
            self.assertIn('Job log tail', analysis.collect(logs, '100', '1', '1459')['evidence'][0]['step'])

    def test_download_redirect_never_receives_the_api_token(self):
        client = analysis.GitHubLogs('secret-read-token')
        redirect = urllib.error.HTTPError('https://api.github.com/fixed', 302, 'Found',
                    {'Location': 'https://blob.example/log?signature=private'}, None)
        with patch.object(client, 'request', side_effect=redirect), \
                patch('urllib.request.urlopen', return_value=io.BytesIO(b'error')) as download:
            self.assertEqual(client.log('/actions/jobs/17/logs'), 'error')
        request = download.call_args.args[0]
        self.assertIsNone(request.get_header('Authorization'))
        self.assertEqual(request.get_header('Range'), 'bytes=-131072')

    def test_large_or_unsafe_download_is_rejected(self):
        client = analysis.GitHubLogs('token')
        with patch.object(client, 'request', return_value=io.BytesIO(b'x' * (analysis.LOG_LIMIT + 1))):
            with self.assertRaises(ValueError):
                client.log('/actions/jobs/17/logs')
        error = urllib.error.HTTPError('https://api.github.com/fixed', 302, 'Found',
                                      {'Location': 'http://untrusted/log'}, None)
        with patch.object(client, 'request', side_effect=error), patch('urllib.request.urlopen') as download:
            with self.assertRaises(ValueError):
                client.log('/actions/jobs/17/logs')
            download.assert_not_called()

    def test_redaction_and_bounded_diagnosis(self):
        with patch.dict(os.environ, {'GH_TOKEN': 'private-value'}):
            text = analysis.redact('private-value Authorization: Bearer abc123 PRIVATE-TOKEN: xyz access_token=foo&x=1 ghp_abcdef')
        for secret in ['private-value', 'abc123', 'xyz', 'foo', 'ghp_abcdef']:
            self.assertNotIn(secret, text)
        rendered = analysis.render({'cause': '编译失败。', 'evidence': 'error: unknown type Tile', 'next_step': '检查类型定义与头文件。'})
        self.assertIn('DeepSeek-V4.1-Flash', rendered)
        self.assertIn('unknown type Tile', rendered)
        with self.assertRaises(ValueError):
            analysis.render({'cause': 'x' * 2001, 'evidence': 'log', 'next_step': 'fix'})

    def test_missing_invalid_and_oversized_model_output_render_fallback(self):
        for content in [None, 'not JSON', '{"cause":"only"}', 'x' * 20001]:
            with self.subTest(content=str(content)[:20]), tempfile.TemporaryDirectory() as directory:
                answer = Path(directory) / 'response'
                if content is not None:
                    answer.write_text(content, encoding='utf-8')
                with patch.object(analysis, 'Path', side_effect=lambda p: Path(directory) / p if p == '_rdv-failure' else Path(p)), \
                        patch.dict(os.environ, {'ANALYSIS_RESPONSE': str(answer)}), \
                        patch('sys.argv', ['analysis', 'render']):
                    analysis.main()
                self.assertEqual((Path(directory) / '_rdv-failure/analysis.md').read_text(encoding='utf-8').strip(), analysis.FALLBACK)

    def test_report_is_independent_of_optional_analysis_and_model_has_no_publishing_token(self):
        jobs = yaml.safe_load((ROOT / '.github/workflows/test-gitcode-pr.yml').read_text(encoding='utf-8'))['jobs']
        diagnostic = jobs['analyze-failure']
        self.assertEqual(diagnostic['runs-on'], 'ubuntu-22.04')
        self.assertIn("needs.merge-and-test.result == 'failure'", diagnostic['if'])
        self.assertIn("needs.prepare.result == 'failure'", diagnostic['if'])
        model = next(s for s in diagnostic['steps'] if s.get('id') == 'analysis')
        self.assertTrue(model['continue-on-error'])
        self.assertEqual(model['with']['model'], analysis.MODEL)
        self.assertEqual(model['with']['sandbox'], 'read-only')
        self.assertNotIn('GITCODE_TOKEN', json.dumps(diagnostic))
        self.assertNotIn('GH_TOKEN', json.dumps(model))
        reporter = jobs['report']
        self.assertIn('always()', reporter['if'])
        final = reporter['steps'][-1]
        self.assertEqual(final['if'], '${{ always() }}')
        self.assertNotIn('needs.analyze-failure.result', final['with']['result'])


@unittest.skipUnless(BASH and shutil.which('jq'), 'Bash and jq required')
class RDVCommentTests(unittest.TestCase):
    def run_status(self, result, attachment):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            details = temp / 'analysis.md'
            if attachment is not None:
                details.write_text(attachment, encoding='utf-8', newline='\n')
            curl = temp / 'curl'
            curl.write_text('''#!/usr/bin/env bash
set -eu
method=GET; url=''; data=''
while (( $# )); do
  case "$1" in
    --request) method="$2"; shift 2;;
    --header) shift 2;;
    --data) data="$2"; shift 2;;
    https://*) url="$1"; shift;;
    *) shift;;
  esac
done
if [[ "$url" == */comments ]]; then
  printf '%s' "$data" > "$COMMENT_CAPTURE"
  printf '{"id":42}'
else
  printf '[]'
fi
''', encoding='utf-8', newline='\n')
            curl.chmod(0o755)
            capture = temp / 'comment.json'
            env = {**os.environ, 'PATH': temp.as_posix() + os.pathsep + os.environ['PATH'],
                   'COMMENT_CAPTURE': capture.as_posix(), 'RDV_PHASE': 'finish', 'RDV_RESULT': result,
                   'GITCODE_TOKEN': 'test-only', 'PR_NUMBER': '1459', 'RDV_RESULT_URL': 'https://github.com/run/123',
                   'RDV_FAILURE_ANALYSIS_FILE': details.as_posix(), 'MOCK_CURL': curl.as_posix(),
                   'STATUS_SCRIPT': (ROOT / '.github/actions/rdv-status/rdv-status.sh').as_posix()}
            process = subprocess.run([BASH, '-c', 'curl() { bash "$MOCK_CURL" "$@"; }; export -f curl; source "$STATUS_SCRIPT"'],
                                     env=env, text=True, capture_output=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(capture.read_text(encoding='utf-8'))['body']

    def test_actual_failure_comment_appends_literal_analysis(self):
        attachment = '原因：编译失败。\n`$(touch injected)`\n建议检查 Tile 定义。'
        self.assertEqual(self.run_status('failure', attachment),
                         '❌ RDV Failed: https://github.com/run/123\n\n' + attachment)

    def test_success_cancelled_and_missing_analysis_keep_original_comment(self):
        for result, prefix in [('success', '✅ RDV Succeeded'), ('cancelled', '❌ RDV Failed'), ('failure', '❌ RDV Failed')]:
            self.assertEqual(self.run_status(result, None if result == 'failure' else 'do not append'),
                             prefix + ': https://github.com/run/123')

    def test_oversized_analysis_does_not_block_result_reporting(self):
        self.assertEqual(self.run_status('failure', 'x' * 8193), '❌ RDV Failed: https://github.com/run/123')


if __name__ == '__main__':
    unittest.main()
