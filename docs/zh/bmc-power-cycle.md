# BMC 下电再上电

使用 Python 3 标准库，无需安装依赖：

```console
python scripts/bmc_power_cycle.py <ip> <username> [password]
```

省略密码时读取 `BMC_PASSWORD` 环境变量，否则交互输入。不要把密码写入文件或提交记录。使用 `--status-only` 只验证登录与电源状态；使用 `--ca-cert <PEM文件>` 指定可信的 BMC 证书。默认验证 HTTPS 证书；仅在明确接受风险时使用 `--insecure` 跳过证书验证。

脚本先 GET `/itf/randomtag`，再以表单提交 POST `/itf/session`（`encrypt_flag=0`、`username`、`password`、`login_tag`）。仅支持 `encrypt_ctrl=0` 的固件。保存 Cookie 并将返回的 `CSRFToken` 放入 `X-CSRFTOKEN` 请求头。

POST `/itf/actions/power` 使用 JSON 参数 `power_command`：0 强制关机、1 开机、2 强制关机再开机、3 强制重启、5 软关机。默认执行命令 2，立即中断主机业务；若已关机则执行 1。请求失败时不自动重复命令。等待 20 秒后轮询 GET `/itf/chassis-status`，最多等待 180 秒，确认 `power_status=1`，这不代表操作系统或 SSH 已就绪。最后 DELETE `/itf/session` 退出。
