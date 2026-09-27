# 变更记录

## 2026-09-27（v1.1.0）修复：归档 / 删除失效

症状：侧栏里归档（Archive）和删除点了没反应，条目仍在。

定位（有取证）：v1.0.0 的 `sidebar` 包装代码里 `globalThis.__JB_STB.map` 是永不清理的跨帧缓存：

```js
for(const [k_,v_] of Z.map){ !L.has(k_) && C(v_) && t.push(v_) }   // 把淘汰的旧对象重新加回列表
```

- 归档：store 里 `isArchived` 已变 `true`，但缓存持有的旧对象仍是 `false` → 被重新加入并再次入栈；
- 删除：会话从 store 移除后由缓存复活，`localStorage["__JB_SESS"]` 快照还会在下次启动把它带回来；
- 实测：缓存里累计 242 条会话，其中 `isArchived=true` 的 **0 条**（缓存从未跟随刷新）。

修复：`sidebar` 移除全部跨帧缓存与持久化快照，列表每帧从 store 现值重建，仅保留 45 秒节流；首次运行会清理旧缓存与 `__JB_SESS`。detect 改为新版本特有标记，保证旧版本能被识别为"待迁移"。

验证：
- 单元测试 7/7 通过（新增"迁移旧粘性实现"回归与"不得出现 Z.map"断言）；
- 抽出**部署后的真实代码**在 Node 里跑场景：初始 `a,b,c` → 归档 b 得 `a,c` → 删除 c 得 `a` → 反复渲染仍 `a` → 恢复得 `a,b,c`，全部符合预期；
- 真实环境：重启后 `localStorage.__JB_SESS = null`、`__JB_STB.map` 已移除、渲染异常 0、侧栏 25 个目录完整。


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
