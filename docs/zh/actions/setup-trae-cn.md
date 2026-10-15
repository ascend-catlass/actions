# 安装官方 TRAE CN CLI

[中文](../../zh/actions/setup-trae-cn.md) · [English](../../en/actions/setup-trae-cn.md)

## 做什么

安装固定版本 0.209.1 的官方 TRAE CN 企业 CLI，校验两个下载文件的 SHA256，将命令加入 PATH。安装与模型执行分开：这个 Action 不登录、不分析、不发布评论。

## 什么时候用

Issue 分析、手动修复、PR review 与 CI 失败分析都复用它，再调用现有 trae-cn。使用 Linux x64、Bash、curl、gzip 和 sha256sum；缺少 bubblewrap 时通过 apt 安装，需要 sudo。

## 调用示例

```yaml
- uses: ascend-catlass/actions/.github/actions/setup-trae-cn@main
```

## 输入

无输入，版本和校验值由 Action 统一维护。

## 输出

无文件输出接口；后续步骤可直接执行 `traecli`。模型认证仍由 trae-cn 的独立 Secret 输入负责。
