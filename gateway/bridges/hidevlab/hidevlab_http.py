"""兼容层：把上游测试与工具的导入名映射到本地实现。

上游 `hidevlab_http.py` 的 Client / matched / read_members 等复用自 `_core.py`，
这里只做名字转发，不改行为。
"""
from _core import (  # noqa: F401
    API, ROOT, APIError, AuthExpired, Client, ProtocolError,
    mask, matched, read_members, truth,
)
