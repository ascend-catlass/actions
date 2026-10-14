# Trae 中国版基础 stage 设计

## 目标与选择

在 `.github/actions/trae-cn` 增加可组合 composite action：仓库中的提示词或
直接输入 → 官方中国版 CLI 2.0 → 答复文件、事件日志和状态。
目标是支撑未来 PR review、Issue triage、修复等 workflow，首版提供手动验证入口。
用户确认已有企业版邮箱和密码；CLI 2.0 权限和 PAT 尚未确认，不能声称真实调用成功。

方案比较：官方 `traecli exec` 与中国版账号目标一致，有 CI/PAT/stdin 接口；
开源 `trae-agent` 可自动运行，但需要独立模型 API，并不复用中国版账号；
桌面界面自动化依赖图形桌面与交互登录，难以作为稳定 CI 基础 stage。
选择官方 CLI 2.0，预安装由 runner 部署负责，避免不受控安装/升级影响任务。

## 合约

提示词二选一、显式 Git 工作目录、默认只读、可选可写、模型、版本与 JSON Schema。
stdin 输入防止 shell 注入，argv 分离参数。只使用官方公开的 PAT 登录接口，
没有邮箱密码自动登录或第三方代理。
临时 HOME/XDG 与 artifact 目录分开，每次运行唯一；登录日志和凭据不上传。
PAT 只交给登录进程，agent 环境按白名单继承网络和系统设置。
执行输出保存为文件，避免把模型返回的 workflow 命令直接写到 Actions 日志。

最终答复和完整轨迹作为文件输出，result.json 记录 status、exit_code、cli_version
和错误说明。非零、超时、空答复、schema 模式非法 JSON 均失败。预算包含版本
探测、接口探测、登录和执行。超时/信号结束进程组并清理临时登录目录。
不自动重试，避免有副作用任务重复执行。强制终止和主机故障无法保证清理。

## PR/Issue 的演进

上层按上下文获取 → 本 stage → schema/diff/测试验证 → 幂等发布划分职责。
记录和重验目标 SHA、限制触发人、控制并发和 bot 递归。发布凭据与模型隔离。
修复任务必须使用专用隔离工作区；外部内容属于数据，不能决定可信提示词和权限。
GitHub 与 GitCode 的平台 API 放在上下文/发布 stage，基础执行能力可共用。

runner 的宿主机权限、项目 hooks/插件/MCP、网络访问都不由这一封装彻底隔离。
需要可销毁且无其他主机凭据的 runner，不能把外部 PR 放到共享特权 NPU 主机。
输出 artifact 可能包含源代码和项目上下文，上层控制访问和保留时间。

## 验证与限制

标准库 unittest 覆盖输入验证、中文多行、凭据环境、隔离清理、版本与接口不匹配、
失败/空答复、超时/取消、模型/schema 参数及日志脱敏。
Linux 进程组测试只在 Linux 执行，手动 workflow 先在 GitHub-hosted Linux 跑
适配层测试，再在 `trae-cn` runner 执行真实 smoke，上传结果 7 天。
详细来源与配置说明见 `.github/actions/trae-cn/README.md`。
没有 PAT/runner 时，测试只能证明适配层逻辑，不证明企业授权、模型服务及 CLI
沙箱与配置路径的真实行为。正式启用前需要固定实际版本并完成 smoke 验收。

本次本地验证：14 项新增测试中 13 项通过，1 项 Linux 进程组测试在 Windows
跳过。三个相关 YAML 文件解析成功，git diff --check 通过。
全仓库 Python 测试额外遇到现有 NPU 检测测试无法找到 Bash 的环境错误；
未修改这些测试。尚未进行真实 Trae 调用，也未提交或推送这些改动。
