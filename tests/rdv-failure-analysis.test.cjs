const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const {makePrompt, renderComment, main, fallback} = require('../.github/actions/analyze-ci-failure/comment.cjs');
const read = name => fs.readFileSync(path.join(root, name), 'utf8').replace(/\r\n/g, '\n');

function temporaryTest(work) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ci-failure-'));
  try { return work(directory); }
  finally {
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    fs.rmSync(directory, {recursive: true, force: true});
  }
}

test('prompt accepts different CI jobs without PR-specific inputs and bounds/scrubs logs', () => {
  const evidence = [{job: 'Publish release', steps: ['Build package'],
    log: 'error: unknown type Tile\nAuthorization: Bearer private-value\n' + 'x'.repeat(100000) + '\nFAILED test_tile'}];
  const prompt = makePrompt(evidence, 'Read-only diagnosis');
  assert.match(prompt, /Publish release/);
  assert.match(prompt, /unknown type Tile/);
  assert.match(prompt, /FAILED test_tile/);
  assert.doesNotMatch(prompt, /private-value/);
  assert.ok(Buffer.byteLength(prompt) < 30000);
  assert.throws(() => makePrompt([], 'template'), /failed jobs/);
});

test('prompt preparation leaves only bounded model input in its isolated workspace', () => temporaryTest(directory => {
  fs.writeFileSync(path.join(directory, 'evidence.json'), JSON.stringify([{job: 'Unit tests', steps: ['pytest'], log: 'FAILED case'}]));
  main('prepare', {ANALYSIS_DIRECTORY: directory});
  assert.equal(fs.existsSync(path.join(directory, 'evidence.json')), false);
  assert.match(fs.readFileSync(path.join(directory, 'prompt.md'), 'utf8'), /FAILED case/);
  assert.ok(fs.existsSync(path.join(directory, 'schema.json')));
}));

test('GitHub client wiring selects only failed jobs from the requested attempt', async () => {
  const action = read('.github/actions/analyze-ci-failure/action.yml');
  const script = action.split('        script: |\n')[1].split('    - name:')[0]
    .split('\n').map(line => line.slice(10)).join('\n');
  const files = new Map();
  const calls = [];
  const list = Symbol('list attempt jobs');
  const download = async options => {
    calls.push(options.job_id);
    return {data: options.job_id === 2 ? 'error: compile' : Buffer.from('FAILED test')};
  };
  const github = {rest: {actions: {listJobsForWorkflowRunAttempt: list, downloadJobLogsForWorkflowRun: download}},
    paginate: async (endpoint, options) => {
      assert.equal(endpoint, list);
      assert.deepEqual(options, {owner: 'owner', repo: 'repo', run_id: 123, attempt_number: 2, per_page: 100});
      return [{id: 1, conclusion: 'success'}, {id: 2, name: 'Build', conclusion: 'failure',
        steps: [{name: 'compile', conclusion: 'failure'}]}, {id: 3, name: 'Tests', conclusion: 'failure',
        steps: [{name: 'test', conclusion: 'failure'}]}];
    }};
  const execute = new (Object.getPrototypeOf(async function() {}).constructor)('require', 'github', 'context', 'process', 'Buffer', script);
  await execute(() => ({writeFileSync: (name, body) => files.set(name, body)}), github,
    {repo: {owner: 'owner', repo: 'repo'}}, {env: {RUN_ID: '123', RUN_ATTEMPT: '2', ANALYSIS_DIRECTORY: '/analysis'}}, Buffer);
  assert.deepEqual(calls, [2, 3]);
  const evidence = JSON.parse(files.get('/analysis/evidence.json'));
  assert.equal(evidence[1].log, 'FAILED test');
  assert.deepEqual(evidence[0].steps, ['compile']);
});

test('comment formatter only validates diagnosis content', () => {
  const body = renderComment({cause: '编译失败', evidence: 'unknown type Tile', next_step: '检查类型定义'});
  assert.match(body, /unknown type Tile/);
  assert.doesNotMatch(body, /By /);
  assert.throws(() => renderComment({cause: 'x'.repeat(2001), evidence: 'log', next_step: 'fix'}));
});

test('missing, malformed, blank and oversized responses produce a usable fallback file', () => {
  for (const value of [undefined, 'not json', '{}', 'x'.repeat(20001),
    JSON.stringify({cause: ' ', evidence: 'log', next_step: 'fix'})]) temporaryTest(directory => {
    const answer = path.join(directory, 'response.md');
    if (value !== undefined) fs.writeFileSync(answer, value);
    fs.writeFileSync(path.join(directory, 'result.json'), JSON.stringify({status: 'success', exit_code: 0, requested_model: 'different-model'}));
    const outputs = path.join(directory, 'outputs');
    main('render', {ANALYSIS_DIRECTORY: directory, TRAE_RESULT: directory, GITHUB_OUTPUT: outputs});
    assert.equal(fs.readFileSync(path.join(directory, 'analysis.md'), 'utf8').trim(), fallback);
    assert.match(fs.readFileSync(outputs, 'utf8'), /status=unavailable/);
  });
});

test('attachment gets attribution from the execution record, without a model argument', () => temporaryTest(directory => {
  const answer = path.join(directory, 'response.md');
  fs.writeFileSync(answer, JSON.stringify({cause: '编译失败', evidence: 'unknown type Tile', next_step: '检查类型定义'}));
  const outputs = path.join(directory, 'outputs');
  for (const model of ['provider/new-model', 'another-model', '']) {
    fs.writeFileSync(path.join(directory, 'result.json'), JSON.stringify({status: 'success', exit_code: 0, requested_model: model}));
    main('render', {ANALYSIS_DIRECTORY: directory, TRAE_RESULT: directory, GITHUB_OUTPUT: outputs});
    const body = fs.readFileSync(path.join(directory, 'analysis.md'), 'utf8');
    assert.match(body, /unknown type Tile/);
    assert.equal(body.includes('<sub>By '), !!model);
    if (model) assert.ok(body.includes(`By ${model}`));
    assert.match(fs.readFileSync(outputs, 'utf8'), /status=analyzed/);
  }
}));

test('failed or invalid execution records preserve the normal failure report', () => temporaryTest(directory => {
  fs.writeFileSync(path.join(directory, 'response.md'), JSON.stringify({cause: 'reason', evidence: 'log', next_step: 'fix'}));
  for (const record of [{status: 'failed', exit_code: 1, requested_model: 'model'},
    {status: 'success', exit_code: 124, requested_model: 'model'},
    {status: 'success', exit_code: 0, requested_model: '<html>'}, {}]) {
    fs.writeFileSync(path.join(directory, 'result.json'), JSON.stringify(record));
    main('render', {ANALYSIS_DIRECTORY: directory, TRAE_RESULT: directory});
    assert.equal(fs.readFileSync(path.join(directory, 'analysis.md'), 'utf8').trim(), fallback);
  }
}));

test('all four model entry points share one CATLASS execution policy', () => {
  for (const name of ['reply-atomgit-issue', 'fix-atomgit-issue', 'review-atomgit-pr']) {
    assert.match(read(`.github/workflows/${name}.yml`), /uses: \.\/\.github\/actions\/catlass-ai/);
    assert.doesNotMatch(read(`.github/workflows/${name}.yml`), /model:|expected-version:|cli-path:|host:|sandbox:|bwrap/);
  }
  const action = read('.github/actions/analyze-ci-failure/action.yml');
  assert.match(action, /actions\/catlass-ai@main/);
  assert.doesNotMatch(action, /model: \$|expected-version:|cli-path:|host:|sandbox:|bwrap/);
  const policy = read('.github/actions/catlass-ai/action.yml');
  assert.match(policy, /actions\/setup-traecn@[0-9a-f]{40}/);
  assert.match(policy, /actions\/traecn@[0-9a-f]{40}/);
  assert.match(policy, /model: DeepSeek-V4.1-Flash/);
  assert.match(action, /actions\/github-script@v9/);
  assert.doesNotMatch(action, /PR_NUMBER|ATOMGIT_TOKEN|GITCODE_TOKEN|Test PR/);
});

test('TestPR wires the generic action and artifact, without embedding implementation', () => {
  const workflow = read('.github/workflows/test-atomgit-pr.yml');
  const job = workflow.split('  analyze-failure:\n')[1].split('  report:\n')[0];
  assert.match(job, /uses: ascend-catlass\/actions\/\.github\/actions\/analyze-ci-failure@main/);
  assert.match(job, /uses: actions\/upload-artifact@v4/);
  assert.doesNotMatch(job, /script:|node |python|require\(|ATOMGIT_TOKEN|GITCODE_TOKEN/);
  assert.ok(job.split('\n').length < 35);
  const report = workflow.split('  report:\n')[1];
  assert.match(report, /always\(\)/);
  assert.match(report, /uses: actions\/download-artifact@v4/);
  assert.doesNotMatch(report, /needs\.analyze-failure\.result/);
});

const bashAvailable = spawnSync('bash', ['--version']).status === 0;
test('RDV Bash assembles literal failure analysis with a safe size limit',
  {skip: !bashAvailable}, () => {
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'rdv-comment-'));
    try {
      for (const [result, attachment] of [['failure', '原因：编译失败\n`$(touch injected)`'],
        ['success', 'do not append'], ['cancelled', 'do not append'], ['failure', 'x'.repeat(8193)], ['failure', null]]) {
        const file = path.join(temp, 'analysis.md');
        if (attachment === null) fs.rmSync(file, {force: true}); else fs.writeFileSync(file, attachment);
        const output = path.join(temp, 'outputs');
        fs.writeFileSync(output, '');
        const run = spawnSync('bash', [path.join(root, '.github/actions/rdv-status/rdv-status.sh')], {
          encoding: 'utf8', env: {...process.env, RDV_PHASE: 'finish', RDV_RESULT: result,
            RDV_RESULT_URL: 'https://github.com/run/123', RDV_FAILURE_ANALYSIS_FILE: file,
            RUNNER_TEMP: temp, GITHUB_OUTPUT: output}
        });
        assert.equal(run.status, 0, run.stderr);
        const bodyFile = fs.readFileSync(output, 'utf8').trim().split('=')[1];
        const expected = (result === 'success' ? '✅ RDV Succeeded' : '❌ RDV Failed') + ': https://github.com/run/123'
          + (result === 'failure' && attachment && attachment.length <= 8192 ? '\n\n' + attachment : '');
        assert.equal(fs.readFileSync(bodyFile, 'utf8'), expected);
        assert.ok(!fs.existsSync(path.join(root, 'injected')));
      }
    } finally {
      assert.equal(path.dirname(path.resolve(temp)), path.resolve(os.tmpdir()));
      fs.rmSync(temp, {recursive: true, force: true});
    }
  });
