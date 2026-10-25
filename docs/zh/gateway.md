# Webhook 网关

[中文](gateway.md) · [English](../en/gateway.md)

`gateway/`

## 做什么

接收 AtomGit（GitCode）的 webhook 事件，校验触发者权限，按事件类型分派给对应的 workflow。它是社区流水线的入口：AtomGit 侧只配一个 webhook 地址，具体走哪条流程由网关判断。

## 什么时候用

AtomGit 项目需要自动触发本仓 workflow 时。网关常驻运行，不随 workflow 启动。

## 处理过程

1. 校验 `X-GitCode-Token`，与 `WEBHOOK_PASSWORD` 不符返回 401。
2. 按 `object_kind` 与事件字段匹配路由；未命中返回 `{"ok":true,"ignored":true}`。
3. 校验触发者是否在允许名单内；不在名单直接拦下，不触发下游。
4. 用 GitHub token 调度目标 workflow，并查询本次运行记录，存入事件日志。

拦截发生在网关层，不在名单的请求不消耗 Actions 分钟数。

## 路由

| 事件条件 | 目标 workflow | 传入参数 |
| --- | --- | --- |
| 评论内容为 `rdvcompile`、目标分支 `master`、PR 开启 | `test-atomgit-pr.yml` | `pr_number` |
| PR 新增 `ci-pipeline-passed` 标签、PR 开启 | `reply-atomgit-ci-passed.yml` | `pr_number` |
| Issue 新建或重开、非机密 | `reply-atomgit-issue.yml` | `issue_url`、`publish` |

## 多个仓库

一个网关可以同时服务多个仓库，用 `REPOS` 声明：

```
REPOS=cann/catlass:catlass,cann/ops-nn:ops-nn,cann/ops-basic:ops-basic:develop
```

每项是 `仓库路径:SIG[:目标分支]`。目标分支省略时用 `TARGET_BRANCH`。名单按仓库所属 SIG 分别获取，各仓的允许名单也分开保存。

控制台顶部有仓库选择框，只显示当前仓库的触发记录与名单。只有一个受管仓库时不显示选择框。

## Issue 的处理规则

Issue 按**内容**分两类，不看作者身份：

| 内容 | 处理 |
| --- | --- |
| 反馈本仓库的问题（bug、异常、建议、使用疑问） | 跑 AI 分析并回复 |
| 其他（会议记录、通知、设计讨论等） | 发固定提示，提醒及时闭环；作者是 committer/maintainer 时同时分配给作者 |

判定优先看 Issue 上的类型标签；新 Issue 通常还没有标签，因此退到正文措辞。要求正文有一定长度，避免空 Issue 被当作反馈。

## 名单的作用范围

名单只约束 PR 相关的路由，Issue 分析不校验：

| 路由 | 校验名单 | 原因 |
| --- | --- | --- |
| `pr/comment/rdvcompile` | 是 | 防止任意人触发 CI |
| `pr/label/cipassed` | 是 | 由维护者操作 |
| `issue/open` | 否 | Issue 分析面向所有作者 |

角色差异（哪些作者会收到回复）由下游 workflow 判断，网关不做内容相关的决策。

## 允许名单

名单支持角色引用与显式用户名混用，逗号分隔：

| 写法 | 含义 |
| --- | --- |
| `@maintainer` | SIG maintainer，对该 SIG 名下所有仓库生效 |
| `@committer` | 该仓库的 committer，只对本仓库生效 |
| `@committer:<子目录>` | 仅该子目录的 committer |
| `alice` | 显式用户名，用于未获 committer 权限但需要触发的人 |

角色名单取自 `cann/community` 仓库的 `CANN/org-info.yaml`（maintainer）与 `CANN/sigs/<sig>/sig-info.yaml`（committer），按 TTL 刷新并本地缓存。获取失败时降级到缓存；缓存也不可用时放行，交由下游复核。

名单在管理界面可直接编辑，保存在配置文件里，改完立即生效。

## 测试模式

请求头加 `X-Dry-Run: 1` 时走完整的鉴权、路由与名单判断，但不调用 GitHub，记录为 `dry_run`。响应用 `would_dispatch` 与 `inputs` 说明将要执行什么。

## 管理界面

概览、触发记录与名单编辑。记录表里来源可直接跳到 AtomGit 的 PR 或 Issue，目标列给出本次 GitHub Actions 运行链接。

## 部署

常驻服务，容器内监听 `8000`，宿主映射到 `127.0.0.1:1109`，由 cloudflared 对外暴露。数据目录放在挂载卷内，容器重建不丢。

## 配置

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `WEBHOOK_PASSWORD` | 是 | 入站密码，需与 AtomGit webhook 配置一致；也用于解锁名单编辑 |
| `GITHUB_ACTIONS_TOKEN` | 是 | 可调度本仓 workflow 的 GitHub 凭据 |
| `ALLOW_LIST` | | 名单初始值；首次启动写入配置文件后以配置文件为准 |
| `ALLOW_FILE` | | 名单配置文件路径 |
| `SIG_NAME` | | 取哪个 SIG 的名单，默认 `catlass` |
| `GITHUB_REPO` | | 目标仓库 |
| `GITHUB_REF_BRANCH` | | workflow 的 ref |
| `REPOS` | | 受管仓库表，格式 `owner/repo:sig[:branch]`，逗号分隔；单个仓库时可省略 |
| `TARGET_BRANCH` | | `rdvcompile` 要求的目标分支 |
| `CI_PASSED_LABEL` | | 触发 CI 提醒的标签名 |
| `ATOMGIT_WEB` | | AtomGit 网页域名，默认 `atomgit.com`；用于来源链接与传给 workflow 的 Issue URL |
| `DATA_DIR` | | 数据目录，存事件库与名单配置 |

## 本地运行

```text
python -m pip install -r gateway/requirements.txt
WEBHOOK_PASSWORD=dev GITHUB_ACTIONS_TOKEN=... python -m uvicorn gateway.gateway:api --port 1109
```

测试不联网，用固定样本注入名单：

```text
python gateway/tests/test_routes.py
python gateway/tests/test_roster.py
```
