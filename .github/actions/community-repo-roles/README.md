# community-repo-roles

[中文手册](../../../docs/zh/actions/community-repo-roles.md) · [English guide](../../../docs/en/actions/community-repo-roles.md)

从已检出的 CANN community 仓库查询某个 repo 的 maintainer 和 committer。
不需要 AtomGit token，不调用人员 API；结果对应传入 checkout 的配置版本。
运行环境需要 Bash，action 使用 Python 3.12 和 PyYAML 6.0.3。

## 调用

先将 community 仓库检出到 runner 的 `community` 目录，再调用：

```yaml
- name: Checkout community
  shell: bash
  run: git clone --depth 1 https://atomgit.com/cann/community.git community

- uses: ascend-catlass/actions/.github/actions/community-repo-roles@main
  id: roles
  with:
    repository: cann/catlass
    community-path: community

- name: Consume role lists
  shell: bash
  env:
    MAINTAINERS: ${{ steps.roles.outputs.maintainers }}
    COMMITTERS: ${{ steps.roles.outputs.committers }}
    RESULT_FILE: ${{ steps.roles.outputs.result-file }}
  run: |
    printf 'Maintainers: %s\nCommitters: %s\n' "$MAINTAINERS" "$COMMITTERS"
    cat "$RESULT_FILE"
```

已有 checkout 可直接复用。需要可重现结果时，调用方应检出固定 community
commit。`repository` 接受 `owner/repo`、AtomGit 的 HTTPS 仓库 URL，
支持 `.git` 后缀；匹配时忽略仓库名大小写。

## 输出与规则

| 输出 | 格式 | 含义 |
| --- | --- | --- |
| `maintainers` | JSON 字符串数组 | 所属 SIG 在 `CANN/org-info.yaml` 中的 maintainer AtomGit ID |
| `committers` | JSON 字符串数组 | `sig-info.yaml` 中 SIG 级与匹配 repo 组显式声明的 committer ID |
| `sigs` | JSON 字符串数组 | 管理该 repo 的 SIG 名称 |
| `result` | JSON 对象 | 人员详情、各作用范围配置及来源文件 |
| `result-file` | 绝对路径 | 与 `result` 相同内容的 UTF-8 JSON 文件 |

`result.maintainers` 和 `result.committers` 保留 `atomgit_id`、可选的 `name`、
`email`。相同 AtomGit ID 忽略大小写去重，并保留首次出现的拼写和非空资料。
仓库组可配置多个 repo；同一 repo 出现在多个 SIG/仓库组时，合并人员名单。

根据 community 指导文档，maintainer 自动拥有 SIG 级 committer 权限；这里输出
分别保留角色声明，不自动把 maintainer 加入 `committers`。如需候选审批人，
可合并两个列表；本 action 的结果不能直接作为某个文件/分支的授权判断。

目录/文件级人员、分支级人员及 branch keeper 不加入上述 `committers` 列表。
它们按原始配置分别保存在 `result.scoped_configs` 的 `entry_configs`、
`branch_configs` 中。公共的 `CANN/sigs/shared_config.yaml` 单独保存在
`result.shared_config`；action 不展开路径通配符，也不计算分支或目录覆盖规则。

找不到 repo、community 路径无效或配置格式错误时，action 失败；声明为空时返回
空数组。脚本也支持本地调用（先安装相同版本的 PyYAML）：

```powershell
python scripts/community_repo_roles.py --community-path ../community --repository cann/catlass --output-file roles.json
```
