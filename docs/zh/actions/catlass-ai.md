# 执行 CATLASS AI 分析

[中文](../../zh/actions/catlass-ai.md) · [English](../../en/actions/catlass-ai.md)

Issue 简要分析、Issue 修复、PR 检视和失败分析共用此执行策略。模型只在这里选择
DeepSeek-V4.1-Flash，企业地址读取调用方环境中的可选变量 TRAE_CN_HOST；统一准备只读沙箱并组合
公共 setup-traecn 和 traecn Action。CLI 版本校验引用安装输出，不另写版本号。
本 Action 不接收发布凭据。

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `pat` | 是 | — | TRAE CN 企业 PAT。 |
| `working-directory` | 是 | — | GITHUB_WORKSPACE 内已准备的 Git 目录。 |
| `prompt-file` | 是 | — | 相对该目录的可信提示词文件。 |
| `output-schema-file` | 否 | `""` | 相对该目录的可选答复 schema。 |
| `timeout-seconds` | 否 | `900` | 模型执行时间预算。 |

## 输出

| 字段 | 说明 |
| --- | --- |
| `result-directory` | 同一次执行的 response.md 和 result.json 所在目录。 |
| `status` | success、failed、timeout 或 cancelled。 |

## 调用示例

需要 Linux、安装 bubblewrap 时所需的 sudo 权限，以及包含提示词的已准备 Git 目录。
发布和过期状态检查由调用方负责。

```yaml
- id: ai
  uses: ascend-catlass/actions/.github/actions/catlass-ai@main
  with:
    pat: ${{ secrets.TRAE_CN_PAT }}
    working-directory: _task-source
    prompt-file: .automation-context/prompt.md
```

下游只传 result-directory，不再单独填写模型 ID。

工作流使用 `env: { TRAE_CN_HOST: '${{ vars.TRAE_CN_HOST }}' }` 映射仓库变量。
composite Action 内不能直接使用 vars 上下文；空值沿用账号默认地址。
