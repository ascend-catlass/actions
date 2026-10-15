# 复用本机 AscendNPU-IR 构建归档

[中文](../../zh/actions/npuir-local-archive.md) · [English](../../en/actions/npuir-local-archive.md)

`npuir-local-archive`

## 做什么

在每台构建机上保存和复用完整的 AscendNPU-IR 源码、构建与安装目录。只有提交、CPU 架构、构建约定等条件一致，才把归档交给后续构建。

## 什么时候用

DSL wheel 构建需要重用较重的编译依赖，或需要发布新完成的依赖归档。

## 执行过程

1. lookup：按版本日期查找本机归档并校验清单；缺失时给出临时构建路径。
2. 由上层工作流在 work_path 编译；此 Action 本身不编译。
3. publish：校验完成目录并发布；在本机文件锁下更新 latest，日期只向前推进。

## 使用前准备

- Linux 自托管构建机，Git、GNU 命令行工具和 flock。归档目录需要写权限。
- 默认 /opt/AscendNPU-IR 首次创建时可能需要免密 sudo；publish 需要完成的 source_path。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/npuir-local-archive@main
  with:
    operation: 'lookup'
    source_sha: '693abf31f3d88d13d30d9578fcf6513b90c0ee33'
    target_arch: 'x86_64'
    build_contract: 'clang19-lld19-release-rtti-assert-triton-zstd-off-v1'
    baseline_date: '20261013'
    build_fingerprint: 'clang-19.1.7+lld-19.1.7'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `operation` | 是 | — | lookup 查询或 publish 发布。 |
| `source_sha` | 是 | — | 归档对应的完整 AscendNPU-IR 提交 SHA。 |
| `target_arch` | 是 | — | CPU 架构，例如 x86_64 或 aarch64。 |
| `build_contract` | 是 | — | 构建选项与工具链约定的版本标识。 |
| `baseline_date` | 是 | — | YYYYMMDD 格式的版本日期，不是本次运行日期。 |
| `archive_root` | 否 | `/opt/AscendNPU-IR` | 本机构建归档根目录。 |
| `source_path` | 否 | `""` | 已完成的构建目录；publish 时必须提供。 |
| `source_branch` | 否 | `""` | 记录在归档清单里的来源分支。 |
| `source_ref` | 否 | `""` | 记录在清单里的请求 ref。 |
| `build_fingerprint` | 否 | `""` | 要记录或要求匹配的准确工具链标识。 |
| `legacy_postfix` | 否 | `""` | 允许迁移的旧本机归档日期后缀。 |
| `legacy_build_fingerprint` | 否 | `""` | 重用旧日期归档时要求的工具链标识。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `path` | 选中的日期归档绝对路径；缺失时仅为计划路径。 |
| `work_path` | 同一文件系统上的临时构建路径。 |
| `archive_key` | 由源码、CPU 架构和构建约定组成的归档标识。 |
| `source_sha` | 归档记录的源码提交。 |
| `target_arch` | 归档记录的 CPU 架构。 |
| `build_contract` | 归档记录的构建约定。 |
| `baseline_date` | 归档记录的版本日期。 |
| `build_fingerprint` | 归档记录的工具链标识。 |
| `cache_hit` | 是否找到可用的完整归档。 |
| `legacy_cache_hit` | 本次是否迁移并复用了旧归档。 |

## 说明与常见问题

- 每台机器保存自己的归档；它不是跨机器共享的远端缓存。目录是 `/opt/AscendNPU-IR/<日期>/AscendNPU-IR`。
- 同一日期不能复用为另一个提交、架构或构建约定；条件冲突会失败，不会静默覆盖。失败构建不成为 latest。
- 迁移旧归档需匹配 legacy 参数。归档输出源码提交仍须与 CATLASS 的依赖 gitlink 一致。

## 实现与调用方

- [.github/actions/npuir-local-archive/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/npuir-local-archive/action.yml)
- [.github/actions/npuir-local-archive/manage-archive.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/npuir-local-archive/manage-archive.sh)
- [.github/workflows/build-ascendnpu-ir-20261013.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20261013.yml)
- [.github/workflows/build-ascendnpu-ir-20260720.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20260720.yml)
- [.github/workflows/build-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-dsl-wheel.yml)
