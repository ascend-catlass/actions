"""把「姓名 手机号」逐行注册到 HiDevLab。

这是被网关桥接调用的客户端，不面向人直接使用。
- 输入：stdin，每行一个人，形如 `张三 13145678912`
- 输出：stdout 单行 JSON
- 鉴权：必须已有有效会话缓存（HIDEVLAB_ACCOUNT + 缓存文件），否则直接失败
  不提示密码、不发短信——webhook 场景下没人能输入验证码。

协议实现复用同目录 `_core.py`（来自上游 hidevlab_http.py 的 Client）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _core  # noqa: E402
import session_cache  # noqa: E402


def emit(ok: bool, **extra) -> int:
    """输出单行 JSON 并返回退出码。"""
    payload = {"ok": ok}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else 1


# 触发词：首行若与此相同则跳过（它是评论里的指令，不是数据）
TRIGGER = os.environ.get("BRIDGE_TRIGGER", "hidevlab-members")


def parse_lines(text: str) -> tuple[list[dict], list[str]]:
    """解析输入。返回 (成员列表, 错误列表)。

    每行格式：姓名 + 空白 + 手机号。姓名可含空格。
    首行的触发词、空行、# 注释行都跳过。
    """
    members: list[dict] = []
    errors: list[str] = []
    seen: dict[str, str] = {}

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == TRIGGER:          # 指令行，不是成员
            continue

        # 末尾必须是 11 位数字手机号
        m = re.match(r"^(.+?)[\s,，\t]+(1\d{10})$", line)
        if not m:
            errors.append(f"第 {lineno} 行格式错误：{line[:40]}")
            continue

        name, phone = m.group(1).strip(), m.group(2)
        if not name:
            errors.append(f"第 {lineno} 行姓名为空")
            continue
        if phone in seen:
            if seen[phone] != name:
                errors.append(f"第 {lineno} 行手机号 {phone} 对应多个姓名")
            continue          # 重复的直接跳过，不算错
        seen[phone] = name
        members.append({"name": name, "phone": phone})

    return members, errors


def main() -> int:
    account = os.environ.get("HIDEVLAB_ACCOUNT", "").strip()
    project = os.environ.get("HIDEVLAB_PROJECT", "").strip()
    if not account or not project:
        return emit(False, error="missing_config",
                    detail="需要 HIDEVLAB_ACCOUNT 与 HIDEVLAB_PROJECT")

    text = sys.stdin.read()
    members, errors = parse_lines(text)
    if errors:
        return emit(False, error="invalid_input", detail="; ".join(errors[:5]),
                    total_errors=len(errors))
    if not members:
        return emit(True, added=0, existed=0, detail="没有可处理的成员")

    # 会话只从缓存恢复，绝不交互
    client = _core.Client()
    cache_path = session_cache.default_path(account)
    try:
        resumed = client.resume_cache(account, cache_path)
    except Exception:  # noqa: BLE001
        return emit(False, error="cache_error", detail="会话缓存不可用")
    if not resumed:
        return emit(False, error="session_expired",
                    detail="会话缓存无效，需要在服务器上人工刷新一次")

    added: list[str] = []
    existed: list[str] = []
    try:
        rows = client.members(project)
        role = client.role(project)

        for member in members:
            name, phone = member["name"], member["phone"]
            try:
                existing = _core.matched(rows, name, phone)
            except _core.ProtocolError as exc:
                # 重名或掩码冲突：停下来交人工判断，不猜
                return emit(False, error="ambiguous", detail=str(exc),
                            added=len(added), existed=len(existed))

            if existing:
                if existing.get("roleCode") != role:
                    return emit(False, error="role_mismatch",
                                detail=f"{name} 已存在但角色不符",
                                added=len(added), existed=len(existed))
                existed.append(name)
                continue

            # 不重试：POST 超时可能已提交，先写后查是安全做法
            try:
                client.add(project, member, role)
            except Exception:  # noqa: BLE001
                pass

            rows = client.members(project)      # 写后必查
            try:
                found = _core.matched(rows, name, phone)
            except _core.ProtocolError:
                found = None
            if found and found.get("roleCode") == role:
                added.append(name)
            else:
                return emit(False, error="add_uncertain",
                            detail=f"{name} 写入结果不确定，已停止",
                            added=len(added), existed=len(existed))

    except _core.ProtocolError as exc:
        return emit(False, error="protocol", detail=str(exc),
                    added=len(added), existed=len(existed))
    except Exception as exc:  # noqa: BLE001
        return emit(False, error=type(exc).__name__,
                    detail=str(exc)[:200],
                    added=len(added), existed=len(existed))

    return emit(True, added=len(added), existed=len(existed),
                detail=f"新增 {len(added)}，已存在 {len(existed)}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        # 不打印 traceback——里面可能带请求细节
        print(json.dumps({"ok": False, "error": "internal"}, ensure_ascii=False))
        sys.exit(1)
