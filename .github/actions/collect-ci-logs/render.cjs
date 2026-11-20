// Produce the comment attachment, falling back to a usable note; no network operations.
const fs = require('node:fs');

const fallback = '失败日志片段暂不可用，请查看上方流水线日志。';
// AtomGit accepts a bounded comment body; keep the attachment well under it.
const MAX_BYTES = 60000;

function truncate(body) {
  if (Buffer.byteLength(body) <= MAX_BYTES) return body;
  const notice = '\n\n（日志过长，已截断；完整日志见上方链接。）\n';
  const room = MAX_BYTES - Buffer.byteLength(notice);
  let kept = Buffer.from(body, 'utf8').subarray(0, room).toString('utf8');
  // Drop a trailing partial character rather than emitting a broken one.
  kept = kept.replace(/\uFFFD$/, '');
  return kept + notice;
}

function main(env = process.env) {
  let body = fallback;
  let status = 'unavailable';
  try {
    const source = env.EXCERPT_FILE;
    if (!source || !fs.existsSync(source)) throw new Error('No excerpt file');
    const text = fs.readFileSync(source, 'utf8').trim();
    if (!text) throw new Error('Empty excerpt');
    body = truncate(text);
    status = 'collected';
  } catch { /* The original RDV result must remain reportable. */ }
  if (env.RUN_URL) body += `\n\n完整日志：${env.RUN_URL}\n`;
  const target = env.ANALYSIS_FILE || 'analysis.md';
  fs.writeFileSync(target, body);
  if (env.GITHUB_OUTPUT) {
    fs.appendFileSync(env.GITHUB_OUTPUT, `excerpt-file=${target}\n`);
    fs.appendFileSync(env.GITHUB_OUTPUT, `status=${status}\n`);
  }
}

module.exports = {main, truncate, fallback, MAX_BYTES};
if (require.main === module) main();
