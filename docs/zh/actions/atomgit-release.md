# 发布 AtomGit Release 安装包

[中文](../../zh/actions/atomgit-release.md) · [English](../../en/actions/atomgit-release.md)

`atomgit-release`

## 做什么

把已经构建和验证的 wheel 发布包上传到 AtomGit Release。已有同名附件时先比对内容；内容相同则复用，内容冲突则失败。

## 什么时候用

稳定版本发布的 AtomGit 分发步骤；它不负责构建 wheel，也不发布到 PyPI。

## 执行过程

1. 检查 bundle 包含 8 个 wheel、SHA256SUMS 和 release-notes.md。
2. 查询指定 tag 的 Release，必要时创建，再上传缺失附件。
3. 对已存在附件校验 SHA-256，最后回查预期附件是否可见。

## 使用前准备

- Linux runner，Python 3、curl；Token 需要 Release 写入权限。
- bundle 指向 release 工作流准备好的目录，包含 wheels/、SHA256SUMS 和 release-notes.md。稳定 tag 的存在性由上层发布工作流先检查。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/atomgit-release@main
  with:
    token: ${{ secrets.ATOMGIT_TOKEN }}
    tag: ${{ inputs.catlass_tag }}
    version: ${{ needs.preflight.outputs.version }}
    bundle: 'release-bundle'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `token` | 是 | — | 可发布 Release 的 AtomGit Token。 |
| `owner` | 否 | `cann` | AtomGit 仓库所有者。 |
| `repo` | 否 | `catlass` | AtomGit 仓库名称。 |
| `tag` | 是 | — | 准确的 Release tag。 |
| `version` | 是 | — | 准确的包版本。 |
| `bundle` | 是 | — | 已准备好的发布包目录。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

没有定义 Action 输出字段；通过步骤状态、日志或其写入的外部结果判断完成情况。

## 说明与常见问题

- 没有 Action 输出字段；成功与否通过步骤退出状态和运行日志判断。
- 重跑可复用相同内容的远端附件，不会覆盖冲突文件。最终回查验证附件名称可见性，不表示逐个重新下载所有新附件校验。

## 实现与调用方

- [.github/actions/atomgit-release/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/atomgit-release/action.yml)
- [scripts/prepare_atomgit_assets.py](https://github.com/ascend-catlass/actions/blob/main/scripts/prepare_atomgit_assets.py)
- [.github/workflows/release-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/release-dsl-wheel.yml)
