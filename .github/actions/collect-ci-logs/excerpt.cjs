// Extract a bounded log excerpt around the first failure; no network operations.
const fs = require('node:fs');

// Markers that identify where a stage actually broke. Ordered by specificity so
// an explicit "##[error]" wins over a generic "FAILED" inside normal output.
const MARKERS = [
  /##\[error\]/,
  /\[detect_npu\]\[ERROR\]/,
  /^FAILED\s/,
  /^E\s+AssertionError/,
  /Traceback \(most recent call last\)/,
  /^fatal:/,
  /Process completed with exit code [1-9]/,
  /::error::/,
];

function redact(text) {
  return text
    .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '')
    .replace(/^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?/gm, '')
    .replace(/(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)/g, '[REDACTED]')
    .replace(/((?:authorization|private-token)\s*[:=]\s*)(?:Bearer\s+|Basic\s+)?[^\s,;]+/gi, '$1[REDACTED]')
    .replace(/\b((?:access_token|[\w-]*(?:token|password|secret|pat))\s*[=:]\s*)[^\s&"']+/gi, '$1[REDACTED]')
    .replace(/https:\/\/[^/\s:@]+:[^/\s@]+@/g, 'https://[REDACTED]@');
}

// The failure marker nearest the end of the log is the one that stopped the
// stage; earlier matches are usually echoed command text.
function findMarker(lines) {
  for (const pattern of MARKERS) {
    for (let index = lines.length - 1; index >= 0; index -= 1) {
      if (pattern.test(lines[index])) return index;
    }
  }
  return -1;
}

function excerpt(log, contextLines) {
  const lines = log.split('\n');
  const marker = findMarker(lines);
  if (marker < 0) return null;
  const half = Math.max(1, Math.floor(contextLines / 2));
  const start = Math.max(0, marker - half);
  const end = Math.min(lines.length, start + contextLines);
  return {
    start: start + 1,
    end,
    marker: marker + 1,
    text: lines.slice(start, end).join('\n'),
  };
}

function collect(evidence, contextLines) {
  if (!Array.isArray(evidence) || !evidence.length || evidence.length > 4) {
    throw new Error('Expected one to four failed jobs');
  }
  const parts = [];
  for (const {job, steps, log} of evidence) {
    if (typeof log !== 'string' || !log.trim() || !Array.isArray(steps)) {
      throw new Error('Missing log evidence');
    }
    const found = excerpt(log, contextLines);
    if (!found) continue;
    const header = `### ${job}` + (steps.length ? ` — 失败步骤：${steps.join(', ')}` : '');
    const where = `日志第 ${found.start}–${found.end} 行（失败位置 ${found.marker} 行，共 ${contextLines} 行）`;
    parts.push(`${header}\n\n${where}\n\n\`\`\`\n${redact(found.text)}\n\`\`\``);
  }
  return parts;
}

function main(env = process.env) {
  const contextLines = Number.parseInt(env.CONTEXT_LINES || '200', 10);
  if (!Number.isInteger(contextLines) || contextLines < 1 || contextLines > 2000) {
    throw new Error('context-lines must be between 1 and 2000');
  }
  const out = env.EXCERPT_OUT || 'excerpt.md';
  const evidence = JSON.parse(fs.readFileSync(env.EVIDENCE_FILE, 'utf8'));
  const parts = collect(evidence, contextLines);
  if (!parts.length) throw new Error('No failure marker found in the failed job logs');
  fs.writeFileSync(out, ['## 失败日志片段', ...parts].join('\n\n') + '\n');
  if (env.GITHUB_OUTPUT) {
    fs.appendFileSync(env.GITHUB_OUTPUT, `excerpt-file=${out}\n`);
    fs.appendFileSync(env.GITHUB_OUTPUT, 'status=collected\n');
  }
}

module.exports = {collect, excerpt, findMarker, redact, main, MARKERS};
if (require.main === module) main();
