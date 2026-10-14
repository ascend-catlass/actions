# npuir-local-archive

[中文手册](../../../docs/zh/actions/npuir-local-archive.md) · [English guide](../../../docs/en/actions/npuir-local-archive.md)

在每台构建机上保存和复用完整的 AscendNPU-IR 源码、构建与安装目录。只有提交、CPU 架构、构建约定等条件一致，才把归档交给后续构建。

Stores and reuses complete AscendNPU-IR source, build and install trees on each build host. An archive is returned only when its commit, CPU architecture and build contract match the request.
