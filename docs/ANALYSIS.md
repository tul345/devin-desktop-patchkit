# 机制分析

> 以下结论都来自本机实测（DOM/fiber 取证、`node --check`、日志、SQLite 直查），不是推测。

## 1. 应用结构

- Electron/VS Code 系内核（Windsurf）。安装目录 `D:\Windsurf`，用户数据 `D:\Roaming\devin`。
- 参与 UI 渲染的三个 bundle（都在 `resources\app` 下）：

| key | 文件 | product.json 校验键 |
| --- | --- | --- |
| `main` | `out/vs/sessions/sessions.desktop.main.js`（44MB） | `vs/sessions/sessions.desktop.main.js` |
| `chat` | `out/vs/workbench/windsurf-chat-client/index.js`（25MB） | `vs/workbench/windsurf-chat-client/index.js` |
| `exa` | `node_modules/@exa/chat-client/index.js`（25MB） | 不在校验清单 |

- `product.json` 的 `checksums` 记录前两个文件的 sha256（base64 去 padding）。改了文件不同步校验值，应用会认为安装损坏。
- ACP 侧：扩展目录里的 `devin.exe` 被换成 6KB 启动器 + `acp_expand_shim.py`（Python）包住 `devin-core.exe`，拦截 JSON-RPC 的 `session/list`。

## 2. 白屏根因（语法残片）

历史补丁在 `isRenderable` 判定处按"链式替换"演进，候选串彼此是子串关系，某次只替掉了前一段，于是留下：

```
…}catch(ex){}return h(e.providerId)&&…&&e.title!=="Devin Local session"}&&e._meta?.["cognition.ai/isArchived"]!==!0&&…
        ▲ 箭头函数已在这儿收尾                     ▲ 多出来的一截判定链 → SyntaxError: missing ) after argument list
```

整个 bundle 解析失败 → 窗口只剩白底（日志表现为：`Window will load` 后 2 秒内 `Window will close`，无崩溃 dump、非显卡问题）。

判定与修复：对每个 bundle 做 `node --check`（ESM），并做语法区域取证；`repair` 用正则匹配这类残片，从 `[JB_DBG]` 之后的第一个 `}&&` 开始收敛成 `},`，修复后再校验一次。

## 3. 侧栏会话管道（数量为什么"慢慢来"）

`chat` bundle 里的 hook（压缩后名 `rGL`）：

```
rGL(e) = useMemo(() => {
  s = useMemo(() => rBe(e.sessionResults), …)      // 后端分页返回的 id 列表（每次 50 条）
  f = tCI(e => e.acp.sessions, …)                  // store 里的会话数组
  C = useCallback(<isRenderable>)                  // 可见性判定
  g = useMemo(<本项目 sidebar 补丁>, [f, C, s])     // ← 数据源在这一层被替换
  h = n8K(g, p)                                    // 按 sessionToSpace 分组；未映射落 cwd:<cwd>
  _ = s ? rGp({grouped: h, …}) : h
  A = Object.entries(_).map(([id, arr]) => rGS(id, arr, rGh({…}), …, title, isGrouped, !1))
  …
})
```

组件侧（同一 bundle，函数 `rzG` 起的组件）：

```
{spaces:j, hiddenSessionCounts:F, folderPartitions:q} = rzq(x, p, m, {groupSessionLimits:I, …})
J = S + R                     // S = useState(e)，e 就是 pageSize，初值 25
H = rzH(j, J, q)              // 在这层按 J 截断总量
```

- `rzq`：`if (d.sessions.length <= t) 整组保留；else 每组只取前 i = groupSessionLimits.get(...) ?? t`
- `rzH`：累加各组会话数，达到 `J` 就停 → **只有前 25 条会话会被渲染**。
- 于是即使数据早就全了，界面也只吐 25 条，然后靠"加载更多"一次次 +`p`。

实测取证（注入一次性日志，测完即撤）：

| 阶段 | 观测值 |
| --- | --- |
| 上游原版 | store 里 238 条会话可用，但界面只有 8 个目录 / 25 条 |
| 只放开 `limits` | 组件输出 238 空间 / 238 会话 → 界面 24~25 个目录 / 238 条（开局即全量） |
| store 稳定性 | 每 20 秒整轮 346 条会话，8 轮 **0 增 0 删**（说明抖动不在数据层） |

所以"数量一直变"由两件事叠加：补丁把数据源换成整库遍历（随同步进出的集合），以及组件层的 25 条闸门。

## 4. "Devin Local session" 噪音行

- 这些行的 `session.title` 与 `session.summary` 都是 `undefined`，字符串 "Devin Local session" 是**界面兜底文案**。
- 实测：104 个此类会话，全部 `providerId=devin-cli`、`userMessageCount=0`（CLI/调度握手造出来的空壳）。
- 原补丁写的是 `title !== "Devin Local session"`，永远为真 → 过滤空转。
- 正确判定：`title || summary || userMessageCount > 0` 才渲染。

## 5. ACP shim 与"先短后长"

- shim 拦截 `session/list` 响应，对 20 个 cwd 依次发子请求合并，日志形如 `expand id=.. base=50 merged=153 dirs=20`（merge 缓存 20 秒）。
- 冷启动时 `_db_dirs_and_order()` 可能还没读成功；原逻辑此时**直接返回未合并的短列表**，IDE 于是先渲染小集合、几分钟后才补齐。
- 补丁：进程启动就预热读库（线程），且首次读库失败必须重试（最多 20×0.75s），避免把短列表交给 IDE。

## 6. pyright 枚举告警

- 语言服务是 `windsurfPyright 1.29.6`（扩展 `codeium.windsurfpyright`），读取工作区 `pyrightconfig.json`，日志在
  `D:\Roaming\devin\logs\<启动时间>\window1\exthost\output_logging_*\1-Devin Pyright.log`。
- 该工作区共 191,661 个文件，其中 `工具库` 107,620（`external` 66,189 / `源码` 36,733 / `quake` 4,266）此前未被排除 → 枚举 >10 秒。
- 精确排除大块、保留自己的脚本目录后：`Found 343 source files`，2 秒完成。
