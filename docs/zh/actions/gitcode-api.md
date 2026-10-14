# 调用 GitCode API

[中文](../../zh/actions/gitcode-api.md) · [English](../../en/actions/gitcode-api.md)

`gitcode-api`

## 做什么

把 GitCode API 的认证、请求编码和 JSON 结果保存封装成一步。上层工作流给它 API 路径和请求文件，后续步骤读取响应文件即可。

## 什么时候用

需要读取 Issue、PR 或其他 GitCode 数据，或者为新自动化流程增加 API 操作时使用。

## 执行过程

1. 检查 Token、HTTP 方法和相对 API 路径。
2. 向固定的 GitCode v5 API 地址发送请求。
3. 把 JSON 响应写入 RUNNER_TEMP，并返回文件路径。

## 使用前准备

- Linux runner，已安装 Python 3，能够访问 api.gitcode.com。
- Token 通过 Actions Secret 传入；body-file 是本地 JSON 对象文件，不应包含凭据。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/gitcode-api@main
  with:
    token: ${{ secrets.GITCODE_TOKEN }}
    method: 'GET'
    path: '/repos/cann/catlass/pulls/123'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `token` | 是 | — | 具有目标 API 权限的 GitCode Token。 |
| `method` | 否 | `GET` | HTTP 方法：GET、POST、PATCH、PUT 或 DELETE。 |
| `path` | 是 | — | 以 / 开头、相对于固定 GitCode v5 地址的 API 路径。 |
| `body-file` | 否 | `""` | 可选的本地 JSON 请求对象文件；不要放凭据。 |
| `body-encoding` | 否 | `form` | 请求正文编码：form 或 json。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `response-file` | RUNNER_TEMP 中保存 JSON 响应的 UTF-8 文件路径。 |

## 说明与常见问题

- 支持 GET、POST、PATCH、PUT、DELETE；这个通用 Action 不判断业务操作是否已经成功。
- 空的成功响应（如某些 PATCH 或 DELETE）保存为 {}；需要确认评论或标签变更时，上层步骤应再查询。

## 实现与调用方

- [.github/actions/gitcode-api/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/gitcode-api/action.yml)
- [scripts/gitcode_api.py](https://github.com/ascend-catlass/actions/blob/main/scripts/gitcode_api.py)
- [.github/workflows/reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml)
