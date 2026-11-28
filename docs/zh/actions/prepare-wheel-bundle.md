# 准备与校验 CATLASS wheel 发布包

[中文](../../zh/actions/prepare-wheel-bundle.md) · [English](../../en/actions/prepare-wheel-bundle.md)

## 功能

校验八个 `ascend-catlass` wheel（Python 3.10～3.13，x86_64 和 aarch64），记录校验和与源码信息，并可额外构建一个稳定版本的 `ascend-catlass-dsl` 兼容 wheel。兼容 wheel 仅包含元数据，精确依赖同版本 `ascend-catlass`。

## 示例

先将两种架构的构建产物下载到 `wheels/`：

```yaml
- uses: ascend-catlass/actions/.github/actions/prepare-wheel-bundle@main
  with:
    version: ${{ needs.preflight.outputs.version }}
    source-sha: ${{ needs.preflight.outputs.source_sha }}
    source-ref: ${{ needs.preflight.outputs.tag }}
    compatibility-package: 'true'
```

## 输入

| 输入 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- |
| `operation` | 否 | `prepare` | `prepare` 构建发布包；`validate` 校验已有发布包；`validate-pypi` 额外核对 PyPI 已有文件 |
| `version` | 是 | — | 源码解析阶段确定的精确版本 |
| `source-sha` | 是 | — | 源码解析阶段确定的 CATLASS 提交 SHA |
| `source-ref` | 是 | — | `master` 或精确稳定 tag |
| `input-dir` | 否 | `wheels` | 下载的架构构建产物目录 |
| `bundle` | 否 | `release-bundle` | 准备阶段的输出目录，或校验阶段的已有发布包目录 |
| `compatibility-package` | 否 | `false` | 是否生成或要求稳定版本的 PyPI 专用兼容 wheel |

## 输出

未定义 Action 输出字段。准备结果包含 `wheels/`、`SHA256SUMS`、`release-manifest.json` 和发布说明。稳定版本额外包含 `compat-wheels/` 与 `compat-SHA256SUMS`。兼容包仅用于 PyPI，不包含在 AtomGit 附件中。

## 校验与重试

准备阶段安装 `requirements-release.txt` 中固定版本的工具，并执行 `twine check`。校验阶段只使用 Python 标准库，不重新构建兼容 wheel。下载的发布包必须与预期包名、版本、源码 ref、提交、wheel 矩阵、元数据和哈希一致。release 发布必须包含兼容包；缺少兼容包的旧产物需要重新构建。

`validate-pypi` 还会检查两个项目对应版本的已发布文件，拒绝历史旧原生包等冲突内容。部分成功后的重试仅接受同名且哈希相同的文件。校验通过后才能进入发布阶段，本 Action 不上传发行包。
