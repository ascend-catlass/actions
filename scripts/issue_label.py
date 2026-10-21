"""CATLASS policy for choosing one existing Issue-kind label."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from scripts.atomgit_api import AtomGitAPI, resolve_token
from shared_actions._lib.traecn_result import load_result

ROOT = '/repos/cann/catlass'
KINDS = {'documentation', 'feature', 'bug-report', 'wontfix', 'question', 'enhancement',
         'bug', 'kind/feature', 'requirement', 'tech-debt', 'invalid', 'duplicate', 'RFC'}


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]*', value):
        raise ValueError('Invalid Issue number')
    return value


def names(labels):
    if not isinstance(labels, list):
        raise ValueError('Invalid label list')
    result = set()
    for label in labels:
        name = label if isinstance(label, str) else label.get('name', label.get('title')) if isinstance(label, dict) else None
        if not isinstance(name, str) or not name:
            raise ValueError('Invalid label name')
        result.add(name)
    return result


def issue(api, issue_number):
    value = api.request('GET', f'{ROOT}/issues/{number(issue_number)}')
    if not isinstance(value, dict) or not isinstance(value.get('state'), str) or not isinstance(value.get('title'), str):
        raise ValueError('Invalid Issue response')
    names(value.get('labels'))
    return value


def available(api):
    result = {}
    for page in range(1, 101):
        labels = api.request('GET', f'{ROOT}/labels?per_page=100&page={page}')
        names(labels)
        for item in labels:
            name = item if isinstance(item, str) else item.get('name', item.get('title'))
            if name in KINDS:
                result[name] = item.get('description') or '' if isinstance(item, dict) else ''
        if len(labels) < 100:
            return result
    raise ValueError('Label catalogue exceeds pagination limit')


def snapshot(value):
    return {'title': value['title'], 'body': value.get('body') or '',
            'labels': sorted(names(value['labels'])), 'state': value['state']}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def eligibility(value):
    if value['state'] not in {'open', 'opened'}:
        return 'issue_not_open'
    if value.get('confidential') is True or value.get('visibility_reason') in {'private', 'confidential'}:
        return 'confidential_issue'
    if names(value['labels']) & KINDS:
        return 'already_classified'
    return ''


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare(api, issue_number, directory):
    value = issue(api, issue_number)
    reason = eligibility(value)
    if reason:
        return reason
    labels = available(api)
    if not labels:
        raise ValueError('No existing Issue-kind labels are available')
    context = {'number': issue_number, 'fingerprint': digest(snapshot(value)), 'labels': labels}
    save(directory / 'context.json', context)
    save(directory / 'issue.json', snapshot(value))
    save(directory / 'labels.json', labels)
    save(directory / 'schema.json', {'type': 'object', 'additionalProperties': False,
         'required': ['label', 'reason'], 'properties': {
             'label': {'type': 'string', 'enum': sorted(labels)},
             'reason': {'type': 'string', 'minLength': 1, 'maxLength': 1000}}})
    template = Path('.github/prompts/atomgit-issue-label.md').read_text(encoding='utf-8')
    (directory / 'prompt.md').write_text(template + '\n\nUntrusted Issue data:\n'
        + json.dumps(snapshot(value), ensure_ascii=False) + '\n\nExisting candidate labels:\n'
        + json.dumps(labels, ensure_ascii=False), encoding='utf-8')
    return 'ready'


def publish(api, context, stage):
    answer = stage.json()
    if not isinstance(answer, dict) or set(answer) != {'label', 'reason'}:
        raise ValueError('Expected exactly one label and a reason')
    label, reason = answer['label'], answer['reason']
    if not isinstance(label, str) or label not in context['labels'] or label not in KINDS:
        raise ValueError('Label is outside the prepared candidates')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('Invalid classification reason')
    value = issue(api, context['number'])
    skip = eligibility(value)
    if skip:
        return {'result': skip}
    if digest(snapshot(value)) != context['fingerprint']:
        raise ValueError('Issue changed during analysis; rerun classification')
    if label not in available(api):
        raise ValueError('Selected label no longer exists')
    api.request('POST', f"{ROOT}/issues/{context['number']}/labels", [label], encoding='json')
    verified = issue(api, context['number'])
    if not (names(value['labels']) | {label}) <= names(verified['labels']):
        raise ValueError('Published label failed read-back verification')
    return {'result': 'labeled', 'label': label, 'reason': reason, 'model': stage.model}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'publish'])
    args = parser.parse_args()
    directory = Path(os.environ['RESULT_DIRECTORY'])
    api = AtomGitAPI(resolve_token())
    if args.operation == 'prepare':
        status = prepare(api, os.environ['ISSUE_NUMBER'], directory)
        result = {'result': status}
    else:
        context = json.loads((directory / 'context.json').read_text(encoding='utf-8'))
        result = publish(api, context, load_result(os.environ['STAGE_RESULT']))
        status = result['result']
    save(directory / 'published.json', result)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write(f"analyze={'true' if status == 'ready' else 'false'}\nresult={status}\n")
    print(f'Issue classification: {status}')


if __name__ == '__main__':
    main()
