# 安装正式发布的 CANN

[中文](../../zh/actions/install-cann-release.md) · [English](../../en/actions/install-cann-release.md)

`install-cann-release` 用于环境维护，与社区、构建及软件发布流程独立。

## 做什么

`resolve` 从[官方发布镜像](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software/)选定一个版本，并检查双 CPU 架构的 Toolkit、910b/A3/950 ops 是否齐全；缺包时报错，不静默回退旧版本。`install` 在 host 安装相同版本的 Toolkit 和对应 ops 到 `/opt/cann/<version>`。

## 版本规则

按 SemVer 主、次、修订版本的数字比较；同一基础版本下，正式版高于任何预发布版。预发布标识逐段比较，数字按数值比较，数字标识低于文本标识。例如：`9.2.0-beta.2 < 9.2.0-beta.10 < 9.2.0-rc.1 < 9.2.0 < 9.2.1 < 9.10.0`。以镜像中的发布版本为候选，包含 beta/rc，不包含 weekly；更高主版本的 beta 可以高于较低主版本的正式版。目录修改时间和目录显示顺序不参与排序。

## 使用前准备

host 需要 root 或免密 sudo、Python 3、Bash、curl、pciutils，以及 CANN 常规安装依赖和已工作的驱动/固件。CPU 使用 `uname -m`；NPU 使用用户指定的 `lspci -n -D | grep -o '19e5:d[0-9a-f]\{3\}' | head -n1 | cut -d: -f2`：d802=910b、d803=A3、d806=950。取首张卡，host 应使用同系列 NPU；未知 ID 报错，不调用 npu-smi。

## 调用示例

```yaml
- id: release
  uses: ascend-catlass/actions/.github/actions/install-cann-release@main
  with:
    operation: resolve
```

在 host 上另以 `operation: install` 调用，传入协调任务输出的 `version` 和实际 `expected-cpu`。工作流已连接这些步骤，并通过现有 artifact 分发工具给 host，无需 host 从 GitHub 拉取代码。

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `operation` | 是 | — | `resolve` 或 `install`。 |
| `version` | 否 | `""` | install 时必需，使用 resolve 的精确输出。 |
| `expected-cpu` | 否 | `""` | install 时必需，x86_64 或 aarch64。 |

## 输出

| 字段 | 说明 |
| --- | --- |
| `version` | resolve 选中的完整版本号。 |

## 安装与重试

先下载并以 `--check` 校验两个包，再依次 Toolkit、ops 安装。安装目录保留完整版本名，如 `/opt/cann/9.2.0`；现有 `/opt` 软链接受支持。环境脚本、目标编译器和 OPP 目录检查通过后才写一个可见的 `installed-version.txt`。以后同版本跳过安装；未完成目录下次用 `--force` 重试，下载包缓存于 `/opt/cann/packages`。该根目录应专用于此流程；不自动删除历史版本或缓存，不改驱动/固件。这是安装与编译器检查，不是算子上板测试。

`/opt/cann/latest` 指向成功的版本目录，复用时也检查更新；使用同一版本比较规则，只前移、不回退。已有普通文件不会被替换为链接。安装失败不会更新 latest。

## 调度

`install-cann-release.yml` 每周一北京时间 03:00（UTC 周日 19:00）运行，或在 main 手动触发。默认使用两台 `bz` host（X64、ARM64）；手动 `runner_label` 配合 `target_arch` 可选择唯一 host。与 weekly 共用并发组，避免两种安装器同时改写系统登记信息。host 日志保留 30 天，单机失败不取消另一台。PR 或未合并分支不会执行安装。
