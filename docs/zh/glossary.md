# 常用术语

[中文](../zh/glossary.md) · [English](../en/glossary.md)

| 术语 | 通俗解释 |
| --- | --- |
| Action | 可以被多条工作流重复使用的步骤，例如“读取 PR 信息” |
| Workflow / 工作流 | 一套完整自动化流程，定义触发条件、任务和步骤 |
| Job / 任务 | 工作流中在某个 runner 上执行的一组步骤 |
| Runner | 真正执行自动化的机器；可以是 GitHub 提供的机器，也可以是自托管昇腾主机 |
| PR | Pull Request，贡献者提交的待合并代码变更 |
| Issue | 项目的问题报告或需求讨论 |
| CI | 自动构建和测试；在本仓库中，PR 测试会把结果写回 GitCode |
| RDV | 本仓库 PR 测试流程使用的名称，对应 `RDV-RUNNING`、`RDV-SUCC`、`RDV-FAIL` 标签 |
| Committer / Maintainer | 社区声明中的项目角色；本仓库可从 community 配置读取对应平台账号 |
| SIG | 社区中负责某个技术领域的 Special Interest Group |
| SHA / gitlink | SHA 是准确的提交标识；gitlink 是主仓库记录的子模块提交，供依赖构建匹配 |
| CANN / NPU | CANN 是昇腾计算软件环境；NPU 是执行设备测试的处理器 |
| DSL / NPUIR | DSL 是 CATLASS 的领域语言组件；NPUIR 在这里指其 AscendNPU-IR 编译依赖 |
| wheel | Python 安装包文件，扩展名为 `.whl` |
| Artifact / 产物 | 工作流保存的文件，例如安装包、日志和分析答复，可按保留时间下载 |
| Secret / Token / PAT | Secret 是凭据保存方式；Token/PAT 是自动化访问服务的凭据 |
| Dry run | 只准备或分析，不执行指定的发布操作；具体以各流程支持的开关为准 |
