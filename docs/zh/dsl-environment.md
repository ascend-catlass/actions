# 不依赖 CANN 镜像重建 DSL 环境

[English](../en/dsl-environment.md)

实验方案将操作系统、Python 包与 CANN、NPUIR 分开管理。Docker 内不再克隆或编译
LLVM/NPUIR。先通过 CANN 安装流水线和当前 NPUIR 准备流水线安装依赖，再将确定版本的
目录以只读方式挂载进容器。

生产 PR 测试已接入该轻量环境：镜像不存在时立即构建，并通过镜像锁避免并发重复构建。
手动入口 `validate-dsl-environment.yml` 可验证任一替换主机或同时验证两台，包含完整 DSL 测试。
wheel 发布、Release 和社区流水线保留现有执行约定；历史 NPUIR 20260720 流水线保持不变。

## 实测基线

2026-10-19 在 Ubuntu 24.04 x86_64、Ascend 950PR 构建机上测得：

| 项目 | 结果 |
| --- | --- |
| CATLASS 提交 | `dd8b8b4c0611af965fb57df9818d3b819db67489` |
| NPUIR 提交 | `693abf31f3d88d13d30d9578fcf6513b90c0ee33` |
| CANN | `9.3.0~weekly.20261014.01`，构建号 `20261014093543763` |
| Python / 编译器 | Python 3.12；Ubuntu clang 19.1.1；缓存 NPUIR 使用 clang/lld 19.1.7 构建 |
| PyTorch / TorchNPU | `2.9.0+cpu` / `2.9.0.post9` |
| 宿主机 Python 环境首次准备 | 458 秒，不含源码传输 |
| 宿主机 DSL 开发包构建 | 19 秒，32 个并行任务 |
| 宿主机 IR 测试 | 2725 通过，19 跳过；31.20 秒 |
| 宿主机 Lit 测试 | 191 通过；测试本身 3.11 秒，不含编译 |
| 宿主机 Release wheel 和真机测试 | 304 通过；测试本身 96.26 秒，含 wheel 构建安装共 130 秒 |
| 薄镜像首次构建 | 434 秒，含依赖下载和镜像导出 |
| 薄镜像体积 | 完成导出和解包后，`docker image ls` 显示 3.1 GB |
| 容器 DSL 开发包构建 | 21 秒 |
| 容器 IR / Lit 测试 | 2739 通过、5 跳过 / 191 通过 |
| 容器 Release wheel 和真机测试 | 304 通过；测试本身 115.58 秒，含 wheel 构建安装共 171 秒 |

仅 NPUIR 安装目录就有 4.7 GiB，这部分留在镜像之外。首次准备主要耗时在网络下载；
上述耗时不包含安装 CANN 或构建缺失的 NPUIR 归档。重复构建镜像会复用 Docker 层。
目前只验证了 x86_64，不替代用于发布 wheel 的 manylinux 构建任务。

首次宿主机 IR 测试早于 TorchNPU 安装；完整配置的容器额外执行了 14 项可选测试。
CANN 在宿主机上约占 15 GiB，这部分同样不放进镜像。

## 宿主机虚拟环境

按照主机管理员的软件包策略安装二进制系统依赖。Ubuntu 24.04 的软件包集合为：

```bash
sudo apt-get install --no-install-recommends \
  ca-certificates clang-19 lld-19 git build-essential python3-dev \
  python3-venv zlib1g-dev libxml2-dev
bash scripts/dsl-env/prepare-python.sh /path/to/catlass /path/to/new-venv
```

脚本拒绝覆盖已有环境，并将实际安装版本记录在 `requirements-resolved.txt`。
先安装 CPU 版 PyTorch，再安装 TorchNPU，避免依赖解析下载 CUDA 组件。
构建工具和 CANN Python 依赖来自当前 CATLASS 源码中的依赖清单。

通过环境包装脚本运行仓库原有构建与测试命令：

```bash
SOURCE=/path/to/catlass
VENV=/path/to/new-venv
CANN=/opt/cann_weekly/20261014/cann-9.3.0
NPUIR=/opt/AscendNPU-IR/20261013/AscendNPU-IR
bash scripts/dsl-env/run.sh "$SOURCE" "$VENV" "$CANN" "$NPUIR" -- \
  bash -c 'cd python/tla_dsl && bash build.sh && python -m pytest -q tests -p no:randomly && cmake --build csrc/mlir/build --target check-tla-lit'
```

`run.sh` 在执行前校验 NPUIR 源码 SHA 与 CATLASS gitlink、主机架构及归档构建约定。
如果源码包没有 Git 元数据，应根据可信的源码版本设置
`CATLASS_DSL_EXPECTED_NPUIR_SHA`。脚本还会选择当前虚拟环境的 Lit；缓存归档中的
`llvm-lit` 可能指向仅存在于归档构建容器中的 Python 解释器。

真机验证应选择空闲设备，并设置隔离、可写的 `TMPDIR` 和 `CATLASS_DSL_CACHE_DIR`，
然后通过同一包装脚本执行 `bash tests/run_dsl_test.sh --device ID`。
该仓库入口会构建并测试 Release wheel。
单独执行示例时，应先在同一 Python 环境和缓存中运行 `python -m catlass.bc_compile`
初始化 bitcode。

## 薄容器

```bash
bash scripts/dsl-env/build-image.sh /path/to/catlass catlass-dsl-light:ubuntu24-py312
bash scripts/dsl-env/run-container.sh /path/to/separate-catlass-worktree \
  catlass-dsl-light:ubuntu24-py312 "$CANN" "$NPUIR" -- \
  bash -c 'cd python/tla_dsl && bash build.sh && python -m pytest -q tests -p no:randomly && cmake --build csrc/mlir/build --target check-tla-lit'
```

可通过 `BASE_IMAGE` 选择可信镜像源或固定的 Ubuntu 24.04 digest。
实测使用 `docker.m.daocloud.io/library/ubuntu:24.04`。构建上下文只包含 Dockerfile 和两份
Python 依赖清单，不包含 CANN、NPUIR、仓库历史或完整源码。

运行时将独立 CATLASS 工作目录以读写方式挂载；CANN 和 NPUIR 在原绝对路径只读挂载；
已安装的昇腾驱动路径也只读挂载。实验脚本 `run-container.sh` 沿用 runner 现有的昇腾
特权容器策略，只读挂载 `run.sh`，以 `/opt/dsl-venv` 为 Python 环境调用。
仅用于可信任在该构建机上执行的源码。
容器与宿主机运行相同的仓库构建、IR、Lit 和真机测试命令。
包装脚本通过 `ascend-toolkit/set_env.sh` 解析真实 CANN 安装目录，避免只挂载一组指向
兄弟目录的符号链接而遗漏实际文件。

宿主机与容器实验必须使用独立源码和构建目录，因为 CMake 缓存包含绝对路径。
Linux 检出应使用 LF 换行；Windows 导出的 CRLF shell 和 Lit 测试文件可能在环境验证前
就失败。更新基础镜像或 Python 依赖基线时应更换镜像标签。生产容器会将实际 weekly CANN 版本
与匹配的 NPUIR 归档同时只读挂载，并在每个测试 shell 中激活 weekly CANN。
