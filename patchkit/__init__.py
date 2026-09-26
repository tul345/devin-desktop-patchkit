# SPDX-License-Identifier: MIT
"""devin-desktop-patchkit —— Devin Desktop(Windsurf 内核) 本地补丁工具包。

解决的问题：
1. 侧栏白屏（补丁残留造成 bundle 语法错误）
2. 侧栏出现 "Devin Local session" 噪音行
3. 会话数量慢慢变多 / 抖动，不能"开局即全量"
4. 工作区过大导致 pyright 枚举超 10 秒告警
5. ACP shim 冷启动时把短列表交给 IDE
"""

__version__ = "1.0.0"
