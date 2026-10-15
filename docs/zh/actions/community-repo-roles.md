# 查询社区维护者与 Committer

[中文](../../zh/actions/community-repo-roles.md) · [English](../../en/actions/community-repo-roles.md)

`community-repo-roles`

## 做什么

从已经下载的 CANN community 仓库中，找到某个项目由哪些 SIG、维护者和 Committer 负责。它按声明文件查询身份，不根据昵称猜测权限。

## 什么时候用

需要给 Issue 分配负责人，或判断 Issue 作者是否已经是项目维护人员时使用。

## 执行过程

1. 读取项目对应的社区配置及人员声明。
2. 合并仓库与 SIG 范围的角色信息。
3. 返回账号列表、SIG 列表和含来源信息的 JSON 文件。

## 使用前准备

- Linux runner、Git、Python；Action 会配置 Python 3.12 并安装 PyYAML。
- 提前下载 community 仓库，并把路径传入 community-path；不需要 AtomGit Token。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- name: Download community declarations
  run: git clone --depth 1 https://atomgit.com/cann/community.git _issue-community
- id: action
  uses: ascend-catlass/actions/.github/actions/community-repo-roles@main
  with:
    repository: 'cann/catlass'
    community-path: '_issue-community'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `repository` | 是 | — | 项目名称 owner/repo，也接受 AtomGit 的 HTTPS 项目地址。 |
| `community-path` | 是 | — | 已经存在的 community 仓库目录。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `maintainers` | 维护者平台账号的 JSON 数组。 |
| `committers` | 仓库及 SIG 中显式声明的 Committer 账号 JSON 数组。 |
| `sigs` | 负责该仓库的 SIG 名称 JSON 数组。 |
| `result` | 含人员详情、配置范围和来源文件的 JSON 对象。 |
| `result-file` | 上述 JSON 结果文件的绝对路径。 |

## 说明与常见问题

- 人员名单取决于本次 checkout 的声明，不能代替平台实际权限检查。
- 现有 Issue 工作流在模型分析前调用它；维护者或 Committer 的 Issue 走作者分配流程。

## 实现与调用方

- [.github/actions/community-repo-roles/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/community-repo-roles/action.yml)
- [scripts/community_repo_roles.py](https://github.com/ascend-catlass/actions/blob/main/scripts/community_repo_roles.py)
- [.github/workflows/reply-atomgit-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-issue.yml)
