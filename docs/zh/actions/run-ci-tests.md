# 运行 CATLASS 测试阶段

[中文](../../zh/actions/run-ci-tests.md) · [English](../../en/actions/run-ci-tests.md)

`run-ci-tests`

## 做什么

在已准备好的测试环境运行一个明确的测试阶段。DSL 测试按开发构建、IR、Lit 和设备测试拆分；非 DSL 测试按修改路径和头文件依赖选择测试组。

## 什么时候用

工作流已经合并待测 PR、准备好环境并选卡后调用。

## 执行过程

1. 判断在当前容器、指定容器或旧宿主机环境执行。
2. 按 suite 执行 dsl-dev、dsl-ir、dsl-lit、dsl 或 all 阶段。
3. 把命令和结果写入日志；失败以非零退出状态交给上层工作流处理。

## 使用前准备

- 已经合并的 CATLASS worktree，匹配的 CANN/Python/编译工具和 NPU 环境。
- dsl-ir 与 dsl-lit 依赖先前 dsl-dev 构建；选择性非 DSL 测试需提供实际 base-sha、head-sha。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/run-ci-tests@main
  with:
    suite: 'all'
    worktree: ${{ steps.container.outputs.worktree }}
    container: ${{ steps.container.outputs.container-name }}
    device-id: ${{ steps.prepare.outputs.device-id }}
    base-sha: ${{ steps.merge.outputs.base_sha }}
    head-sha: ${{ needs.prepare.outputs.head_sha }}
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `suite` | 是 | — | dsl-dev、dsl-ir、dsl-lit、dsl 或 all。 |
| `worktree` | 是 | — | 合并后的 CATLASS 测试源码目录。 |
| `container` | 否 | `""` | 测试容器名称；为空则使用当前环境或宿主机。 |
| `device-id` | 否 | `0` | 测试使用的 NPU 卡编号。 |
| `base-sha` | 否 | `""` | 选择性非 DSL 测试所需的实际目标提交 SHA。 |
| `head-sha` | 否 | `""` | 选择性非 DSL 测试所需的 PR 来源 SHA。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

没有定义 Action 输出字段；通过步骤状态、日志或其写入的外部结果判断完成情况。

## 说明与常见问题

- suite=all 是选择性非 DSL 测试入口，并不代表每次跑全量。公共构建依赖变化才要求全量 3510 测试；不支持的 910B 专用组不会在 950 上运行。
- 文档或图片 PR 是否跳过 NPU，以及 DSL/非 DSL 如何分流，由上层 PR 工作流决定。
- Action 不提供输出字段。宿主机直跑会激活原有 CANN/Conda 环境；容器使用镜像环境。

## 实现与调用方

- [.github/actions/run-ci-tests/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/action.yml)
- [.github/actions/run-ci-tests/run-ci-tests.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/run-ci-tests.sh)
- [.github/actions/run-ci-tests/run-targeted-tests.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/run-targeted-tests.sh)
- [.github/actions/run-ci-tests/run-dsl-unit-tests.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/run-dsl-unit-tests.sh)
- [.github/actions/run-ci-tests/SOURCE.md](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md)
- [.github/workflows/test-gitcode-pr-cann-9-2-beta-2.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr-cann-9-2-beta-2.yml)
- [.github/workflows/test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml)
