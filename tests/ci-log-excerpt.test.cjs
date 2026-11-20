const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const {collect, excerpt, findMarker, redact} = require('../.github/actions/collect-ci-logs/excerpt.cjs');
const render = require('../.github/actions/collect-ci-logs/render.cjs');
const read = name => fs.readFileSync(path.join(root, name), 'utf8').replace(/\r\n/g, '\n');

function temporaryTest(work) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ci-logs-'));
  try { return work(directory); }
  finally {
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    fs.rmSync(directory, {recursive: true, force: true});
  }
}

test('the marker nearest the end of the log wins over echoed command text', () => {
  const lines = [
    '>>> bash tests/run_all_test.sh',      // echoed text mentioning a failure
    'FAILED tests/old_case.py',
    'normal output',
    '##[error]Process completed with exit code 1',
  ];
  assert.equal(findMarker(lines), 3);
});

test('excerpt keeps the requested number of lines around the marker', () => {
  const log = Array.from({length: 1000}, (_, i) => `line ${i + 1}`).join('\n');
  const withMarker = log.split('\n');
  withMarker[700] = '##[error]boom';
  const found = excerpt(withMarker.join('\n'), 200);
  assert.equal(found.marker, 701);
  assert.equal(found.end - found.start + 1, 200);
  assert.ok(found.start <= 701 && found.end >= 701);
  assert.match(found.text, /##\[error\]boom/);
});

test('excerpt clamps at the start and end of short logs', () => {
  const short = ['##[error]first', 'a', 'b'].join('\n');
  const found = excerpt(short, 200);
  assert.equal(found.start, 1);
  assert.equal(found.end, 3);
});

test('collect redacts credentials, strips timestamps and bounds the output', () => {
  const log = 'Authorization: Bearer private-value\n'
    + '2026-11-19T16:12:58.5564956Z ##[error]unknown type Tile\n'
    + 'token=abcdef123456\n';
  const parts = collect([{job: 'Build', steps: ['compile'], log}], 200);
  const text = parts.join('\n');
  assert.match(text, /unknown type Tile/);
  assert.doesNotMatch(text, /private-value/);
  assert.doesNotMatch(text, /abcdef123456/);
  assert.doesNotMatch(text, /2026-11-19T16:12:58/);
  assert.match(text, /Build/);
  assert.match(text, /compile/);
});

test('collect rejects empty evidence and blank logs, and returns nothing without a marker', () => {
  assert.throws(() => collect([], 200), /failed jobs/);
  assert.throws(() => collect([{job: 'x', steps: [], log: '   \n'}], 200), /Missing log evidence/);
  assert.throws(() => collect([{job: 'x', steps: []}], 200), /Missing log evidence/);
  // A healthy log is not an error; it simply yields no excerpt.
  assert.deepEqual(collect([{job: 'x', steps: [], log: 'all good\nstill good'}], 200), []);
});

test('the excerpt step fails loudly when no marker exists', () => temporaryTest(directory => {
  const evidence = path.join(directory, 'evidence.json');
  fs.writeFileSync(evidence, JSON.stringify([{job: 'x', steps: [], log: 'nothing wrong here'}]));
  const outputs = path.join(directory, 'outputs');
  fs.writeFileSync(outputs, '');
  const run = spawnSync(process.execPath,
    [path.join(root, '.github/actions/collect-ci-logs/excerpt.cjs')],
    {encoding: 'utf8', env: {...process.env, EVIDENCE_FILE: evidence,
      EXCERPT_OUT: path.join(directory, 'excerpt.md'), GITHUB_OUTPUT: outputs}});
  assert.notEqual(run.status, 0);
  assert.match(run.stderr, /No failure marker/);
}));

test('the excerpt step writes a bounded excerpt and reports collected', () => temporaryTest(directory => {
  const evidence = path.join(directory, 'evidence.json');
  fs.writeFileSync(evidence, JSON.stringify([
    {job: 'Test PR #1786', steps: ['Prepare test dependencies and device'],
     log: 'noise\n[detect_npu][ERROR] no selectable NPU\n##[error]Process completed with exit code 1'}]));
  const out = path.join(directory, 'excerpt.md');
  const outputs = path.join(directory, 'outputs');
  fs.writeFileSync(outputs, '');
  const run = spawnSync(process.execPath,
    [path.join(root, '.github/actions/collect-ci-logs/excerpt.cjs')],
    {encoding: 'utf8', env: {...process.env, EVIDENCE_FILE: evidence, EXCERPT_OUT: out,
      CONTEXT_LINES: '200', GITHUB_OUTPUT: outputs}});
  assert.equal(run.status, 0, run.stderr);
  const body = fs.readFileSync(out, 'utf8');
  assert.match(body, /no selectable NPU/);
  assert.match(body, /失败步骤：Prepare test dependencies and device/);
  assert.match(fs.readFileSync(outputs, 'utf8'), /status=collected/);
}));

test('render falls back when the excerpt is missing, empty or unreadable', () => temporaryTest(directory => {
  for (const prepare of [() => {}, d => fs.writeFileSync(path.join(d, 'e.md'), ''),
    d => fs.writeFileSync(path.join(d, 'e.md'), '   \n')]) {
    prepare(directory);
    const outputs = path.join(directory, 'outputs');
    fs.writeFileSync(outputs, '');
    render.main({EXCERPT_FILE: path.join(directory, 'e.md'),
      ANALYSIS_FILE: path.join(directory, 'analysis.md'), GITHUB_OUTPUT: outputs});
    const body = fs.readFileSync(path.join(directory, 'analysis.md'), 'utf8');
    assert.match(body, /失败日志片段暂不可用/);
    assert.match(fs.readFileSync(outputs, 'utf8'), /status=unavailable/);
  }
}));

test('render truncates an oversized excerpt instead of dropping it', () => {
  const big = 'x'.repeat(render.MAX_BYTES + 5000);
  const out = render.truncate(big);
  assert.ok(Buffer.byteLength(out) <= render.MAX_BYTES);
  assert.match(out, /已截断/);
});

test('render appends the run link so the full log stays reachable', () => temporaryTest(directory => {
  const source = path.join(directory, 'e.md');
  fs.writeFileSync(source, '## 失败日志片段\n\n```\n##[error]boom\n```\n');
  const outputs = path.join(directory, 'outputs');
  fs.writeFileSync(outputs, '');
  render.main({EXCERPT_FILE: source, ANALYSIS_FILE: path.join(directory, 'analysis.md'),
    RUN_URL: 'https://github.com/run/123/attempts/2', GITHUB_OUTPUT: outputs});
  const body = fs.readFileSync(path.join(directory, 'analysis.md'), 'utf8');
  assert.match(body, /##\[error\]boom/);
  assert.match(body, /https:\/\/github.com\/run\/123\/attempts\/2/);
  assert.match(fs.readFileSync(outputs, 'utf8'), /status=collected/);
}));

test('the collect action wires the GitHub client without PR-specific inputs', () => {
  const action = read('.github/actions/collect-ci-logs/action.yml');
  assert.match(action, /actions\/github-script@v9/);
  assert.match(action, /excerpt\.cjs/);
  assert.match(action, /render\.cjs/);
  assert.doesNotMatch(action, /PR_NUMBER|ATOMGIT_TOKEN|GITCODE_TOKEN|Test PR/);
  assert.doesNotMatch(action, /model:|trae|catlass-ai/i);
});

test('TestPR collects logs and keeps reporting independent of collection', () => {
  const workflow = read('.github/workflows/test-atomgit-pr.yml');
  const job = workflow.split('  collect-logs:\n')[1].split('  report:\n')[0];
  assert.match(job, /uses: ascend-catlass\/actions\/\.github\/actions\/collect-ci-logs@main/);
  assert.match(job, /uses: actions\/upload-artifact@v4/);
  assert.doesNotMatch(job, /script:|node |python|require\(|ATOMGIT_TOKEN|GITCODE_TOKEN|TRAE_CN_PAT/);
  const report = workflow.split('  report:\n')[1];
  assert.match(report, /always\(\)/);
  assert.match(report, /uses: actions\/download-artifact@v4/);
  assert.doesNotMatch(report, /needs\.collect-logs\.result/);
});

test('the removed analysis feature leaves no references behind', () => {
  for (const name of ['README.md', 'README.en.md', 'mkdocs.yml',
    '.github/workflows/docs-build.yml', '.github/workflows/test-atomgit-pr.yml']) {
    assert.doesNotMatch(read(name), /analyze-ci-failure|analyze-failure|rdv-failure-analysis/);
  }
  assert.equal(fs.existsSync(path.join(root, '.github/actions/analyze-ci-failure')), false);
});

const bashAvailable = spawnSync('bash', ['--version']).status === 0;
test('RDV Bash assembles the literal log excerpt with a safe size limit',
  {skip: !bashAvailable}, () => {
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'rdv-comment-'));
    try {
      for (const [result, attachment] of [['failure', '##[error]boom\n`$(touch injected)`'],
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
