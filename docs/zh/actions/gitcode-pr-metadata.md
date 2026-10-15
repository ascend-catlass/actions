# 读取并校验 PR 版本信息

[中文](../../zh/actions/gitcode-pr-metadata.md) · [English](../../en/actions/gitcode-pr-metadata.md)

`gitcode-pr-metadata`

## 做什么

查询 PR 的目标分支、来源分支和完整提交 SHA，并确认 PR 仍然开启。后续构建可以按明确的源码版本执行。

## 什么时候用

PR 测试开始前，获取合并和测试所需的分支与提交版本。

## 执行过程

1. 校验 PR 编号为正整数，仓库名称符合 owner/repo 格式。
2. 复用 gitcode-api 查询 PR。
3. 检查开启状态、分支名称和 40 位来源 SHA，再输出元数据。

## 使用前准备

- Linux runner，Python 3、jq、Git 和具有 PR 读取权限的 Token。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/gitcode-pr-metadata@main
  with:
    token: ${{ secrets.GITCODE_TOKEN }}
    pr-number: '123'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `token` | 是 | — | 具有 PR 读取权限的 GitCode Token。 |
| `pr-number` | 是 | — | 项目内的正整数 PR 编号。 |
| `repository` | 否 | `cann/catlass` | GitCode 仓库，格式为 owner/repo。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `base_ref` | PR 目标分支。 |
| `head_ref` | PR 来源分支。 |
| `head_sha` | PR 来源提交的完整 SHA。 |

## 说明与常见问题

- 这个 Action 不下载或合并源码。test-gitcode-pr 工作流随后 fetch PR，并再次确认获取到的 head SHA 与输出一致。
- 关闭的 PR、无效分支名或异常 SHA 会使步骤失败。

## 实现与调用方

- [.github/actions/gitcode-pr-metadata/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/gitcode-pr-metadata/action.yml)
- [.github/workflows/test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml)
