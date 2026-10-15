const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawnSync} = require('node:child_process');

const root = path.resolve(__dirname, '..');
const workflow = fs.readFileSync(path.join(root, '.github/workflows/test-gitcode-pr.yml'), 'utf8').replace(/\r\n/g, '\n');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
function inlineStep(id) {
  const step = workflow.split(`        id: ${id}\n`)[1].split('\n      - name:')[0];
  return step.split('          script: |\n')[1].split('\n').map(line => line.slice(12)).join('\n');
}
async function execute(id, {github = {}, env = {}, files = {}} = {}) {
  const writes = {};
  const fakeFs = {
    mkdirSync() {},
    writeFileSync(file, value) { writes[file] = value; },
    readFileSync(file) { if (!(file in files)) throw Error('Missing fixture'); return files[file]; },
    statSync(file) { if (!(file in files)) throw Error('Missing fixture'); return {size: Buffer.byteLength(files[file])}; }
  };
  await new AsyncFunction('github', 'context', 'core', 'require', 'process', 'Buffer', inlineStep(id))(
    github, {repo: {owner: 'ascend-catlass', repo: 'actions'}, runId: 100}, {warning(){}},
    name => { assert.equal(name, 'node:fs'); return fakeFs; }, {env}, Buffer);
  return writes;
}

test('github-script selects the current attempt and appends bounded, scrubbed log evidence', async () => {
  let listed, downloaded;
  const github = {
    rest: {actions: {listJobsForWorkflowRunAttempt() {}, async downloadJobLogsForWorkflowRun(args) {
      downloaded = args;
      return {data: 'error: unknown type Tile\nAuthorization: Bearer private-value\n' + 'x'.repeat(100000) + '\nFAILED test_tile'};
    }}},
    async paginate(method, args) {
      assert.equal(method, this.rest.actions.listJobsForWorkflowRunAttempt);
      listed = args;
      return [{id: 17, name: 'Test PR #1459', conclusion: 'failure', steps: [{name: 'Build DSL', conclusion: 'failure'}]},
        {id: 18, name: 'Report PR result', conclusion: 'success'}];
    }
  };
  const writes = await execute('context', {github, env: {PR_NUMBER: '1459', GITHUB_RUN_ATTEMPT: '2'},
    files: {'.github/prompts/rdv-failure-analysis.md': 'Read-only diagnosis'}});
  assert.equal(listed.run_id, 100);
  assert.equal(listed.attempt_number, 2);
  assert.equal(downloaded.job_id, 17);
  const prompt = writes['_rdv-failure/prompt.md'];
  assert.match(prompt, /unknown type Tile/);
  assert.match(prompt, /FAILED test_tile/);
  assert.match(prompt, /Build DSL/);
  assert.doesNotMatch(prompt, /private-value/);
  assert.ok(Buffer.byteLength(prompt) < 100000);
});

test('github-script refuses a mismatched PR job before downloading logs', async () => {
  const github = {rest: {actions: {}}, async paginate() {
    return [{id: 17, name: 'Test PR #123', conclusion: 'failure'}];
  }};
  await assert.rejects(execute('context', {github, env: {PR_NUMBER: '1459', GITHUB_RUN_ATTEMPT: '1'}}), /Expected one/);
});

test('renderer accepts a concise diagnosis and includes DeepSeek attribution', async () => {
  const files = {answer: JSON.stringify({cause: '编译失败', evidence: 'unknown type Tile', next_step: '检查类型定义'})};
  const writes = await execute('render_analysis', {env: {ANALYSIS_RESPONSE: 'answer'}, files});
  assert.match(writes['_rdv-failure/analysis.md'], /unknown type Tile/);
  assert.match(writes['_rdv-failure/analysis.md'], /DeepSeek-V4.1-Flash/);
});

test('renderer preserves reporting for missing, malformed, blank or oversized model answers', async () => {
  for (const value of [undefined, 'not json', '{}', 'x'.repeat(20001),
    JSON.stringify({cause: ' ', evidence: 'log', next_step: 'fix'})]) {
    const files = value === undefined ? {} : {answer: value};
    const writes = await execute('render_analysis', {env: {ANALYSIS_RESPONSE: 'answer'}, files});
    assert.match(writes['_rdv-failure/analysis.md'], /自动分析暂不可用/);
  }
});

test('workflow uses maintained Actions and keeps diagnosis separate from final reporting', () => {
  const job = workflow.split('  analyze-failure:\n')[1].split('  report:\n')[0];
  assert.match(job, /uses: actions\/github-script@v9/g);
  assert.match(job, /model: DeepSeek-V4.1-Flash/);
  assert.match(job, /sandbox: read-only/);
  assert.doesNotMatch(job, /python|GITCODE_TOKEN/);
  assert.ok(!fs.existsSync(path.join(root, 'scripts/rdv_failure_analysis.py')));
  const report = workflow.split('  report:\n')[1];
  assert.match(report, /always\(\)/);
  assert.match(report, /uses: actions\/download-artifact@v4/);
  assert.doesNotMatch(report, /needs\.analyze-failure\.result/);
});

const bashAvailable = spawnSync('bash', ['--version']).status === 0;
const jqAvailable = spawnSync('jq', ['--version']).status === 0;
test('actual RDV Bash posts literal analysis only on failure, with a safe size limit',
  {skip: !bashAvailable || !jqAvailable}, () => {
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'rdv-comment-'));
    try {
      const mock = path.join(temp, 'curl');
      fs.writeFileSync(mock, `#!/usr/bin/env bash
set -eu
url=''; data=''
while (( $# )); do
  case "$1" in
    --request|--header) shift 2;;
    --data) data="$2"; shift 2;;
    https://*) url="$1"; shift;;
    *) shift;;
  esac
done
if [[ "$url" == */comments ]]; then printf '%s' "$data" > "$COMMENT_CAPTURE"; printf '{"id":42}'; else printf '[]'; fi
`);
      for (const [result, attachment] of [['failure', '原因：编译失败\n`$(touch injected)`'],
        ['success', 'do not append'], ['cancelled', 'do not append'], ['failure', 'x'.repeat(8193)], ['failure', null]]) {
        const file = path.join(temp, 'analysis.md');
        if (attachment === null) fs.rmSync(file, {force: true}); else fs.writeFileSync(file, attachment);
        const capture = path.join(temp, 'comment.json');
        const run = spawnSync('bash', ['-c', 'curl() { bash "$MOCK_CURL" "$@"; }; export -f curl; source "$STATUS_SCRIPT"'], {
          encoding: 'utf8', env: {...process.env, RDV_PHASE: 'finish', RDV_RESULT: result,
            PR_NUMBER: '1459', GITCODE_TOKEN: 'test-only', RDV_RESULT_URL: 'https://github.com/run/123',
            RDV_FAILURE_ANALYSIS_FILE: file, MOCK_CURL: mock, COMMENT_CAPTURE: capture,
            STATUS_SCRIPT: path.join(root, '.github/actions/rdv-status/rdv-status.sh')}
        });
        assert.equal(run.status, 0, run.stderr);
        const expected = (result === 'success' ? '✅ RDV Succeeded' : '❌ RDV Failed') + ': https://github.com/run/123'
          + (result === 'failure' && attachment && attachment.length <= 8192 ? '\n\n' + attachment : '');
        assert.equal(JSON.parse(fs.readFileSync(capture, 'utf8')).body, expected);
      }
    } finally {
      // Only remove the exact temporary directory created by this test.
      assert.equal(path.dirname(path.resolve(temp)), path.resolve(os.tmpdir()));
      fs.rmSync(temp, {recursive: true, force: true});
    }
  });
