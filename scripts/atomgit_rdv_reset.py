"""Remove stale RDV labels from a CATLASS pull request after it is updated.

RDV-SUCC / RDV-FAIL / RDV-RUNNING describe the result of one RDV run. Once
the PR is updated that result no longer applies, so the labels are removed
and the PR has to be tested again.

DELETE may answer 204 or an empty body, so every removal is verified with a
follow-up GET rather than trusting the write response.
"""
import os
import sys

from atomgit_api import AtomGitAPI, resolve_token

PROJECT = '/repos/cann/catlass'
RDV_LABELS = ('RDV-SUCC', 'RDV-FAIL', 'RDV-RUNNING')


def label_names(pr):
    """Read label names from a PR response, accepting both shapes."""
    if not isinstance(pr, dict) or not isinstance(pr.get('labels'), list):
        raise ValueError('Invalid AtomGit PR response')
    out = []
    for label in pr['labels']:
        name = label if isinstance(label, str) else (
            label.get('title') or label.get('name')) if isinstance(label, dict) else None
        if isinstance(name, str) and name:
            out.append(name)
    return out


def validate_number(value):
    if (not isinstance(value, str) or not value.isascii()
            or not value.isdecimal() or int(value) <= 0):
        raise ValueError('Invalid PR number')
    return int(value)


def remove(api, pr_number):
    """Remove RDV labels. Returns a short status string."""
    number = validate_number(pr_number)
    path = f'{PROJECT}/pulls/{number}'

    pr = api.request('GET', path)
    if not isinstance(pr, dict) or not isinstance(pr.get('state'), str):
        raise ValueError('Invalid AtomGit PR response')
    if pr['state'] not in {'opened', 'open'}:
        return 'pr_not_open'

    present = [name for name in label_names(pr) if name in RDV_LABELS]
    if not present:
        return 'no_rdv_label'

    for name in present:
        api.request('DELETE', f'{path}/labels/{name}')

    # Verify: a failed delete must not look like success.
    remaining = [name for name in label_names(api.request('GET', path))
                 if name in RDV_LABELS]
    if remaining:
        raise RuntimeError('RDV labels still present: ' + ', '.join(remaining))
    return 'removed:' + ','.join(present)


def main():
    status = remove(AtomGitAPI(resolve_token()), os.environ.get('PR_NUMBER', ''))
    print(status)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write(f'result={status}\n')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        # Avoid dumping request details, which can contain credentials.
        print(f'STOP: {type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
