// Produce the comment attachment, falling back to a usable note; no network operations.
const fs = require('node:fs');

const fallback = '失败日志片段暂不可用，请查看上方流水线日志。';
// AtomGit rejects a comment body longer than 65536 characters (measured: 60000
// CJK characters pass, 66000 ASCII fail, so the limit counts characters, not
// bytes). Leave room for the RDV prefix and the log link.
const MAX_CHARS = 60000;

function truncate(body) {
  if (body.length <= MAX_CHARS) return body;
  const notice = '\n\n（日志过长，已截断；完整日志见下方链接。）\n';
  const room = MAX_CHARS - notice.length;
  let kept = body.slice(0, room);
  // Prefer cutting at a line boundary so the excerpt stays readable.
  const lastBreak = kept.lastIndexOf('\n');
  if (lastBreak > room * 0.8) kept = kept.slice(0, lastBreak);
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

module.exports = {main, truncate, fallback, MAX_CHARS};
if (require.main === module) main();
