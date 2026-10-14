"""Post the CATLASS CI-passed review reminder once per pull request."""
import os

from gitcode_api import GitCodeAPI


MESSAGE = (
    '感谢您的贡献！您的 CI 流水线已通过，请及时 @ 相关领域的 committer 进行代码检视。'
    '若本次开发的特性规模较大，建议申报 SIG 议题进行讨论。\n\n'
    '如涉及 Ascend 950 相关特性，由于测试资源较为紧张，请联系 committer 在本 PR 下评论 '
    '`rdvcompile`，触发 Ascend 950 流水线。'
)


def remind(api, pr_number):
    if not isinstance(pr_number, str) or not pr_number.isascii() or not pr_number.isdecimal() or int(pr_number) <= 0:
        raise ValueError('Invalid PR number')
    path = f'/repos/cann/catlass/pulls/{int(pr_number)}'
    pr = api.request('GET', path)
    if not isinstance(pr, dict) or not isinstance(pr.get('labels'), list) or not isinstance(pr.get('state'), str):
        raise ValueError('Invalid GitCode PR response')
    if pr['state'] not in {'opened', 'open'}:
        return 'pr_not_open'
    labels = [label if isinstance(label, str) else label.get('title', label.get('name'))
              for label in pr['labels'] if isinstance(label, (str, dict))]
    if 'ci-pipeline-passed' not in labels:
        return 'label_not_present'
    page = 1
    while True:
        comments = api.request('GET', f'{path}/comments?per_page=100&page={page}&comment_type=pr_comment')
        if not isinstance(comments, list):
            raise ValueError('Invalid GitCode comments response')
        if any(isinstance(comment, dict) and comment.get('body') == MESSAGE for comment in comments):
            return 'already_reminded'
        if len(comments) < 100:
            break
        page += 1
    api.request('POST', f'{path}/comments', {'body': MESSAGE}, encoding='json')
    return 'commented'


def main():
    result = remind(GitCodeAPI(os.environ.get('GITCODE_TOKEN', '')), os.environ.get('PR_NUMBER', ''))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write(f'result={result}\n')
    print(f'CI review reminder: {result}')


if __name__ == '__main__':
    main()
