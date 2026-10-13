# CANN weekly host 流水线

每天北京时间 02:00（UTC `0 18 * * *`）扫描官方 master 镜像，也支持手动运行。GitHub 的定时任务可能排队延迟。

一个解析任务锁定最新的数字构建目录，提取 Toolkit 包名中的 weekly 版本和日期，并检查该批软件包是否齐全。两个安装任务共享同一组输出，避免运行期间镜像更新导致版本不同。

两个 host runner 暂用标签 `[self-hosted, Linux, bz, X64]` 和 `[self-hosted, Linux, bz, ARM64]`，后续在 workflow matrix 集中替换。CPU 用 `uname -m` 检测并与调度标签交叉核对。NPU 完全按用户指定命令判断，不使用 npu-smi：

```bash
lspci -n -D | grep -o '19e5:d[0-9a-f]\{3\}' | head -n1 | cut -d: -f2
```

| PCI ID | ops 包 |
| --- | --- |
| d802 | 910b |
| d803 | A3 |
| d806 | 950 |

该命令取第一张匹配卡，前提是每台执行机安装同系列 NPU。未知 ID 直接失败。

安装仅由 `scripts/install-cann-weekly.sh` 完成：下载 Toolkit 和匹配的 ops，执行安装包 `--check`，依次执行 `--install --quiet --install-for-all --install-path=/opt/cann_weekly/YYYYMMDD`。直接安装到最终日期路径，不搬迁，不改驱动、固件或用户 shell。

Actions 并发组防止本流水线重叠运行。只有全部包安装成功、目标环境脚本能加载、目标 bisheng 能执行且 OPP 目录存在，才写一个可见的 `installed-version.txt`。以后扫描同构建直接跳过。同日期不同已完成构建报冲突。失败保留目录，下次用 `--force` 重新安装两个包；`/opt/cann_weekly` 应专用于此流水线，不与其他安装程序共用日期目录。这属于安装和编译器检查，不等同于算子上板测试。

历史版本保留在 `/opt/cann_weekly/YYYYMMDD`，下载包保留在可见的 `/opt/cann_weekly/packages/`，不自动删除。没有额外隐藏状态文件、阶段标记或锁文件。日志上传 Actions artifact，保留 30 天。两台独立安装，一台失败不取消另一台。root 或免密 sudo、bash、curl、pciutils 和 CANN 常规依赖需已具备；不依赖 Python 编排脚本或 Codex 远程连接。

安装成功后更新 `/opt/cann_weekly/latest` 软链接，指向该日期目录；扫描到同构建已经成功安装时也刷新该链接。安装失败时不更新链接。

保留两台 host 现有的 `/opt` 软链接，不修改存储布局。安装参数与 latest 路径始终使用 `/opt/cann_weekly`；验证环境时比较解析后的真实路径，兼容安装器在日志中显示 `/home/opt`。

本地检查 workflow YAML、全部内嵌 shell 和安装脚本语法，并使用真实镜像验证版本解析。真实 host 权限、软件安装器对系统登记信息的影响及与已有 CANN 共存行为，由 Actions 首跑确认。只有进入仓库默认分支后，定时触发才会生效。

参考：[官方 master 镜像](https://ascend.devcloud.huaweicloud.com/artifactory/cann-run-mirror/software/master/)、[用户指定的快速安装页](https://www.hiascend.com/cann/download?versionId=801&ids=d806%2Ch0501%2Ch0601%2Ch0703&currentTab=1)。2026-10-13 查到的构建是 `20261009000323778`，包版本 `9.3.0~weekly.20261009.01`，应安装到 `/opt/cann_weekly/20261009`。
