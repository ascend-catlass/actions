# 准备测试依赖并选择 NPU

[中文](../../zh/actions/prepare-ci-tests.md) · [English](../../en/actions/prepare-ci-tests.md)

`prepare-ci-tests`

## 做什么

在选定的测试环境安装项目所需的 Python 依赖，并选择一张符合条件、运行进程较少的 NPU 卡。

## 什么时候用

在容器准备完成后、DSL 或非 DSL 测试开始前使用。

## 执行过程

1. 从 requirements.txt 创建临时过滤文件，排除直接声明的 Torch、Torch NPU 和 Lit，再用 pip 安装其余依赖。
2. 在测试环境执行 detect_npu.sh，检查可用卡。
3. 按进程数、卡编号排序选卡，并返回 device-id。

## 使用前准备

- 已存在的 CATLASS worktree，Python/pip、Bash、awk 和可工作的 npu-smi。
- 镜像或环境已经提供匹配的 Torch、Torch NPU；使用宿主机创建的容器时传入 container。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/prepare-ci-tests@main
  with:
    worktree: ${{ steps.container.outputs.worktree }}
    container: ${{ steps.container.outputs.container-name }}
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `worktree` | 是 | — | 测试环境中的源码目录。 |
| `container` | 否 | `""` | 宿主机创建的 Docker 容器名；为空时使用当前环境。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `device-id` | 选中的 NPU 卡编号，传给后续 DEVICE_ID 或 device-id。 |

## 说明与常见问题

- 过滤只影响直接安装请求；pip 仍会解析传递依赖。原 requirements.txt 不改动，DSL dev 阶段仍可能安装 Lit。
- 默认候选条件为剩余内存大于 1024 MB、进程数小于 4；没有候选卡则失败。选择是当时的快照，不是独占预约。
- 选卡脚本来自 flash-attention-npu，来源及许可证保存在 Action 目录。

## 实现与调用方

- [.github/actions/prepare-ci-tests/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/prepare-ci-tests/action.yml)
- [.github/actions/prepare-ci-tests/detect_npu.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/prepare-ci-tests/detect_npu.sh)
- [.github/actions/prepare-ci-tests/SOURCE.md](https://github.com/ascend-catlass/actions/blob/main/.github/actions/prepare-ci-tests/SOURCE.md)
- [.github/workflows/test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml)
