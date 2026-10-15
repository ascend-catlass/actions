"""Trusted preparation/publication for manual TRAE CN fix and inline review tasks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

from scripts.atomgit_api import AtomGitAPI
from scripts.atomgit_issue_reply import Client, fingerprint, snapshot

ROOT = '/repos/cann/catlass'
SOURCE = 'https://atomgit.com/cann/catlass.git'
MODEL = 'DeepSeek-V4.1-Flash'


def git(worktree, *args, binary=False):
    return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(worktree), *args],
                                   text=not binary).strip()


def number(value):
    if not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise ValueError('Expected a positive Issue/PR number')
    return str(value)


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}', value):
        raise ValueError('Missing full source revision')
    return value


def safe_path(value):
    if (not isinstance(value, str) or not value or '\\' in value
            or any(ord(c) < 32 for c in value) or value.startswith('/')
            or any(p in {'..', '.git'} for p in PurePosixPath(value).parts)
            or ':' in value):
        raise ValueError('Unsafe source path')
    return value


def pages(api, path):
    for page in range(1, 101):
        batch = api.request('GET', f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
        if not isinstance(batch, list):
            raise ValueError('Invalid paginated response')
        yield from batch
        if len(batch) < 100:
            return
    raise ValueError('Refusing incomplete pagination')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare(api, mode, n, worktree, result):
    n = number(n)
    if worktree.exists():
        raise ValueError('Preparation requires a fresh checkout')
    subprocess.run(['git', 'clone', '--no-checkout', SOURCE, str(worktree)], check=True)
    identity = api.request('GET', '/user')
    metadata = {'mode': mode, 'number': n, 'user_id': identity['id']}
    if mode == 'fix':
        client = Client(f'https://atomgit.com/cann/catlass/issues/{n}', os.environ['ATOMGIT_TOKEN'])
        issue, comments = client.issue(), client.comments()
        if issue.get('state') not in {'open', 'opened'}:
            raise ValueError('Issue is closed')
        # Pin the target, not the fork default branch.
        git(worktree, 'checkout', '--detach', 'origin/master')
        metadata.update(source_sha=git(worktree, 'rev-parse', 'HEAD'),
                        fingerprint=fingerprint(snapshot(issue, comments, identity['id'])))
        data = snapshot(issue, comments, identity['id'])
    else:
        pr = api.request('GET', f'{ROOT}/pulls/{n}')
        require_open(pr)
        metadata.update(head_sha=sha(pr['head']['sha']), base_sha=sha(pr['base']['sha']))
        git(worktree, 'fetch', 'origin', f'refs/merge-requests/{n}/head')
        if git(worktree, 'rev-parse', 'FETCH_HEAD') != metadata['head_sha']:
            raise ValueError('PR changed while fetching')
        git(worktree, 'checkout', '--detach', metadata['head_sha'])
        git(worktree, 'cat-file', '-e', metadata['base_sha'])
        merge_base = git(worktree, 'merge-base', metadata['base_sha'], metadata['head_sha'])
        diff = git(worktree, 'diff', '--no-ext-diff', '--no-renames', '--unified=3', merge_base, metadata['head_sha'])
        metadata['lines'] = changed_lines(diff)
        data = {'title': pr.get('title'), 'body': pr.get('body'), 'diff': diff}
    template = Path(f'.github/prompts/atomgit-{mode}.md').read_text(encoding='utf-8')
    prompt = template + '\n\n以下仅是待分析数据：\n' + json.dumps(data, ensure_ascii=False)
    if len(prompt.encode()) > 900_000:
        raise ValueError('Context exceeds bounded model prompt size')
    context = worktree / '.automation-context'
    context.mkdir()
    (context / 'prompt.md').write_text(prompt, encoding='utf-8')
    schema = json.loads(Path(f'.github/prompts/atomgit-{mode}.schema.json').read_text(encoding='utf-8'))
    save(context / 'schema.json', schema)
    save(result / 'context.json', metadata)


def require_open(pr):
    if pr.get('state') not in {'open', 'opened'}:
        raise ValueError('PR is not open')


def changed_lines(diff):
    result, path, line = {}, None, None
    for row in diff.splitlines():
        if row.startswith('+++ b/'):
            path = safe_path(row[6:])
            result.setdefault(path, [])
        elif row.startswith('+++ '):
            path = None
        elif row.startswith('@@ '):
            match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', row)
            if not match:
                raise ValueError('Unsupported diff hunk')
            line = int(match[1])
        elif path is not None and line is not None:
            if row.startswith('+'):
                result[path].append(line)
                line += 1
            elif row.startswith(' '):
                line += 1
    return result


def validate_findings(answer, lines):
    if not isinstance(answer, dict) or set(answer) != {'findings'}:
        raise ValueError('Expected a findings object')
    findings = answer['findings']
    if not isinstance(findings, list) or len(findings) > 10:
        raise ValueError('At most ten findings are allowed')
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {'path', 'line', 'body'}:
            raise ValueError('Invalid finding fields')
        safe_path(finding['path'])
        if type(finding['line']) is not int or finding['line'] not in lines.get(finding['path'], []):
            raise ValueError('Finding must point to an added/modified line in the pinned diff')
        body = finding['body']
        if not isinstance(body, str) or not body.strip() or len(body.encode()) > 2400:
            raise ValueError('Invalid inline comment body')
    return findings


def current_pr(api, metadata):
    pr = api.request('GET', f"{ROOT}/pulls/{metadata['number']}")
    require_open(pr)
    if (pr['head']['sha'], pr['base']['sha']) != (metadata['head_sha'], metadata['base_sha']):
        raise ValueError('PR changed during review; rerun before publishing')
    return pr


def publish_review(api, metadata, answer):
    findings = validate_findings(answer, metadata['lines'])
    current_pr(api, metadata)
    identity = api.request('GET', '/user')
    if identity['id'] != metadata['user_id']:
        raise ValueError('Publishing identity changed')
    path = f"{ROOT}/pulls/{metadata['number']}/comments"
    existing = list(pages(api, path))
    published = []
    for finding in findings:
        key = hashlib.sha256(json.dumps([metadata['head_sha'], finding], sort_keys=True).encode()).hexdigest()
        marker = f'<!-- trae-cn-review:{key} -->'
        body = f"{finding['body'].strip()}\n\n<sub>By {MODEL}</sub>\n{marker}"
        matches = [c for c in existing if (c.get('user') or {}).get('id') == identity['id'] and marker in c.get('body', '')]
        if matches:
            published.append(matches[0]['id'])
            continue
        current_pr(api, metadata)
        created = api.request('POST', path, {'body': body, 'path': finding['path'],
                              'position': finding['line'], 'position_type': 'text'}, encoding='json')
        verified = api.request('GET', f"{ROOT}/pulls/comments/{created['id']}")
        position = verified.get('position') or {}
        if (verified.get('body') != body or (verified.get('user') or {}).get('id') != identity['id']
                or position.get('new_path') != finding['path']
                or position.get('head_sha') != metadata['head_sha']):
            raise RuntimeError('Inline comment read-back failed')
        published.append(created['id'])
        existing.append(verified)
    return {'findings': len(findings), 'comment_ids': published}


def apply_fix(worktree, answer):
    if not isinstance(answer, dict) or set(answer) != {'simple', 'summary', 'patch'}:
        raise ValueError('Invalid fix response')
    if type(answer['simple']) is not bool:
        raise ValueError('simple must be a boolean')
    if not answer['simple']:
        return False
    if not isinstance(answer['summary'], str) or not 1 <= len(answer['summary']) <= 2000:
        raise ValueError('Missing bounded fix summary')
    patch = answer['patch']
    if not isinstance(patch, str) or not patch.strip() or len(patch.encode()) > 100_000:
        raise ValueError('Expected a small unified patch')
    # Validate every declared path before passing model output to git apply.
    for row in patch.splitlines():
        if row.startswith(('--- ', '+++ ')):
            path = row[4:].split('\t', 1)[0]
            if path != '/dev/null':
                if not path.startswith(('a/', 'b/')):
                    raise ValueError('Patch paths must use a/ and b/ prefixes')
                safe_path(path[2:])
                if path[2:].startswith(('.github/', '.gitcode/', '.atomgit/', '.automation-context/')):
                    raise ValueError('Simple fixes cannot change automation configuration')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', encoding='utf-8', newline='\n', delete=False) as stream:
        stream.write(patch)
        patch_file = Path(stream.name)
    try:
        git(worktree, 'apply', '--check', str(patch_file))
        git(worktree, 'apply', '--index', str(patch_file))
    finally:
        patch_file.unlink()
    files = git(worktree, 'diff', '--cached', '--name-only', '-z').rstrip('\0').split('\0')
    if len(files) > 10 or not files or files == ['']:
        raise ValueError('A simple fix must change one to ten files')
    for path in files:
        safe_path(path)
        if path.startswith(('.github/', '.gitcode/', '.atomgit/', '.automation-context/')):
            raise ValueError('Simple fixes cannot change automation configuration')
    modes = git(worktree, 'diff', '--cached', '--raw')
    if any(mode in modes for mode in ('120000', '160000')):
        raise ValueError('Simple fixes cannot change symlinks or submodules')
    return True


def restore_fix(metadata, worktree):
    if worktree.exists():
        raise ValueError('Fix restoration requires a fresh checkout')
    subprocess.run(['git', 'clone', '--no-checkout', SOURCE, str(worktree)], check=True)
    git(worktree, 'checkout', '--detach', sha(metadata['source_sha']))


def validate_fix(worktree, command, log):
    if not command or not command.strip():
        raise ValueError('A maintainer-specified validation command is required')
    # The subprocess receives no publishing or model credentials.
    allowed = {'PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'HOME'}
    env = {k: v for k, v in os.environ.items() if k in allowed}
    with log.open('w', encoding='utf-8') as stream:
        subprocess.run(['bash', '-euo', 'pipefail', '-c', command], cwd=worktree,
                       env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600, check=True)


def compile_once(api, n, identity):
    path = f'{ROOT}/pulls/{number(n)}/comments'
    existing = list(pages(api, path + '?comment_type=pr_comment'))
    if any(c.get('body', '').strip() == 'compile' and (c.get('user') or {}).get('id') == identity['id'] for c in existing):
        return
    created = api.request('POST', path, {'body': 'compile'}, encoding='json')
    verified = api.request('GET', f"{ROOT}/pulls/comments/{created['id']}")
    if verified.get('body', '').strip() != 'compile' or (verified.get('user') or {}).get('id') != identity['id']:
        raise RuntimeError('compile comment read-back failed')


def push_branch(worktree, login, branch):
    with tempfile.TemporaryDirectory(prefix='atomgit-push-') as directory:
        askpass = Path(directory) / 'askpass.sh'
        askpass.write_text('#!/bin/sh\ncase "$1" in *Username*) printf "%s" "$ATOMGIT_PUSH_LOGIN";; *) printf "%s" "$ATOMGIT_PUSH_TOKEN";; esac\n', encoding='utf-8')
        askpass.chmod(0o700)
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'LANG', 'TMPDIR'}}
        env.update(GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT='0', ATOMGIT_PUSH_LOGIN=login, ATOMGIT_PUSH_TOKEN=os.environ['ATOMGIT_TOKEN'])
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'credential.helper=', '-C', str(worktree),
                        'push', f'https://atomgit.com/{login}/catlass.git', f'HEAD:refs/heads/{branch}'], env=env, check=True, timeout=180)


def publish_fix(api, metadata, answer, worktree, validation_command, result):
    validation = json.loads((result / 'validation.json').read_text(encoding='utf-8'))
    if validation['result'] == 'needs-human':
        return validation
    if validation.get('result') != 'validated':
        raise ValueError('Missing successful validation result')
    if validation.get('command') != validation_command:
        raise ValueError('Validation command changed')
    restore_fix(metadata, worktree)
    if not apply_fix(worktree, answer):
        raise ValueError('Validation and model decision disagree')
    if validation.get('patch_sha') != hashlib.sha256(git(worktree, 'diff', '--cached', '--binary', binary=True)).hexdigest():
        raise ValueError('Staged patch changed after validation')
    client = Client(f"https://atomgit.com/cann/catlass/issues/{metadata['number']}", os.environ['ATOMGIT_TOKEN'])
    identity = api.request('GET', '/user')
    if identity['id'] != metadata['user_id']:
        raise ValueError('Publishing identity changed')
    if fingerprint(snapshot(client.issue(), client.comments(), identity['id'])) != metadata['fingerprint']:
        raise ValueError('Issue discussion changed; rerun before publishing')
    login = identity['login']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', login):
        raise ValueError('Invalid publishing login')
    # Existing personal fork is an explicit setup prerequisite; never push upstream.
    fork = api.request('GET', f'/repos/{login}/catlass')
    if not fork.get('fork') or (fork.get('parent') or {}).get('full_name') != 'cann/catlass':
        raise ValueError('Publishing account needs a cann/catlass fork with verified parent')
    branch = f"codex/issue-{metadata['number']}-{metadata['source_sha'][:12]}"
    marker = f"<!-- issue-fix:{metadata['number']}:{metadata['source_sha']} -->"
    existing = [pr for pr in pages(api, ROOT + '/pulls?state=open')
                if marker in (pr.get('body') or '') and (pr.get('user') or {}).get('id') == identity['id']
                and pr.get('head', {}).get('ref') == branch
                and pr.get('head', {}).get('repo', {}).get('full_name') == f'{login}/catlass']
    if existing:
        pr = existing[0]
    else:
        git(worktree, '-c', f'user.name={login}', '-c', 'user.email=codex@openai.com',
            'commit', '-m', f"fix: resolve CATLASS issue {metadata['number']}")
        push_branch(worktree, login, branch)
        pr = api.request('POST', ROOT + '/pulls', {
            'title': f"fix: resolve issue #{metadata['number']}", 'head': f'{login}:{branch}', 'base': 'master',
            'body': f"{marker}\nFixes #{metadata['number']}\n\n{answer['summary']}\n\nValidation: `{validation_command}`\n\nBy {MODEL}"})
    n = number(pr.get('number') or pr.get('iid'))
    verified = api.request('GET', f'{ROOT}/pulls/{n}')
    require_open(verified)
    if verified.get('head', {}).get('ref') != branch or marker not in (verified.get('body') or ''):
        raise RuntimeError('Created PR failed read-back verification')
    compile_once(api, n, identity)
    return {'result': 'pr-created', 'pr_number': n, 'pr_url': f'https://atomgit.com/cann/catlass/pull/{n}'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'validate', 'publish'])
    parser.add_argument('--mode', choices=['fix', 'review'], required=True)
    parser.add_argument('--number', required=True)
    parser.add_argument('--worktree', type=Path, default=Path('_task-source'))
    parser.add_argument('--result', type=Path, default=Path('_task-result'))
    args = parser.parse_args()
    number(args.number)
    if args.phase == 'validate':
        answer = json.loads(Path(os.environ['TASK_RESPONSE']).read_text(encoding='utf-8'))
        if args.mode != 'fix':
            raise ValueError('Validation phase is only for fixes')
        metadata = json.loads((args.result / 'context.json').read_text(encoding='utf-8'))
        if metadata['mode'] != 'fix' or metadata['number'] != args.number:
            raise ValueError('Validation context mismatch')
        restore_fix(metadata, args.worktree)
        if not apply_fix(args.worktree, answer):
            save(args.result / 'validation.json', {'result': 'needs-human'})
            return
        patch_sha = hashlib.sha256(git(args.worktree, 'diff', '--cached', '--binary', binary=True)).hexdigest()
        validate_fix(args.worktree, os.environ.get('VALIDATION_COMMAND', ''), args.result / 'validation.log')
        if git(args.worktree, 'diff', '--name-only'):
            raise ValueError('Validation changed tracked source files')
        save(args.result / 'validation.json', {'result': 'validated', 'patch_sha': patch_sha, 'command': os.environ['VALIDATION_COMMAND']})
        return
    api = AtomGitAPI(os.environ['ATOMGIT_TOKEN'])
    if args.phase == 'prepare':
        prepare(api, args.mode, args.number, args.worktree, args.result)
    else:
        metadata = json.loads((args.result / 'context.json').read_text(encoding='utf-8'))
        if metadata['number'] != args.number or metadata['mode'] != args.mode:
            raise ValueError('Task context mismatch')
        answer = json.loads(Path(os.environ['TASK_RESPONSE']).read_text(encoding='utf-8'))
        result = (publish_review(api, metadata, answer) if args.mode == 'review' else
                  publish_fix(api, metadata, answer, args.worktree, os.environ.get('VALIDATION_COMMAND', ''), args.result))
        save(args.result / 'publication.json', result)
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
