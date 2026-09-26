# 补丁明细

每条补丁 = 一个 `detect` 特征串 + 若干候选锚点（`old → new`）。执行顺序：先看 `detect` 命中就跳过（幂等），否则依次尝试候选锚点，命中要求**在文件里唯一出现**。

## sidebar —— 侧栏会话数据源：全量 + 粘性 + 快照

- 目标：`chat`、`exa`、`main`
- detect：`__JB_STB`
- 上游锚点（两种形态都支持）：
  - 原始：`let e=tfe(f),t=[];for(let n of s){let r=e.get(n);r&&C(r)&&t.push(r)}return t`（`s` = 分页 id 列表）
  - 已打"整库遍历"的中间态：`…for(let r of e.values()){r&&C(r)&&t.push(r)}…`
  - `main` 变体同理（变量 `ae/he/ee/y`）
- 替换后语义（生成代码要点）：
  1. 遍历 store 全量（`*.values()`），过 `isRenderable` 后入列表；
  2. 维护 `globalThis.__JB_STB.map`（sessionId → 会话），**已出现过的会话永不消失**；
  3. 启动时从 `localStorage["__JB_SESS"]` 播种快照 → 首帧即全量；
  4. 最多每 60 秒把最近的 ≤400 条快照写回 `localStorage`；
  5. 列表内容变化且距上次刷新 >45 秒才接受新快照（节流，避免连续抖动）。
- 验证：重启后首屏侧栏目录数/会话数与预期一致（本项目实测 24~25 目录 / 238 条），且连续采样无回退。

## noise —— 隐藏空会话噪音行

- 目标：`chat`、`exa`、`main`
- detect：`userMessageCount"]>0`
- 锚点（按特异性从高到低，取第一个唯一命中）：
  1. 历史链形态：`&&<v>._meta?.["cognition.ai/isArchived"]!==!0&&(0,<mod>.getProposedByDevinId)(<v>._meta)===void 0&&<v>.title!=="Devin Local session"`
  2. 只比较文案：`&&<v>.title!=="Devin Local session"`
  3. 干净的原始判定：`h(<v>.providerId)&&!(<v>.arenaId&&!0!==<v>.isArenaRep)`（`main` 里是 `j(...)`/`<v>.isArenaRep!==!0`）
- 统一替换为：`&&(<v>.title||<v>.summary||<v>._meta?.["cognition.ai/userMessageCount"]>0)`
- 为什么不是删掉 "Devin Local session" 那串：那是**界面兜底文案**，不是数据字段；比较它永远为真。详见 `ANALYSIS.md §4`。

## limits —— 放开侧栏渲染上限

- 目标：`chat`、`exa`（`main` 无此结构）
- detect：`rzq(x,1e9`
- 锚点：
  - `rzq(x,p,m,{groupSessionLimits:I` → `rzq(x,1e9,m,{groupSessionLimits:I`（每组上限）
  - `J=S+R,H=` → `J=1e9,H=`（总量上限，`S` 初值 25）
- 副作用：分页"加载更多"实际被绕过（`hasMore=false`），整列一次铺开。想改成"每目录最多 N 条"就把 `1e9` 换成 N。

## repair —— 语法残片修复（白屏）

- 触发：`node --check` 报 `SyntaxError`（典型 `missing ) after argument list`）
- 做法：定位 `[JB_DBG]` 之后的第一个 `}&&`，用正则匹配重复判定链
  `(?:\&\&(?:<v>\._meta\?\.\["cognition\.ai/isArchived"\]!==!0|\(0,<mod>\.getProposedByDevinId\)\(<v>\._meta\)===void 0|<v>\.title!=="Devin Local session"))+`
  并确认其后紧跟 `,`，然后删除残片（收敛成 `},`）。
- 安全门：修复后的内容必须通过 `node --check`，否则**不写入**。

## pyright —— 工作区排除清单

- `python devin-patchkit.py pyright --workspace <dir> [--extra 工具库/源码 …]`
- 幂等合并 `exclude`：默认加 `**/node_modules`、`**/__pycache__`、`**/.git`、`**/.venv`、`**/venv`、`**/site-packages`、`**/*.egg-info`，`--extra` 追加项目特有的大目录。
- 改前自动把原 `pyrightconfig.json` 备份成 `pyrightconfig.json.bak-<时间戳>`。
- 验证：看 `1-Devin Pyright.log`，出现 `Found N source files` 且秒级完成即达标。

## shim —— ACP shim 预热 + 重试

- 目标：`%DEVIN_USERDATA%\acp_expand_shim.py`
- 标记：`# [patchkit]`（命中即跳过）
- 改动：
  1. `main()` 里增加预热线程 `threading.Thread(target=_db_dirs_and_order, daemon=True).start()`；
  2. `_expand()` 中"读库失败就返回原样"改成先重试（20 次 × 0.75s）再降级。
- 安全门：写入前 `py_compile` 校验；原文件备份为 `acp_expand_shim.py.bak-<时间戳>`。
- 注意：这个文件一旦写坏，IDE 的会话列表会直接异常；本项目坚持"先写 `.new` → 编译 → 替换"。
