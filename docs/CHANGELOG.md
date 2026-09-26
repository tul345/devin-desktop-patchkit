# 变更记录

## 2026-09-26 ~ 09-27（首次整理成项目）

按处理顺序，全部有实测取证：

1. **白屏**
   症状：Devin 打开即白底；日志里每个实例 `Window will load` 后 2 秒内 `Window will close`，无崩溃 dump。
   定位：`chat`/`exa` 两个 bundle `SyntaxError: missing ) after argument list`；逐条逆放补丁确认是 `isRenderable` 那处的残片。
   修复：清除残片（262/258/258 字节），三文件恢复 `PARSE_OK`，同步 `product.json` 校验值。
2. **"Devin Local session" 噪音行**
   实测：104 个空壳会话（`providerId=devin-cli`、`userMessageCount=0`、`title/summary` 为 `undefined`）。
   修复：判定改为 `title || summary || userMessageCount > 0`；侧栏该文案行数 0。
3. **数量抖动 / 慢慢补齐**
   取证：store 每 20 秒整轮 346 条、8 轮 0 增 0 删（数据层稳定）；界面 8 目录 / 25 条。
   定位：组件层 `rzq(x, p, …)` 每组上限 + `rzH(j, J=S+R, …)` 总量上限（`S` 初值 25）。
   修复：`sidebar`（全量 + 粘性 + 快照）+ `limits`（两组上限放开）。
   结果：重启后首屏 **24~25 个目录 / 238 条会话**，无渲染异常。
4. **pyright 枚举告警**
   取证：语言服务 `windsurfPyright 1.29.6` 加载工作区 `pyrightconfig.json`；工作区 191,661 文件，`工具库` 107,620 未排除。
   修复：精确排除 `工具库/{源码,external,quake,字典,临时输出,payload库}` + 通用大目录；日志从超时变为 `Found 343 source files`（2 秒）。
5. **ACP shim 冷启动短列表**
   取证：`acp_shim_expand.log` 每分钟 `base=50 merged=153 dirs=20`；全日志仅 3 次子查询超时。
   修复：预热线程 + 失败重试。
6. **收尾**
   撤掉所有临时调试注入、关闭临时调试端口、应用干净重启；改动按动作分目录备份到 `D:\Roaming\devin\Backups`。

## 事故与教训

- 打 shim 补丁时，脚本用 `open(path, "w", newline="\\n")` 触发 `ValueError`，但文件**已被截断为 0 字节**。
  已从备份恢复并 `py_compile` 通过。此后所有写入改为"写 `.new` → 校验 → `os.replace`"（见 `patcher.py`）。
- 判断"是否已修复"必须用可观测证据（DOM 文本、日志、`node --check`、SQLite 计数），不接受"看起来应该行"。
- 早期几次"数量在抖动"的结论来自**测量脚本自身的截断**（只读了侧栏前 1500 字符），后来改用全窗口读取并做整轮对比才定位准确。
