# 构建与维护文档

[中文](../zh/maintaining.md) · [English](../en/maintaining.md)

文档是普通 Markdown 文件：`docs/zh/` 为中文，`docs/en/` 为英文，每个 Action 各有一页。即使没有启动文档站，也能直接在 GitHub 阅读。

## 本地预览

建议在 Python 虚拟环境安装文档依赖。在仓库根目录运行：

```text
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

然后在浏览器打开终端显示的本地地址，通常为 `http://127.0.0.1:8000/`。修改 Markdown 后会自动刷新。

## 推送前检查

```text
python scripts/check_docs.py
python -m mkdocs build --strict
git diff --check
```

第一项检查全部 Action 是否有双语页面、输入输出表格是否与接口一致、调用示例是否使用有效参数。第二项检查导航与链接，生成 `site/` 静态文件；构建目录不提交到 Git。

`docs-build.yml` 在 PR、`main` 文档相关变更后以及手动触发时执行同样的检查，并保存文档站文件为 `automation-docs-site` artifact，保留 7 天。下载并解压到 `site/` 目录后，用静态 HTTP 服务预览，例如 `python -m http.server --directory site 8000`。文件不会自动发布到 GitHub Pages。

## 新增或修改一个 Action

1. 先阅读 `.github/actions/<名称>/action.yml` 和实际脚本，确认行为。
2. 同时更新 `docs/zh/actions/<名称>.md` 与 `docs/en/actions/<名称>.md`。说明做什么、何时用、前置条件、步骤、示例、输入输出和限制。
3. 接口名称、必填标记和默认值与 `action.yml` 一致；操作相关的条件必填在正文说明。
4. 在双语概览、`mkdocs.yml` 导航和 Action 目录 README 中添加链接。
5. 完成上述检查后审查差异，再提交推送。修改运行逻辑时还要执行对应行为测试。

示例使用 Secret 引用，不使用真实凭据。区分“步骤已经实现”和“外部系统保证的结果”，例如发布分配命令评论不等于已核验平台负责人变更。

## 框架与来源

这里使用 MkDocs 1.6.1 自带主题和搜索，不依赖额外主题或多语言插件。中文与英文各自导航，页面顶端可切换对应语言；历史设计记录保留在 `docs/plans/`，不进入用户手册。

配置与严格构建依据 [MkDocs 配置文档](https://www.mkdocs.org/user-guide/configuration/)；本地预览和 Markdown 写作参见 [MkDocs 用户指南](https://www.mkdocs.org/user-guide/)。
