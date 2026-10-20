# 创建昇腾测试容器

[中文](../../zh/actions/create-ascend-container.md) · [English](../../en/actions/create-ascend-container.md)

`create-ascend-container`

## 做什么

为测试准备一个临时昇腾容器。若 runner 本身已经在容器内，就直接沿用当前环境；若在宿主机上，则创建容器并挂载源码及必要驱动文件。

## 什么时候用

PR 测试需要统一镜像环境，同时让同一套测试步骤兼容宿主机 runner 和容器 runner。

## 执行过程

1. 检查 /.dockerenv，判断当前是否已在容器内。
2. 宿主机模式下，若镜像缺失则立即构建轻量镜像，然后挂载源码、weekly CANN、NPUIR 和驱动。镜像构建加锁后再次检查，避免并发重复构建。
3. 返回后续测试应使用的源码路径及容器名称。

## 使用前准备

- Linux 昇腾测试环境；宿主机模式需要 Docker、已安装的 NPU 驱动、weekly CANN 和匹配的 NPUIR 归档。镜像不存在时立即构建。
- worktree 指向已存在的宿主机绝对路径；name 必须唯一。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/create-ascend-container@main
  with:
    name: catlass-test-${{ github.run_id }}-${{ github.run_attempt }}
    worktree: ${{ github.workspace }}/catlass
```

```yaml
- name: Clean up the managed container
  if: ${{ always() && steps.action.outputs.container-name != '' }}
  shell: bash
  env:
    CONTAINER_NAME: ${{ steps.action.outputs.container-name }}
  run: docker rm --force "$CONTAINER_NAME"
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `image-repository` | 否 | `catlass-dsl-lab` | Docker 镜像仓库名。 |
| `image-tag` | 否 | `ubuntu24-py312-rdv-v2` | Docker 镜像标签。 |
| `base-image` | 否 | `ubuntu:24.04` | 缺失镜像构建时使用的 Ubuntu 24.04 基础镜像。 |
| `cann-root` | 否 | `/opt/cann_weekly/latest/ascend-toolkit` | weekly CANN toolkit；解析真实版本目录后只读挂载。 |
| `npuir-root` | 否 | `/opt/AscendNPU-IR/latest/AscendNPU-IR` | 只读挂载的 NPUIR 归档目录。 |
| `name` | 是 | — | 本次测试的唯一容器名称。 |
| `worktree` | 是 | — | 要挂载的已存在源码目录。 |
| `container-worktree` | 否 | `/workspace/catlass` | 新容器内的源码挂载位置。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `container-name` | 本 Action 管理的容器名；已在容器中时为空。 |
| `worktree` | 所选测试环境中应使用的源码路径。 |

## 说明与常见问题

- 宿主机模式使用 --privileged 访问 NPU；驱动、weekly CANN 和 NPUIR 只读挂载，Python 3.12 和 CPU PyTorch 来自轻量镜像。每个测试 shell 都会激活 weekly CANN；容器启动后校验 NPUIR 与源码 gitlink，并验证 acl/TorchNPU 能否导入。
- 生产 PR 工作流使用实测过的 Ubuntu 镜像源，可通过 `base-image` 指定其他可信 Ubuntu 24.04 镜像或 digest。CANN 和 NPUIR 必须先通过各自流水线准备好；构建镜像不会重复编译或安装这两个依赖。
- 使用 `validate-dsl-environment.yml` 可在任一替换主机或两台主机上自动构建缺失镜像并运行完整 DSL 测试。已有镜像直接复用；有意更新镜像依赖时应更换镜像标签。
- Action 不自动删除容器。调用方应在 always() 清理步骤中删除非空 container-name；容器内模式返回空名称，不能删除原 runner。
- RDV 工作流还会删除本次运行的 `.rdv-work/pr-运行编号-attempt` 源码和编译目录。容器删除不会清除宿主机挂载目录；宿主机 runner 需允许免交互 `sudo`，以删除容器生成的 root 文件。清理会校验路径和容器名称，保留其他运行及 NPUIR 缓存。

## 实现与调用方

- [.github/actions/create-ascend-container/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/create-ascend-container/action.yml)
- [.github/actions/create-ascend-container/create-ascend-container.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/create-ascend-container/create-ascend-container.sh)
- [.github/workflows/test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml)
