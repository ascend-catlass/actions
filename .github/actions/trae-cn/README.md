# Trae 中国版基础 stage

通过**官方中国版 TraeCode CLI 2.0** 执行一个任务。接收字符串或仓库里的
UTF-8 提示词，返回最终答复、JSONL 执行事件、stderr 和机器可读状态。
后续的 PR review、Issue triage、修复 workflow 可以组合这个 stage。

## 前置条件

- Linux runner，Python 3.9+，Git，预装中国版 `traecli` 2.0。
- 具备 CLI 使用权限的企业账号。2026-10-14 查阅的官方文档注明：
  CLI 2.0 仅向企业旗舰版套餐开放，普通企业账号是否具备权限须实际确认。
- 企业账号签发的 PAT，保存到 Actions Secret `TRAE_CN_PAT`。
  PAT 是个人访问令牌，供自动化认证使用；**邮箱密码不是 PAT**。
  生成入口请向企业管理员确认，本文不假设控制台有某个未经验证的菜单。
- runner 能访问中国版服务；企业自定义 API 域可配置变量 `TRAE_CN_HOST`。

Stage 不安装 CLI、不修改 runner 的全局登录状态。部署人员先按官方安装说明
安装并核验版本，再提供给 stage。官方安装入口是
`https://trae.cn/trae-cli/install_v2.sh`，请先下载审阅再执行。
安装路径若不在 PATH，可通过 `cli-path` 传入绝对路径。
安装器可能取最新版本；生产部署应使用经过验证的固定镜像/二进制，设置
`expected-version` 为实际版本。stage 会检查版本和所需 exec 参数，拒绝旧接口。

## 在本仓库试运行

1. 为专用 Linux runner 添加 `trae-cn` 标签，预装官方 CLI 2.0。
2. 在 GitHub 仓库 Settings → Secrets and variables → Actions 中新增
   `TRAE_CN_PAT` Secret；如使用自定义企业 API 域，新增 `TRAE_CN_HOST` 变量。
3. 在 Actions 页面手动运行 **Test Trae China stage**。
   默认读取 `.github/prompts/trae-cn-smoke.md`，以只读方式分析本仓库。
4. 下载 `trae-cn-<run_id>-<attempt>` artifact。`response.md` 是最终答复；
   `result.json` 记录状态、版本和错误说明。只有 `status=success` 才消费答复。

本地适配层测试使用模拟 CLI；真实登录、模型权限、Linux 沙箱及中国版服务
连接必须通过该手动 workflow 验证。Windows 当前不支持此 stage。

## 在其他 workflow 中组合

```yaml
permissions:
  contents: read
jobs:
  analyze:
    runs-on: [self-hosted, Linux, trae-cn]
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - id: agent
        uses: ascend-catlass/actions/.github/actions/trae-cn@main
        # 生产使用时，将 main 替换为经过验证的完整 commit SHA。
        with:
          trae-pat: ${{ secrets.TRAE_CN_PAT }}
          prompt-file: .github/prompts/review.md
          sandbox: read-only
      - if: ${{ always() && steps.agent.outputs.result-directory != '' }}
        uses: actions/upload-artifact@v4
        with:
          name: agent-result
          path: ${{ steps.agent.outputs.result-directory }}
          retention-days: 7
```

远程 action 会在调用方已经 checkout 的仓库运行。`working-directory` 相对于
`GITHUB_WORKSPACE`；提示词和 schema 路径相对于该 Git 仓库根目录，必须位于其中。
如果提示词来自独立的可信控制仓库，可由上层 stage 读取为 `prompt` 输入，
不要从 PR 分支选择能覆盖系统要求的提示词。

| 输入 | 默认 / 行为 |
| --- | --- |
| `trae-pat` | 必填，来自 Secret；不会作为命令行参数传入 |
| `prompt` / `prompt-file` | 二选一；1 MiB 上限，UTF-8，支持中文和多行 |
| `working-directory` | `.`；必须是 workspace 内的 Git checkout |
| `cli-path` | `traecli`；可用绝对路径 |
| `expected-version` | 空；设置后校验 CLI 报告的完整数字版本 |
| `model` | 空；使用企业默认模型 |
| `host` | 空；使用中国版 CLI 默认服务；自定义域须为 HTTPS |
| `sandbox` | `read-only`；修复任务显式指定 `workspace-write` |
| `output-schema-file` | 空；JSON Schema 交给 CLI 约束最终响应 |
| `timeout-seconds` | `900`；1–3600，覆盖检查版本、登录及执行 |

输出：`result-directory`、`response-file`、`events-file`、`stderr-file`、
`result-file`、`status`、`exit-code`。结果目录每次唯一，位于 `RUNNER_TEMP`。
失败和超时也发布目录及状态；stage 非零退出，默认会使 job 失败。
失败上传需使用 `always()`。若上层设置 `continue-on-error`，必须检查 status，
不要发布失败过程中写出的部分答复。强制终止 runner 时无法保证输出或清理完成。

提示词通过 stdin 传递，绝不插入 shell 代码。CLI 非交互执行，审批策略为
`never`，不使用全权限沙箱，不自动重试。最终答复限制为 10 MiB；schema 模式额外检查最终答复是合法
JSON；上层消费者还应独立校验其完整 schema 和业务约束。

每次运行在临时 HOME/XDG 目录登录，结束后删除。agent 子进程不继承
GitHub token 或任意步骤 Secret，PAT 环境变量只传入登录进程。
执行日志和答复会替换原样出现的 PAT，登录日志不导出；这不是数据泄漏防护边界，
编码或变形凭据、仓库机密、源码和提示词仍可能出现在答复和轨迹里。
artifact 的访问范围和保留时间需按实际仓库配置。

## PR / Issue 上层 workflow 的设计边界

- **上下文 stage**：确定目标仓库、Issue/PR 编号、base/head SHA；分页获取
  描述、评论、diff 和必要文件，把这些内容标成待分析数据。固定 SHA，避免
  生成答复后目标发生变化。可信提示词模板保存在控制分支。
- **运行 stage**：调用本 action。评审与分类使用只读；修复使用隔离 checkout
  和工作区可写。执行真实测试，输出测试结果，不能只相信 agent 的成功说明。
- **验证 stage**：校验结构化输出、路径和 diff 范围，检查敏感文件、生成文件、
  workflow 修改及测试；发布前重新校验目标 SHA。
- **发布 stage**：单独授予最小写权限，幂等更新机器人评论或创建修复 PR。
  GitHub token 只交给发布步骤，避免直接交给模型。处理 bot 递归触发、并发、
  head 更新、取消、限额和重复评论；自动合并应另行设计。
- **触发控制**：维护者手动/可信标签/命令触发，并先校验发起者权限。不要
  在 `pull_request_target` 中用 Secret 执行未经审核的 PR checkout。
  同样不要因 Issue 文本有 `/fix` 就在持久化特权主机上运行任务。
- **runner 隔离**：CLI 的 read-only 策略不等于主机隔离，不能防止读取所有
  主机机密或项目插件/MCP/网络操作。外部贡献任务应使用无宿主凭据、无 Docker
  socket、无 NPU 设备、无 sudo 的可销毁 worker；共享编译/NPU runner 不适合。
  本 stage 不自动净化项目级规则、hooks、插件或 MCP，须由上层工作区准备负责。

首版只提供基础执行能力和手动 smoke workflow，不开启自动评论、推送或合并。
GitCode 的 PR/Issue 上下文获取与发布也可以复用这个 stage，但认证和 API
适配应放在独立 stage。

## 调研来源

- [官方 CLI 2.0 概述与使用限制](https://docs.trae.cn/cli_about-trae-code-cli-2)
- [官方安装与 PAT 登录](https://docs.trae.cn/cli_get-started-with-trae-code-cli-2)
- [官方 exec、stdin、JSONL、最终答复和沙箱参数](https://docs.trae.cn/cli_command-line-parameters)
- [OpenAI Codex Action](https://github.com/openai/codex-action/blob/main/action.yml)：
  参考字符串/文件提示词、工作目录和最终消息输出接口。
- [Anthropic Claude Code Action](https://github.com/anthropics/claude-code-action/blob/main/action.yml)：
  参考基础执行能力与上层 GitHub 协作逻辑的职责分配。
- [ByteDance trae-agent](https://github.com/bytedance/trae-agent)：开源 agent 使用
  独立模型 provider/API key，不是中国版企业账号的替代登录方式。

未复制这些项目源码。接口以 2026-10-14 的官方文档为依据；真实 CLI 合约仍待
有权限的 runner 试跑确认。
