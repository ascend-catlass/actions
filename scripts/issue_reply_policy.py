"""CATLASS reply eligibility, prose policy and legacy-comment migration."""
import argparse
import json
from pathlib import Path
import os
import re

from shared_actions._lib import operations
from scripts.atomgit_api import AtomGitAPI, resolve_token
from scripts.atomgit_issue_reply import MARKER, LEGACY_MARKER, check_author_roles


def check_publication(api, metadata, answer, roles):
    if not answer.strip() or len(answer.encode()) > 2400:
        raise ValueError("Reply must be nonempty and at most 2400 UTF-8 bytes")
    if any(marker in answer for marker in (MARKER, LEGACY_MARKER, operations.MARKER)):
        raise ValueError("Model reply must not contain an automation marker")
    if re.search(r"(?i)trae|自动分析|运行记录|(?m:^By\s)", answer):
        raise ValueError("Reply must contain natural discussion text without tool branding or signature")
    repo, number = operations.issue_url(metadata['issue_url'])
    root = f'/repos/{repo}'
    user = api.request('GET', '/user')['id']
    if user != metadata['user_id']:
        raise ValueError('Publishing identity changed')
    issue = api.request('GET', f'{root}/issues/{number}')
    comments = operations.pages(api, f'{root}/issues/{number}/comments')
    check_author_roles(issue, metadata['issue_url'], roles)
    if operations.digest(operations.snapshot(issue, comments, user)) != metadata['fingerprint']:
        raise ValueError('Issue discussion changed; analyze again')
    # Preserve the project's existing single reply when moving to the shared marker.
    legacy = [c for c in comments if (c.get('user') or {}).get('id') == user
              and any(m in (c.get('body') or '') for m in (MARKER, LEGACY_MARKER))]
    shared = [c for c in comments if operations.owned(c, user)]
    if len(legacy) + len(shared) > 1:
        raise ValueError('Multiple owned replies; resolve duplicates before publishing')
    if legacy:
        old = legacy[0]
        body = old['body'].replace(MARKER, operations.MARKER).replace(LEGACY_MARKER, operations.MARKER)
        path = f"{root}/issues/comments/{old['id']}"
        api.request('PATCH', path, {'body': body})
        verified = api.request('GET', path)
        if verified.get('body') != body or (verified.get('user') or {}).get('id') != user:
            raise ValueError('Legacy reply migration failed verification')
        updated = [dict(c, body=body) if c['id'] == old['id'] else c for c in comments]
        metadata['fingerprint'] = operations.digest(operations.snapshot(issue, updated, user))
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context-file', type=Path, required=True)
    parser.add_argument('--body-file', type=Path, required=True)
    parser.add_argument('--roles-file', type=Path)
    args = parser.parse_args()
    metadata = json.loads(args.context_file.read_text(encoding='utf-8'))
    roles = json.loads(args.roles_file.read_text(encoding='utf-8')) if args.roles_file else None
    result = check_publication(AtomGitAPI(resolve_token()), metadata,
                               args.body_file.read_text(encoding='utf-8'), roles)
    args.context_file.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
