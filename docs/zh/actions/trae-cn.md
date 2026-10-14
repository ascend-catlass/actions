# 运行 TRAE CN 分析任务

[中文](../../zh/actions/trae-cn.md) · [English](../../en/actions/trae-cn.md)

`trae-cn`

## 做什么

通过官方中国版 TRAE CLI 2.0 执行仓库分析任务，并把最终答复、执行事件和状态保存为文件，供后续步骤使用。默认以只读模式执行。

## 什么时候用

为 Issue 分析提供模型执行步骤，或在其他工作流中复用仓库分析能力。

## 执行过程

1. 检查输入、CLI 版本和所需接口，创建临时登录目录。
2. 使用企业 PAT 登录，并把提示词通过 stdin 交给非交互任务。
3. 保存答复、JSONL 事件、stderr 和 result.json，返回状态并清理临时登录环境。

## 使用前准备

- Linux runner，Python 3.9+、Git、已经下载的仓库以及预装官方中国版 CLI 2.0。此 Action 不安装 CLI。
- 有 CLI 使用权限的企业 PAT；prompt 与 prompt-file 必须二选一。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false
- id: action
  uses: ascend-catlass/actions/.github/actions/trae-cn@main
  with:
    trae-pat: ${{ secrets.TRAE_CN_PAT }}
    prompt: 'Summarize the repository structure and list the relevant source files.'
    sandbox: 'read-only'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `trae-pat` | 是 | — | 企业 TRAE CN PAT，使用 Actions Secret。 |
| `prompt` | 否 | `""` | 直接传入的任务提示词，与 prompt-file 二选一。 |
| `prompt-file` | 否 | `""` | 工作仓库内的 UTF-8 提示词文件相对路径。 |
| `working-directory` | 否 | `.` | 相对于 GITHUB_WORKSPACE 的 Git 仓库目录。 |
| `cli-path` | 否 | `traecli` | 已安装的官方中国版 CLI 2.0 可执行文件。 |
| `expected-version` | 否 | `""` | 可选的准确数字版本，设置后登录前校验。 |
| `model` | 否 | `""` | 模型名称；为空时使用企业账号默认模型。 |
| `host` | 否 | `""` | 可选 HTTPS 企业 API 域；为空使用 CLI 默认地址。 |
| `sandbox` | 否 | `read-only` | read-only 分析，或 workspace-write 修改代码。 |
| `output-schema-file` | 否 | `""` | 仓库内约束最终答复的 JSON Schema 文件。 |
| `timeout-seconds` | 否 | `900` | 包括版本检查、登录、执行在内的总秒数；允许 1–3600。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `result-directory` | 包含答复、事件、日志与状态的本次唯一目录。 |
| `response-file` | 最终答复文件路径，仅在 success 时消费。 |
| `events-file` | CLI 标准输出的 JSONL 事件文件。 |
| `stderr-file` | CLI 标准错误日志文件。 |
| `result-file` | 记录步骤状态与 CLI 版本的 JSON 文件。 |
| `status` | success、failed、timeout 或 cancelled。 |
| `exit-code` | 步骤退出码；超时为 124，非零表示失败。 |

## 说明与常见问题

- 只有 status=success 时才使用答复；失败、超时或取消会使步骤非零退出。失败日志上传需要调用方使用 always()。
- 工作目录需位于 GITHUB_WORKSPACE；提示词与 schema 文件必须在该仓库内。默认 read-only，代码修改需显式指定 workspace-write。
- PAT 只交给登录进程，模型执行不继承 GitHub Token。CLI 的只读模式不能替代宿主机隔离；外部任务宜使用可销毁且没有宿主凭据的 worker。
- 它不发布评论或推送代码。现有 Issue 工作流另行安装固定版 CLI，并用 gitcode-issue 发布结果。

## 实现与调用方

- [.github/actions/trae-cn/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/trae-cn/action.yml)
- [.github/actions/trae-cn/run.py](https://github.com/ascend-catlass/actions/blob/main/.github/actions/trae-cn/run.py)
- [.github/workflows/reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml)
- [.github/workflows/trae-cn-smoke.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/trae-cn-smoke.yml)
