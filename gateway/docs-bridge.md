# 外部命令桥接（注册成员）

网关可以不做「转发到 workflow」，而是把事件里的文本交给一个外部命令处理。
目前用于把评论里的「姓名 手机号」批量注册到 HiDevLab。

## 设计

网关只做三件事：**取出评论正文** → **交给命令** → **记录结果**。
命令自己负责解析、鉴权、会话、写入、容错。业务逻辑一行都不进网关。

```
AtomGit 评论
  │  hidevlab-members
  │  张三 13145678912
  │  李四 13900001111
  ▼
gateway.py  ——  只取出正文，调用 BRIDGE_CMD
  ▼
bridges/hidevlab_members.sh  ——  薄封装，转调客户端
  ▼
bridges/hidevlab/hidevlab_members.py  ——  解析 + 调用 HiDevLab
  ▼
{"ok": true, "added": 2, "existed": 0}
```

## 配置

| 变量 | 说明 |
| --- | --- |
| `BRIDGE_CMD` | 要执行的命令，空则禁用桥接 |
| `BRIDGE_TRIGGER` | 评论首行的触发词，默认 `hidevlab-members` |
| `BRIDGE_TIMEOUT` | 命令超时秒数，默认 180 |
| `HIDEVLAB_ACCOUNT` | 华为账号 |
| `HIDEVLAB_PROJECT` | 项目码，默认 `PUB2111002819152646144` |

## 为什么需要预建会话

HiDevLab 登录要密码 + 短信验证码，webhook 场景下没人能输入。
所以先在服务器上人工跑一次建立加密会话缓存，之后网关用 `--require-cache` 语义读取：
缓存有效就干活，失效就**立即失败并报 `session_expired`**，绝不阻塞等输入。

服务器上首次建立会话（在有终端的环境执行一次）：

```bash
cd /opt/atomgit-actions/gateway/bridges/hidevlab
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
HIDEVLAB_ACCOUNT=<华为账号> .venv/bin/python -m ... --sms
```

会话缓存默认在 `~/.local/state/hidevlab-http/`，密钥在 `~/.config/hidevlab-http/`，
权限 0700/0600。**这两个文件不要进仓库。**

## 容错约定

- 输入格式错误 → 整批拒绝，不发任何请求
- 重名或掩码号码冲突 → 停止，交人工判断（不猜）
- 已有成员角色不符 → 停止（不擅自提权）
- 写入不重试：POST 超时可能已提交，写后必查再决定
- 会话失效 → 立即失败，不弹交互

## 换后端

改 `BRIDGE_CMD` 指向别的脚本即可。只要遵守同一约定：
stdin 收文本、stdout 写单行 JSON、退出码 0 表示成功。
